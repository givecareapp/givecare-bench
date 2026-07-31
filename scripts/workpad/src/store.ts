import { createHash, randomBytes, randomUUID } from "node:crypto";
import {
  appendFile,
  lstat,
  mkdir,
  open,
  readFile,
  readdir,
  rename,
  rm,
  rmdir,
} from "node:fs/promises";
import { dirname, join } from "node:path";

import { diff3Merge } from "node-diff3";
import { lock } from "proper-lockfile";

export const DEFAULT_DOC_ID = "shared-workpad";
const DOC_ID_PATTERN = /^[a-z0-9][a-z0-9-]{0,63}$/;
const SHA_PATTERN = /^[0-9a-f]{64}$/;
const ARCHIVE_PATTERN = /^activity\.(\d+)\.jsonl$/;
const MAX_ACTIVITY_BYTES = 8 * 1024 * 1024;
const MAX_AUTH_BYTES = 2 * 1024 * 1024;
const MAX_MARKDOWN_BYTES = 192 * 1024;
const MAX_NOTE_CHARS = 4_000;
const ROTATE_ACTIVITY_BYTES = 1024 * 1024;
const SESSION_TTL_MS = 7 * 24 * 60 * 60 * 1_000;
const LOCK_OPTIONS = {
  retries: { maxTimeout: 400, minTimeout: 40, retries: 5 },
  stale: 10_000,
};

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
  verb: "checkpoint" | "edited" | "noted";
};

export type DocRef = {
  dataDir: string;
  docId: string;
  seedPath: string;
};

export type SaveResult = {
  event: ActivityEvent | null;
  markdown?: string;
  merged: boolean;
  saved: boolean;
  sha: string;
};

type DocPaths = {
  activity: string;
  archive: string;
  document: string;
  revisions: string;
  root: string;
};

type WriteOptions = DocRef & {
  actor: Actor;
  baseSha: string;
  eventId?: () => string;
  now?: () => string;
};

