import { createHash, randomBytes, randomUUID } from "node:crypto";
import {
  appendFile,
  lstat,
  mkdir,
  open,
  readFile,
  rename,
  rm,
} from "node:fs/promises";
import { dirname, join } from "node:path";

export const DOC_ID = "shared-workpad";
const MAX_MARKDOWN_BYTES = 192 * 1024;
const MAX_ACTIVITY_BYTES = 2 * 1024 * 1024;
const MAX_AUTH_BYTES = 2 * 1024 * 1024;
const MAX_NOTE_CHARS = 4_000;
const SESSION_TTL_MS = 7 * 24 * 60 * 60 * 1_000;

export type Actor = {
  canEdit: boolean;
  docs: Set<string>;
  id: string;
  kind: "human" | "agent";
  role: "owner" | "editor" | "viewer";
};

export type ActivityEvent = {
  actor: { id: string; kind: string; role: string };
  base_sha: string;
  doc_id: string;
  event_id: string;
  note: string;
  result_sha: string;
  source_refs: string[];
  ts: string;
  verb: "edited" | "noted";
};

type StorePaths = {
  dataDir: string;
  seedPath: string;
};

type WriteOptions = StorePaths & {
  actor: Actor;
  baseSha: string;
  eventId?: () => string;
  now?: () => string;
};

export class ConflictError extends Error {
  currentSha: string;

  constructor(currentSha: string) {
    super("The workpad changed after this editor loaded.");
    this.currentSha = currentSha;
  }
}

export function sha256(value: string | Uint8Array): string {
  return createHash("sha256").update(value).digest("hex");
}

async function pathKind(path: string): Promise<"missing" | "file" | "symlink" | "other"> {
  try {
    const info = await lstat(path);
    if (info.isSymbolicLink()) return "symlink";
    if (info.isFile()) return "file";
    return "other";
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") return "missing";
    throw error;
  }
}

async function boundedRead(path: string, limit: number): Promise<Buffer> {
  const kind = await pathKind(path);
  if (kind === "symlink") throw new Error(`Refusing symlink: ${path}`);
  if (kind !== "file") throw new Error(`Expected file: ${path}`);
  const value = await readFile(path);
  if (value.byteLength > limit) throw new Error(`File exceeds ${limit} bytes: ${path}`);
  return value;
}

async function sourceBytes({ dataDir, seedPath }: StorePaths): Promise<Buffer> {
  const documentPath = join(dataDir, `${DOC_ID}.md`);
  const kind = await pathKind(documentPath);
  if (kind === "symlink") throw new Error(`Refusing symlink: ${documentPath}`);
  return boundedRead(kind === "file" ? documentPath : seedPath, MAX_MARKDOWN_BYTES);
}

async function activityRecords(dataDir: string): Promise<ActivityEvent[]> {
  const path = join(dataDir, `${DOC_ID}.activity.jsonl`);
  const kind = await pathKind(path);
  if (kind === "missing") return [];
  if (kind !== "file") throw new Error(`Expected file: ${path}`);
  const content = await boundedRead(path, MAX_ACTIVITY_BYTES);
  const records: ActivityEvent[] = [];
  for (const line of content.toString("utf8").split(/\r?\n/)) {
    if (!line) continue;
    try {
      const parsed: unknown = JSON.parse(line);
      if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
        records.push(parsed as ActivityEvent);
      }
    } catch {
      // A torn or malformed line never hides valid surrounding provenance.
    }
  }
  return records;
}

async function reconciledSource(
  paths: StorePaths,
  records: ActivityEvent[],
): Promise<Buffer> {
  let ledgerSource = await boundedRead(paths.seedPath, MAX_MARKDOWN_BYTES);
  let ledgerSha = sha256(ledgerSource);
  const ledgerShas = new Set([ledgerSha]);

  for (const event of records) {
    if (event.verb !== "edited") continue;
    if (
      event.doc_id !== DOC_ID ||
      event.base_sha !== ledgerSha ||
      !/^[0-9a-f]{64}$/.test(event.result_sha)
    ) {
      throw new Error("Workpad provenance chain is invalid.");
    }
    const revision = await boundedRead(
      join(paths.dataDir, "revisions", `${event.result_sha}.md`),
      MAX_MARKDOWN_BYTES,
    );
    if (sha256(revision) !== event.result_sha) {
      throw new Error("Workpad revision does not match its provenance hash.");
    }
    ledgerSource = revision;
    ledgerSha = event.result_sha;
    ledgerShas.add(ledgerSha);
  }

  const current = await sourceBytes(paths);
  const currentSha = sha256(current);
  if (currentSha === ledgerSha) return current;
  if (!ledgerShas.has(currentSha)) {
    throw new Error("Refusing an unledgered Workpad projection.");
  }
  await atomicWrite(join(paths.dataDir, `${DOC_ID}.md`), ledgerSource);
  return ledgerSource;
}

export async function loadDocument(paths: StorePaths) {
  const records = await activityRecords(paths.dataDir);
  const source = await reconciledSource(paths, records);
  return {
    activity: records.slice(-200).reverse(),
    doc_id: DOC_ID,
    markdown: source.toString("utf8"),
    sha: sha256(source),
  };
}

async function atomicWrite(path: string, value: Uint8Array): Promise<void> {
  await mkdir(dirname(path), { recursive: true });
  const kind = await pathKind(path);
  if (kind === "symlink") throw new Error(`Refusing symlink: ${path}`);
  const temporary = `${path}.${process.pid}.${randomUUID()}.tmp`;
  const handle = await open(temporary, "wx", 0o600);
  try {
    await handle.writeFile(value);
    await handle.sync();
  } finally {
    await handle.close();
  }
  try {
    await rename(temporary, path);
  } finally {
    await rm(temporary, { force: true });
  }
}

async function appendEvent(dataDir: string, event: ActivityEvent): Promise<void> {
  await mkdir(dataDir, { recursive: true });
  const path = join(dataDir, `${DOC_ID}.activity.jsonl`);
  const kind = await pathKind(path);
  if (kind === "symlink") throw new Error(`Refusing symlink: ${path}`);
  await appendFile(path, `${JSON.stringify(event)}\n`, { encoding: "utf8", mode: 0o600 });
  const handle = await open(path, "r");
  try {
    await handle.sync();
  } finally {
    await handle.close();
  }
}

const queues = new Map<string, Promise<unknown>>();

function serialized<T>(key: string, operation: () => Promise<T>): Promise<T> {
  const prior = queues.get(key) ?? Promise.resolve();
  const current = prior.catch(() => undefined).then(operation);
  queues.set(key, current);
  return current.finally(() => {
    if (queues.get(key) === current) queues.delete(key);
  });
}

function makeEvent({
  actor,
  baseSha,
  resultSha,
  verb,
  note,
  now = () => new Date().toISOString(),
  eventId = () => `evt:${randomUUID()}`,
}: {
  actor: Actor;
  baseSha: string;
  resultSha: string;
  verb: ActivityEvent["verb"];
  note: string;
  now?: () => string;
  eventId?: () => string;
}): ActivityEvent {
  return {
    actor: { id: actor.id, kind: actor.kind, role: actor.role },
    base_sha: baseSha,
    doc_id: DOC_ID,
    event_id: eventId(),
    note,
    result_sha: resultSha,
    source_refs: [],
    ts: now(),
    verb,
  };
}

export async function saveDocument({
  dataDir,
  seedPath,
  actor,
  baseSha,
  markdown,
  note,
  now,
  eventId,
}: WriteOptions & { markdown: string; note: string }) {
  const encoded = Buffer.from(markdown, "utf8");
  if (encoded.byteLength === 0 || encoded.byteLength > MAX_MARKDOWN_BYTES) {
    throw new RangeError("Markdown must be between 1 byte and 192 KiB.");
  }
  if (note.length > MAX_NOTE_CHARS) throw new RangeError("Note exceeds 4,000 characters.");

  return serialized(dataDir, async () => {
    const records = await activityRecords(dataDir);
    const current = await reconciledSource({ dataDir, seedPath }, records);
    const currentSha = sha256(current);
    if (baseSha !== currentSha) throw new ConflictError(currentSha);
    const resultSha = sha256(encoded);
    if (resultSha === currentSha) {
      return { event: null, saved: false, sha: currentSha };
    }

    await atomicWrite(join(dataDir, "revisions", `${currentSha}.md`), current);
    await atomicWrite(join(dataDir, "revisions", `${resultSha}.md`), encoded);
    const event = makeEvent({
      actor,
      baseSha: currentSha,
      eventId,
      note,
      now,
      resultSha,
      verb: "edited",
    });
    await appendEvent(dataDir, event);
    await atomicWrite(join(dataDir, `${DOC_ID}.md`), encoded);
    return { event, saved: true, sha: resultSha };
  });
}