const SYSTEM_ACTOR: ActivityEvent["actor"] = {
  id: "workpad",
  kind: "agent",
  role: "owner",
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

function docPaths({ dataDir, docId }: DocRef): DocPaths {
  if (!DOC_ID_PATTERN.test(docId)) throw new RangeError(`Invalid document id: ${docId}`);
  const root = join(dataDir, docId);
  return {
    activity: join(root, "activity.jsonl"),
    archive: join(root, "archive"),
    document: join(root, "doc.md"),
    revisions: join(root, "revisions"),
    root,
  };
}

function revisionPath(paths: DocPaths, sha: string): string {
  return join(paths.revisions, `${sha}.md`);
}

function legacyPaths(dataDir: string) {
  return {
    activity: join(dataDir, `${DEFAULT_DOC_ID}.activity.jsonl`),
    document: join(dataDir, `${DEFAULT_DOC_ID}.md`),
    revisions: join(dataDir, "revisions"),
  };
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

async function isDirectory(path: string): Promise<boolean> {
  try {
    return (await lstat(path)).isDirectory();
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") return false;
    throw error;
  }
}

async function fileSize(path: string): Promise<number> {
  try {
    const info = await lstat(path);
    return info.isFile() ? info.size : 0;
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") return 0;
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

async function appendEvent(path: string, event: ActivityEvent): Promise<void> {
  await mkdir(dirname(path), { recursive: true });
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

async function locked<T>(target: string, operation: () => Promise<T>): Promise<T> {
  await mkdir(target, { recursive: true });
  const release = await lock(target, LOCK_OPTIONS);
  try {
    return await operation();
  } finally {
    await release();
  }
}

async function migrateLegacy(ref: DocRef, paths: DocPaths): Promise<string[]> {
  if (ref.docId !== DEFAULT_DOC_ID) return [];
  const legacy = legacyPaths(ref.dataDir);
  const actions: string[] = [];

  for (const [from, to] of [
    [legacy.document, paths.document],
    [legacy.activity, paths.activity],
  ]) {
    const kind = await pathKind(from);
    if (kind === "missing") continue;
    if (kind === "symlink") throw new Error(`Refusing symlink: ${from}`);
    if (kind !== "file" || (await pathKind(to)) !== "missing") continue;
    await mkdir(paths.root, { recursive: true });
    await rename(from, to);
    actions.push(`moved ${from} to ${to}`);
  }

  if (await isDirectory(legacy.revisions)) {
    await mkdir(paths.revisions, { recursive: true });
    for (const entry of await readdir(legacy.revisions)) {
      const from = join(legacy.revisions, entry);
      const to = join(paths.revisions, entry);
      if ((await pathKind(from)) !== "file" || (await pathKind(to)) !== "missing") continue;
      await rename(from, to);
    }
    try {
      await rmdir(legacy.revisions);
      actions.push(`moved ${legacy.revisions} to ${paths.revisions}`);
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code !== "ENOTEMPTY") throw error;
    }
  }
  return actions;
}

async function hasLegacyLayout(ref: DocRef): Promise<boolean> {
  if (ref.docId !== DEFAULT_DOC_ID) return false;
  const legacy = legacyPaths(ref.dataDir);
  for (const path of [legacy.document, legacy.activity, legacy.revisions]) {
    if ((await pathKind(path)) !== "missing") return true;
  }
  return false;
}

function mutation<T>(ref: DocRef, operation: (paths: DocPaths) => Promise<T>): Promise<T> {
  const paths = docPaths(ref);
  return serialized(paths.root, () =>
    locked(paths.root, async () => {
      await migrateLegacy(ref, paths);
      return operation(paths);
    }),
  );
}

async function migrated(ref: DocRef): Promise<void> {
  if (await hasLegacyLayout(ref)) await mutation(ref, async () => undefined);
}

function parseActivity(content: string): ActivityEvent[] {
  const records: ActivityEvent[] = [];
  for (const line of content.split(/\r?\n/)) {
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

async function activityRecords(path: string): Promise<ActivityEvent[]> {
  const kind = await pathKind(path);
  if (kind === "missing") return [];
  if (kind !== "file") throw new Error(`Expected file: ${path}`);
  const content = await boundedRead(path, MAX_ACTIVITY_BYTES);
  return parseActivity(content.toString("utf8"));
}

async function archiveLedgers(
  paths: DocPaths,
): Promise<{ path: string; sequence: number }[]> {
  if (!(await isDirectory(paths.archive))) return [];
  const matched: { path: string; sequence: number }[] = [];
  for (const name of await readdir(paths.archive)) {
    const match = ARCHIVE_PATTERN.exec(name);
    if (match) {
      matched.push({ path: join(paths.archive, name), sequence: Number(match[1]) });
    }
  }
  return matched.sort((left, right) => left.sequence - right.sequence);
}

async function anchorRecords(
  paths: DocPaths,
  active: ActivityEvent[],
): Promise<ActivityEvent[]> {
  if (active.length > 0) return active;
  const last = (await archiveLedgers(paths)).at(-1);
  return last ? activityRecords(last.path) : [];
}

async function projectionBytes(ref: DocRef, paths: DocPaths): Promise<Buffer> {
  const kind = await pathKind(paths.document);
  if (kind === "symlink") throw new Error(`Refusing symlink: ${paths.document}`);
  return boundedRead(kind === "file" ? paths.document : ref.seedPath, MAX_MARKDOWN_BYTES);
}

function chainHead(records: ActivityEvent[]): ActivityEvent | null {
  for (let index = records.length - 1; index >= 0; index -= 1) {
    const event = records[index];
    if (event.verb === "edited" || event.verb === "checkpoint") return event;
  }
  return null;
}

async function verifiedProjection(
  ref: DocRef,
  paths: DocPaths,
  records: ActivityEvent[],
): Promise<Buffer> {
  const head = chainHead(records);
  if (head && !SHA_PATTERN.test(head.result_sha)) {
    throw new Error("Workpad provenance chain is invalid.");
  }
  const expectedSha = head
    ? head.result_sha
    : sha256(await boundedRead(ref.seedPath, MAX_MARKDOWN_BYTES));
  if (head && (await pathKind(revisionPath(paths, expectedSha))) !== "file") {
    throw new Error("Workpad revision is missing for its ledgered state.");
  }

  const current = await projectionBytes(ref, paths);
  const currentSha = sha256(current);
  if (currentSha === expectedSha) return current;

  const ledgered = new Set<string>();
  for (const event of records) {
    ledgered.add(event.base_sha);
    ledgered.add(event.result_sha);
  }
  if (!head || !ledgered.has(currentSha)) {
    throw new Error("Refusing an unledgered Workpad projection.");
  }

  const revision = await boundedRead(revisionPath(paths, expectedSha), MAX_MARKDOWN_BYTES);
  if (sha256(revision) !== expectedSha) {
    throw new Error("Workpad revision does not match its provenance hash.");
  }
  await atomicWrite(paths.document, revision);
  return revision;
}

export async function loadDocument(ref: DocRef) {
  const paths = docPaths(ref);
  await migrated(ref);
  const records = await activityRecords(paths.activity);
  const source = await verifiedProjection(
    ref,
    paths,
    await anchorRecords(paths, records),
  );
  return {
    activity: records.slice(-200).reverse(),
    doc_id: ref.docId,
    markdown: source.toString("utf8"),
    sha: sha256(source),
  };
}

function makeEvent({
  actor,
  baseSha,
  docId,
  resultSha,
  verb,
  note,
  now = () => new Date().toISOString(),
  eventId = () => `evt:${randomUUID()}`,
}: {
  actor: ActivityEvent["actor"];
  baseSha: string;
  docId: string;
  resultSha: string;
  verb: ActivityEvent["verb"];
  note: string;
  now?: () => string;
  eventId?: () => string;
}): ActivityEvent {
  return {
    actor: { id: actor.id, kind: actor.kind, role: actor.role },
    base_sha: baseSha,
    doc_id: docId,
    event_id: eventId(),
    note,
    result_sha: resultSha,
    source_refs: [],
    ts: now(),
    verb,
  };
}

async function rotate({
  actor,
  current,
  docId,
  eventId,
  now,
  paths,
}: {
  actor: ActivityEvent["actor"];
  current: Buffer;
  docId: string;
  eventId?: () => string;
  now?: () => string;
  paths: DocPaths;
}): Promise<{ archive: string | null; event: ActivityEvent }> {
  let archive: string | null = null;
  if ((await pathKind(paths.activity)) === "file") {
    const sequence = ((await archiveLedgers(paths)).at(-1)?.sequence ?? 0) + 1;
    await mkdir(paths.archive, { recursive: true });
    archive = join(paths.archive, `activity.${sequence}.jsonl`);
    await rename(paths.activity, archive);
  }
  const currentSha = sha256(current);
  await atomicWrite(revisionPath(paths, currentSha), current);
  const event = makeEvent({
    actor,
    baseSha: currentSha,
    docId,
    eventId,
    note: "",
    now,
    resultSha: currentSha,
    verb: "checkpoint",
  });
  await appendEvent(paths.activity, event);
  return { archive, event };
}

function lines(value: Buffer): string[] {
  return value.toString("utf8").split("\n");
}

async function mergedBytes({
  baseSha,
  current,
  currentSha,
  incoming,
  paths,
}: {
  baseSha: string;
  current: Buffer;
  currentSha: string;
  incoming: Buffer;
  paths: DocPaths;
}): Promise<Buffer> {
  if (!SHA_PATTERN.test(baseSha)) throw new ConflictError(currentSha);
  const basePath = revisionPath(paths, baseSha);
  if ((await pathKind(basePath)) !== "file") throw new ConflictError(currentSha);
  const base = await boundedRead(basePath, MAX_MARKDOWN_BYTES);
  if (sha256(base) !== baseSha) {
    throw new Error("Workpad revision does not match its provenance hash.");
  }

  const merged: string[] = [];
  for (const region of diff3Merge(lines(current), lines(base), lines(incoming), {
    excludeFalseConflicts: true,
  })) {
    if (!region.ok) throw new ConflictError(currentSha);
    merged.push(...region.ok);
  }

  const value = Buffer.from(merged.join("\n"), "utf8");
  if (value.byteLength === 0 || value.byteLength > MAX_MARKDOWN_BYTES) {
    throw new RangeError("Markdown must be between 1 byte and 192 KiB.");
  }
  return value;
}

export async function saveDocument({
  dataDir,
  docId,
  seedPath,
  actor,
  baseSha,
  markdown,
  note,
  now,
  eventId,
}: WriteOptions & { markdown: string; note: string }): Promise<SaveResult> {
  const encoded = Buffer.from(markdown, "utf8");
  if (encoded.byteLength === 0 || encoded.byteLength > MAX_MARKDOWN_BYTES) {
    throw new RangeError("Markdown must be between 1 byte and 192 KiB.");
  }
  if (note.length > MAX_NOTE_CHARS) throw new RangeError("Note exceeds 4,000 characters.");
  const ref = { dataDir, docId, seedPath };

  return mutation(ref, async (paths) => {
    const records = await activityRecords(paths.activity);
    const current = await verifiedProjection(
      ref,
      paths,
      await anchorRecords(paths, records),
    );
    const currentSha = sha256(current);
    const merged = baseSha !== currentSha;
    const next = merged
      ? await mergedBytes({ baseSha, current, currentSha, incoming: encoded, paths })
      : encoded;
    const resultSha = sha256(next);
    if (resultSha === currentSha) {
      return merged
        ? {
            event: null,
            markdown: next.toString("utf8"),
            merged,
            saved: false,
            sha: currentSha,
          }
        : { event: null, merged, saved: false, sha: currentSha };
    }

    await atomicWrite(revisionPath(paths, currentSha), current);
    await atomicWrite(revisionPath(paths, resultSha), next);
    if ((await fileSize(paths.activity)) > ROTATE_ACTIVITY_BYTES) {
      await rotate({ actor: SYSTEM_ACTOR, current, docId, now, paths });
    }
    const event = makeEvent({
      actor,
      baseSha: currentSha,
      docId,
      eventId,
      note,
      now,
      resultSha,
      verb: "edited",
    });
    await appendEvent(paths.activity, event);
    await atomicWrite(paths.document, next);
    return merged
      ? { event, markdown: next.toString("utf8"), merged, saved: true, sha: resultSha }
      : { event, merged, saved: true, sha: resultSha };
  });
}

export async function appendNote({
  dataDir,
  docId,
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
  const ref = { dataDir, docId, seedPath };

  return mutation(ref, async (paths) => {
    const records = await activityRecords(paths.activity);
    const current = await verifiedProjection(
      ref,
      paths,
      await anchorRecords(paths, records),
    );
    const currentSha = sha256(current);
    if (baseSha !== currentSha) throw new ConflictError(currentSha);
    const event = makeEvent({
      actor,
      baseSha: currentSha,
      docId,
      eventId,
      note: normalized,
      now,
      resultSha: currentSha,
      verb: "noted",
    });
    await appendEvent(paths.activity, event);
    return { event, sha: currentSha };
  });
}

export async function listDocs(dataDir: string): Promise<string[]> {
  let entries;
  try {
    entries = await readdir(dataDir, { withFileTypes: true });
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") return [];
    throw error;
  }
  const docs: string[] = [];
  for (const entry of entries) {
    if (!entry.isDirectory() || !DOC_ID_PATTERN.test(entry.name)) continue;
    const root = join(dataDir, entry.name);
    if (
      (await pathKind(join(root, "doc.md"))) === "file" ||
      (await pathKind(join(root, "activity.jsonl"))) === "file"
    ) {
      docs.push(entry.name);
    }
  }
  return docs.sort();
}

export async function fsckDocument(ref: DocRef): Promise<{ ok: boolean; issues: string[] }> {
  const paths = docPaths(ref);
  await migrated(ref);
  const issues: string[] = [];
  let expected = sha256(await boundedRead(ref.seedPath, MAX_MARKDOWN_BYTES));
  let seen = 0;

  const ledgers = (await archiveLedgers(paths)).map((entry) => entry.path);
  for (const ledger of [...ledgers, paths.activity]) {
    for (const event of await activityRecords(ledger)) {
      seen += 1;
      const label = `${event.event_id ?? "unknown"}`;
      if (event.doc_id !== ref.docId) {
        issues.push(`${label}: belongs to ${event.doc_id}, not ${ref.docId}`);
      }
      if (!SHA_PATTERN.test(event.result_sha) || !SHA_PATTERN.test(event.base_sha)) {
        issues.push(`${label}: malformed provenance hashes`);
        continue;
      }
      if (event.verb === "checkpoint") {
        if (event.base_sha !== event.result_sha) {
          issues.push(`${label}: checkpoint does not rest on its own state`);
        }
        if (seen === 1) expected = event.result_sha;
        else if (event.result_sha !== expected) {
          issues.push(`${label}: checkpoint does not match the replayed state`);
          expected = event.result_sha;
        }
        continue;
      }
      if (event.base_sha !== expected) {
        issues.push(`${label}: base_sha does not follow the chain`);
      }
      if (event.verb === "noted") {
        if (event.result_sha !== event.base_sha) {
          issues.push(`${label}: a note may not change the document`);
        }
        continue;
      }
      try {
        const revision = await boundedRead(
          revisionPath(paths, event.result_sha),
          MAX_MARKDOWN_BYTES,
        );
        if (sha256(revision) !== event.result_sha) {
          issues.push(`${label}: revision does not match its provenance hash`);
        }
      } catch {
        issues.push(`${label}: revision ${event.result_sha} is unreadable`);
      }
      expected = event.result_sha;
    }
  }

  const current = await projectionBytes(ref, paths);
  if (sha256(current) !== expected) {
    issues.push("projection does not match the replayed ledger state");
  }
  return { issues, ok: issues.length === 0 };
}

async function quarantineTail(
  path: string,
  stamp: string,
  valid: (value: unknown) => boolean,
): Promise<string | null> {
  if ((await pathKind(path)) !== "file") return null;
  const content = (await boundedRead(path, MAX_ACTIVITY_BYTES)).toString("utf8");
  const trailing = content.slice(content.lastIndexOf("\n") + 1);
  if (!trailing) return null;

  let parsed: unknown;
  try {
    parsed = JSON.parse(trailing);
  } catch {
    parsed = undefined;
  }
  if (parsed !== undefined && valid(parsed)) {
    await atomicWrite(path, Buffer.from(`${content}\n`, "utf8"));
    return `terminated the unfinished final line of ${path}`;
  }
  const quarantine = `${path}.quarantine-${stamp}`;
  await atomicWrite(quarantine, Buffer.from(trailing, "utf8"));
  await atomicWrite(
    path,
    Buffer.from(content.slice(0, content.length - trailing.length), "utf8"),
  );
  return `quarantined a torn line to ${quarantine}`;
}

function activityShaped(value: unknown): boolean {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

export async function repairDocument(
  ref: DocRef & { sessionsPath?: string },
): Promise<{ repaired: boolean; actions: string[] }> {
  const stamp = new Date().toISOString();
  const actions: string[] = [];

  if (ref.sessionsPath) {
    const sessionsPath = ref.sessionsPath;
    const repaired = await sessionMutation(sessionsPath, () =>
      quarantineTail(sessionsPath, stamp, validSessionEvent),
    );
    if (repaired) actions.push(repaired);
  }

  const docActions = await mutation(ref, async (paths) => {
    const performed: string[] = [];
    const quarantined = await quarantineTail(paths.activity, stamp, activityShaped);
    if (quarantined) performed.push(quarantined);

    const records = await anchorRecords(paths, await activityRecords(paths.activity));
    const head = chainHead(records);
    const expected = head
      ? head.result_sha
      : sha256(await boundedRead(ref.seedPath, MAX_MARKDOWN_BYTES));
    const current = await projectionBytes(ref, paths);
    if (sha256(current) === expected) return performed;
    if (!head) {
      performed.push("refused: the projection diverges with no ledgered revision");
      return performed;
    }
    let revision: Buffer;
    try {
      revision = await boundedRead(revisionPath(paths, expected), MAX_MARKDOWN_BYTES);
    } catch {
      performed.push(`refused: revision ${expected} is unreadable`);
      return performed;
    }
    if (sha256(revision) !== expected) {
      performed.push(`refused: revision ${expected} does not match its provenance hash`);
      return performed;
    }
    await atomicWrite(paths.document, revision);
    performed.push(`rematerialized the projection from revision ${expected}`);
    return performed;
  });

  actions.push(...docActions);
  return {
    actions,
    repaired: actions.some((action) => !action.startsWith("refused:")),
  };
}

export async function compactDocument({
  dataDir,
  docId,
  seedPath,
  actor,
  eventId,
  now,
}: DocRef & {
  actor?: Actor;
  eventId?: () => string;
  now?: () => string;
}): Promise<{ archive: string | null; event: ActivityEvent }> {
  const ref = { dataDir, docId, seedPath };
  return mutation(ref, async (paths) => {
    const current = await verifiedProjection(
      ref,
      paths,
      await anchorRecords(paths, await activityRecords(paths.activity)),
    );
    return rotate({
      actor: actor ?? SYSTEM_ACTOR,
      current,
      docId,
      eventId,
      now,
      paths,
    });
  });
}

export async function gcRevisions(
  ref: DocRef,
  { apply = false }: { apply?: boolean } = {},
): Promise<{ deleted: string[]; referenced: number; unreferenced: string[] }> {
  const survey = async (paths: DocPaths) => {
    const referenced = new Set<string>();
    for (const event of await activityRecords(paths.activity)) {
      referenced.add(event.base_sha);
      referenced.add(event.result_sha);
    }
    referenced.add(sha256(await projectionBytes(ref, paths)));
    const unreferenced: string[] = [];
    let kept = 0;
    if (await isDirectory(paths.revisions)) {
      for (const name of (await readdir(paths.revisions)).sort()) {
        const sha = name.endsWith(".md") ? name.slice(0, -3) : "";
        if (!SHA_PATTERN.test(sha)) continue;
        if (referenced.has(sha)) kept += 1;
        else unreferenced.push(sha);
      }
    }
    return { referenced: kept, unreferenced };
  };

  if (!apply) {
    await migrated(ref);
    return { ...(await survey(docPaths(ref))), deleted: [] };
  }
  return mutation(ref, async (paths) => {
    const found = await survey(paths);
    for (const sha of found.unreferenced) {
      await rm(revisionPath(paths, sha), { force: true });
    }
    return { ...found, deleted: found.unreferenced };
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
  if (!docs.has(DEFAULT_DOC_ID)) return null;
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
  const text = content.toString("utf8");
  const rows = text.split(/\r?\n/);
  const torn = text.endsWith("\n") ? -1 : rows.length - 1;
  const records: SessionEvent[] = [];
  for (const [index, line] of rows.entries()) {
    if (!line) continue;
    let parsed: unknown;
    try {
      parsed = JSON.parse(line);
    } catch {
      // A crash mid-append leaves a partial final line; earlier damage is not ours to guess.
      if (index === torn) continue;
      return null;
    }
    if (!validSessionEvent(parsed)) {
      if (index === torn) continue;
      return null;
    }
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

function sessionMutation<T>(sessionsPath: string, operation: () => Promise<T>): Promise<T> {
  return serialized(sessionsPath, () => locked(dirname(sessionsPath), operation));
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
  if (!docs.has(DEFAULT_DOC_ID)) return null;
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
  return sessionMutation(sessionsPath, async () => {
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
  return sessionMutation(sessionsPath, async () => {
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