export async function appendNote({
  dataDir,
  seedPath,
  actor,
  baseSha,
  note,
  now,
  eventId,
}: WriteOptions & { note: string }) {
  const normalized = note.trim();
  if (!normalized || normalized.length > MAX_NOTE_CHARS) {
    throw new RangeError("A note between 1 and 4,000 characters is required.");
  }
  return serialized(dataDir, async () => {
    const records = await activityRecords(dataDir);
    const current = await reconciledSource({ dataDir, seedPath }, records);
    const currentSha = sha256(current);
    if (baseSha !== currentSha) throw new ConflictError(currentSha);
    const event = makeEvent({
      actor,
      baseSha: currentSha,
      eventId,
      note: normalized,
      now,
      resultSha: currentSha,
      verb: "noted",
    });
    await appendEvent(dataDir, event);
    return { event, sha: currentSha };
  });
}

function tokenFields(line: string): Map<string, string> {
  const fields = new Map<string, string>();
  for (const part of line.trim().split(/\s+/)) {
    const separator = part.indexOf("=");
    if (separator > 0) fields.set(part.slice(0, separator), part.slice(separator + 1));
  }
  return fields;
}

type SessionIssued = {
  actor: { id: string; kind: Actor["kind"]; role: Actor["role"] };
  docs: string[];
  event: "session_issued";
  expires: string;
  invite_hash: string;
  session_hash: string;
  ts: string;
};

type SessionRevoked = {
  event: "session_revoked";
  session_hash: string;
  ts: string;
};

type SessionEvent = SessionIssued | SessionRevoked;

async function privateBytes(path: string, limit: number): Promise<Buffer | null> {
  const kind = await pathKind(path);
  if (kind === "missing") return null;
  if (kind !== "file") return null;
  const info = await lstat(path);
  if ((info.mode & 0o077) !== 0) return null;
  return boundedRead(path, limit);
}

async function invitation(
  tokensPath: string,
  token: string,
  now: Date,
): Promise<{ actor: Actor; deadline: Date } | null> {
  const content = await privateBytes(tokensPath, 128 * 1024);
  if (!content) return null;
  let selected: Map<string, string> | null = null;
  for (const raw of content.toString("utf8").split(/\r?\n/)) {
    const line = raw.trim();
    if (!line || line.startsWith("#")) continue;
    const fields = tokenFields(line);
    if (fields.get("token") === token) {
      selected = fields;
      break;
    }
  }
  if (!selected) return null;

  const role = selected.get("role");
  if (role !== "owner" && role !== "editor" && role !== "viewer") return null;
  const docs = new Set((selected.get("docs") ?? "").split(",").filter(Boolean));
  if (!docs.has(DOC_ID)) return null;
  const expires = selected.get("expires");
  if (!expires) return null;
  const deadline = new Date(expires);
  if (Number.isNaN(deadline.valueOf()) || deadline <= now) return null;
  const actorKind = selected.get("kind");
  return {
    actor: {
      canEdit: role === "owner" || role === "editor",
      docs,
      id: selected.get("id") || "collaborator",
      kind: actorKind === "agent" ? "agent" : "human",
      role,
    },
    deadline,
  };
}

function validSessionEvent(value: unknown): value is SessionEvent {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const event = value as Record<string, unknown>;
  if (
    (event.event !== "session_issued" && event.event !== "session_revoked") ||
    typeof event.session_hash !== "string" ||
    typeof event.ts !== "string"
  ) {
    return false;
  }
  if (event.event === "session_revoked") return true;
  if (
    typeof event.expires !== "string" ||
    typeof event.invite_hash !== "string" ||
    !Array.isArray(event.docs) ||
    !event.docs.every((doc) => typeof doc === "string") ||
    !event.actor ||
    typeof event.actor !== "object" ||
    Array.isArray(event.actor)
  ) {
    return false;
  }
  const actor = event.actor as Record<string, unknown>;
  return (
    typeof actor.id === "string" &&
    (actor.kind === "human" || actor.kind === "agent") &&
    (actor.role === "owner" || actor.role === "editor" || actor.role === "viewer")
  );
}

async function sessionEvents(path: string): Promise<SessionEvent[] | null> {
  const kind = await pathKind(path);
  if (kind === "missing") return [];
  const content = await privateBytes(path, MAX_AUTH_BYTES);
  if (!content) return null;
  const records: SessionEvent[] = [];
  for (const line of content.toString("utf8").split(/\r?\n/)) {
    if (!line) continue;
    let parsed: unknown;
    try {
      parsed = JSON.parse(line);
    } catch {
      return null;
    }
    if (!validSessionEvent(parsed)) return null;
    records.push(parsed);
  }
  return records;
}

async function appendSessionEvent(path: string, event: SessionEvent): Promise<void> {
  await mkdir(dirname(path), { recursive: true });
  const kind = await pathKind(path);
  if (kind === "symlink" || kind === "other") {
    throw new Error(`Refusing session store: ${path}`);
  }
  if (kind === "file") {
    const info = await lstat(path);
    if ((info.mode & 0o077) !== 0) {
      throw new Error("Session store must be mode 600.");
    }
  }
  await appendFile(path, `${JSON.stringify(event)}\n`, {
    encoding: "utf8",
    mode: 0o600,
  });
  const handle = await open(path, "r");
  try {
    await handle.sync();
  } finally {
    await handle.close();
  }
}

function actorFromSession(
  records: SessionEvent[],
  sessionHash: string,
  now: Date,
): Actor | null {
  let issued: SessionIssued | null = null;
  let revoked = false;
  for (const record of records) {
    if (record.session_hash !== sessionHash) continue;
    if (record.event === "session_issued") {
      issued = record;
      revoked = false;
    } else {
      revoked = true;
    }
  }
  if (!issued || revoked) return null;
  const deadline = new Date(issued.expires);
  if (Number.isNaN(deadline.valueOf()) || deadline <= now) return null;
  const docs = new Set(issued.docs);
  if (!docs.has(DOC_ID)) return null;
  return {
    canEdit: issued.actor.role === "owner" || issued.actor.role === "editor",
    docs,
    id: issued.actor.id,
    kind: issued.actor.kind,
    role: issued.actor.role,
  };
}

export async function redeemInvite({
  tokensPath,
  sessionsPath,
  token,
  now = new Date(),
  sessionToken = () => randomBytes(32).toString("base64url"),
}: {
  tokensPath: string;
  sessionsPath: string;
  token: string;
  now?: Date;
  sessionToken?: () => string;
}): Promise<{ actor: Actor; expires: string; token: string } | null> {
  return serialized(sessionsPath, async () => {
    const selected = await invitation(tokensPath, token, now);
    const records = await sessionEvents(sessionsPath);
    if (!selected || !records) return null;
    const inviteHash = sha256(token);
    if (
      records.some(
        (record) =>
          record.event === "session_issued" && record.invite_hash === inviteHash,
      )
    ) {
      return null;
    }

    const opaqueToken = sessionToken();
    if (!opaqueToken || opaqueToken === token) {
      throw new Error("Session token must be separate from its invitation.");
    }
    const expires = new Date(
      Math.min(selected.deadline.valueOf(), now.valueOf() + SESSION_TTL_MS),
    ).toISOString();
    const event: SessionIssued = {
      actor: {
        id: selected.actor.id,
        kind: selected.actor.kind,
        role: selected.actor.role,
      },
      docs: [...selected.actor.docs],
      event: "session_issued",
      expires,
      invite_hash: inviteHash,
      session_hash: sha256(opaqueToken),
      ts: now.toISOString(),
    };
    await appendSessionEvent(sessionsPath, event);
    return { actor: selected.actor, expires, token: opaqueToken };
  });
}

export async function resolveSession(
  sessionsPath: string,
  token: string,
  now = new Date(),
): Promise<Actor | null> {
  const records = await sessionEvents(sessionsPath);
  return records ? actorFromSession(records, sha256(token), now) : null;
}

export async function revokeSession({
  sessionsPath,
  token,
  now = new Date(),
}: {
  sessionsPath: string;
  token: string;
  now?: Date;
}): Promise<boolean> {
  return serialized(sessionsPath, async () => {
    const records = await sessionEvents(sessionsPath);
    const sessionHash = sha256(token);
    if (!records || !actorFromSession(records, sessionHash, now)) return false;
    await appendSessionEvent(sessionsPath, {
      event: "session_revoked",
      session_hash: sessionHash,
      ts: now.toISOString(),
    });
    return true;
  });
}
