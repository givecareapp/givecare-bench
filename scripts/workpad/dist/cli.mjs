#!/usr/bin/env node

// src/cli.ts
import { readFile as readFile2 } from "node:fs/promises";
import { parseArgs } from "node:util";
import { pathToFileURL } from "node:url";

// src/store.ts
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
  rmdir
} from "node:fs/promises";
import { dirname, join } from "node:path";
import { diff3Merge } from "node-diff3";
import { lock } from "proper-lockfile";
var DEFAULT_DOC_ID = "shared-workpad";
var DOC_ID_PATTERN = /^[a-z0-9][a-z0-9-]{0,63}$/;
var SHA_PATTERN = /^[0-9a-f]{64}$/;
var ARCHIVE_PATTERN = /^activity\.(\d+)\.jsonl$/;
var MAX_ACTIVITY_BYTES = 8 * 1024 * 1024;
var MAX_AUTH_BYTES = 2 * 1024 * 1024;
var MAX_MARKDOWN_BYTES = 192 * 1024;
var MAX_NOTE_CHARS = 4e3;
var ROTATE_ACTIVITY_BYTES = 1024 * 1024;
var SESSION_TTL_MS = 7 * 24 * 60 * 60 * 1e3;
var LOCK_OPTIONS = {
  retries: { maxTimeout: 400, minTimeout: 40, retries: 5 },
  stale: 1e4
};
var SYSTEM_ACTOR = {
  id: "workpad",
  kind: "agent",
  role: "owner"
};
var ConflictError = class extends Error {
  currentSha;
  constructor(currentSha) {
    super("The workpad changed after this editor loaded.");
    this.currentSha = currentSha;
  }
};
function sha256(value) {
  return createHash("sha256").update(value).digest("hex");
}
function docPaths({ dataDir, docId }) {
  if (!DOC_ID_PATTERN.test(docId)) throw new RangeError(`Invalid document id: ${docId}`);
  const root = join(dataDir, docId);
  return {
    activity: join(root, "activity.jsonl"),
    archive: join(root, "archive"),
    document: join(root, "doc.md"),
    revisions: join(root, "revisions"),
    root
  };
}
function revisionPath(paths, sha) {
  return join(paths.revisions, `${sha}.md`);
}
function legacyPaths(dataDir) {
  return {
    activity: join(dataDir, `${DEFAULT_DOC_ID}.activity.jsonl`),
    document: join(dataDir, `${DEFAULT_DOC_ID}.md`),
    revisions: join(dataDir, "revisions")
  };
}
async function pathKind(path) {
  try {
    const info = await lstat(path);
    if (info.isSymbolicLink()) return "symlink";
    if (info.isFile()) return "file";
    return "other";
  } catch (error) {
    if (error.code === "ENOENT") return "missing";
    throw error;
  }
}
async function isDirectory(path) {
  try {
    return (await lstat(path)).isDirectory();
  } catch (error) {
    if (error.code === "ENOENT") return false;
    throw error;
  }
}
async function fileSize(path) {
  try {
    const info = await lstat(path);
    return info.isFile() ? info.size : 0;
  } catch (error) {
    if (error.code === "ENOENT") return 0;
    throw error;
  }
}
async function boundedRead(path, limit) {
  const kind = await pathKind(path);
  if (kind === "symlink") throw new Error(`Refusing symlink: ${path}`);
  if (kind !== "file") throw new Error(`Expected file: ${path}`);
  const value = await readFile(path);
  if (value.byteLength > limit) throw new Error(`File exceeds ${limit} bytes: ${path}`);
  return value;
}
async function atomicWrite(path, value) {
  await mkdir(dirname(path), { recursive: true });
  const kind = await pathKind(path);
  if (kind === "symlink") throw new Error(`Refusing symlink: ${path}`);
  const temporary = `${path}.${process.pid}.${randomUUID()}.tmp`;
  const handle = await open(temporary, "wx", 384);
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
async function appendEvent(path, event) {
  await mkdir(dirname(path), { recursive: true });
  const kind = await pathKind(path);
  if (kind === "symlink") throw new Error(`Refusing symlink: ${path}`);
  await appendFile(path, `${JSON.stringify(event)}
`, { encoding: "utf8", mode: 384 });
  const handle = await open(path, "r");
  try {
    await handle.sync();
  } finally {
    await handle.close();
  }
}
var queues = /* @__PURE__ */ new Map();
function serialized(key, operation) {
  const prior = queues.get(key) ?? Promise.resolve();
  const current = prior.catch(() => void 0).then(operation);
  queues.set(key, current);
  return current.finally(() => {
    if (queues.get(key) === current) queues.delete(key);
  });
}
async function locked(target, operation) {
  await mkdir(target, { recursive: true });
  const release = await lock(target, LOCK_OPTIONS);
  try {
    return await operation();
  } finally {
    await release();
  }
}
async function migrateLegacy(ref, paths) {
  if (ref.docId !== DEFAULT_DOC_ID) return [];
  const legacy = legacyPaths(ref.dataDir);
  const actions = [];
  for (const [from, to] of [
    [legacy.document, paths.document],
    [legacy.activity, paths.activity]
  ]) {
    const kind = await pathKind(from);
    if (kind === "missing") continue;
    if (kind === "symlink") throw new Error(`Refusing symlink: ${from}`);
    if (kind !== "file" || await pathKind(to) !== "missing") continue;
    await mkdir(paths.root, { recursive: true });
    await rename(from, to);
    actions.push(`moved ${from} to ${to}`);
  }
  if (await isDirectory(legacy.revisions)) {
    await mkdir(paths.revisions, { recursive: true });
    for (const entry of await readdir(legacy.revisions)) {
      const from = join(legacy.revisions, entry);
      const to = join(paths.revisions, entry);
      if (await pathKind(from) !== "file" || await pathKind(to) !== "missing") continue;
      await rename(from, to);
    }
    try {
      await rmdir(legacy.revisions);
      actions.push(`moved ${legacy.revisions} to ${paths.revisions}`);
    } catch (error) {
      if (error.code !== "ENOTEMPTY") throw error;
    }
  }
  return actions;
}
async function hasLegacyLayout(ref) {
  if (ref.docId !== DEFAULT_DOC_ID) return false;
  const legacy = legacyPaths(ref.dataDir);
  for (const path of [legacy.document, legacy.activity, legacy.revisions]) {
    if (await pathKind(path) !== "missing") return true;
  }
  return false;
}
function mutation(ref, operation) {
  const paths = docPaths(ref);
  return serialized(
    paths.root,
    () => locked(paths.root, async () => {
      await migrateLegacy(ref, paths);
      return operation(paths);
    })
  );
}
async function migrated(ref) {
  if (await hasLegacyLayout(ref)) await mutation(ref, async () => void 0);
}
function parseActivity(content) {
  const records = [];
  for (const line of content.split(/\r?\n/)) {
    if (!line) continue;
    try {
      const parsed = JSON.parse(line);
      if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
        records.push(parsed);
      }
    } catch {
    }
  }
  return records;
}
async function activityRecords(path) {
  const kind = await pathKind(path);
  if (kind === "missing") return [];
  if (kind !== "file") throw new Error(`Expected file: ${path}`);
  const content = await boundedRead(path, MAX_ACTIVITY_BYTES);
  return parseActivity(content.toString("utf8"));
}
async function archiveLedgers(paths) {
  if (!await isDirectory(paths.archive)) return [];
  const matched = [];
  for (const name of await readdir(paths.archive)) {
    const match = ARCHIVE_PATTERN.exec(name);
    if (match) {
      matched.push({ path: join(paths.archive, name), sequence: Number(match[1]) });
    }
  }
  return matched.sort((left, right) => left.sequence - right.sequence);
}
async function anchorRecords(paths, active) {
  if (active.length > 0) return active;
  const last = (await archiveLedgers(paths)).at(-1);
  return last ? activityRecords(last.path) : [];
}
async function projectionBytes(ref, paths) {
  const kind = await pathKind(paths.document);
  if (kind === "symlink") throw new Error(`Refusing symlink: ${paths.document}`);
  return boundedRead(kind === "file" ? paths.document : ref.seedPath, MAX_MARKDOWN_BYTES);
}
function chainHead(records) {
  for (let index = records.length - 1; index >= 0; index -= 1) {
    const event = records[index];
    if (event.verb === "edited" || event.verb === "checkpoint") return event;
  }
  return null;
}
async function verifiedProjection(ref, paths, records) {
  const head = chainHead(records);
  if (head && !SHA_PATTERN.test(head.result_sha)) {
    throw new Error("Workpad provenance chain is invalid.");
  }
  const expectedSha = head ? head.result_sha : sha256(await boundedRead(ref.seedPath, MAX_MARKDOWN_BYTES));
  if (head && await pathKind(revisionPath(paths, expectedSha)) !== "file") {
    throw new Error("Workpad revision is missing for its ledgered state.");
  }
  const current = await projectionBytes(ref, paths);
  const currentSha = sha256(current);
  if (currentSha === expectedSha) return current;
  const ledgered = /* @__PURE__ */ new Set();
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
async function loadDocument(ref) {
  const paths = docPaths(ref);
  await migrated(ref);
  const records = await activityRecords(paths.activity);
  const source = await verifiedProjection(
    ref,
    paths,
    await anchorRecords(paths, records)
  );
  return {
    activity: records.slice(-200).reverse(),
    doc_id: ref.docId,
    markdown: source.toString("utf8"),
    sha: sha256(source)
  };
}
function makeEvent({
  actor,
  baseSha,
  docId,
  resultSha,
  verb,
  note,
  now = () => (/* @__PURE__ */ new Date()).toISOString(),
  eventId = () => `evt:${randomUUID()}`
}) {
  return {
    actor: { id: actor.id, kind: actor.kind, role: actor.role },
    base_sha: baseSha,
    doc_id: docId,
    event_id: eventId(),
    note,
    result_sha: resultSha,
    source_refs: [],
    ts: now(),
    verb
  };
}
async function rotate({
  actor,
  current,
  docId,
  eventId,
  now,
  paths
}) {
  let archive = null;
  if (await pathKind(paths.activity) === "file") {
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
    verb: "checkpoint"
  });
  await appendEvent(paths.activity, event);
  return { archive, event };
}
function lines(value) {
  return value.toString("utf8").split("\n");
}
async function mergedBytes({
  baseSha,
  current,
  currentSha,
  incoming,
  paths
}) {
  if (!SHA_PATTERN.test(baseSha)) throw new ConflictError(currentSha);
  const basePath = revisionPath(paths, baseSha);
  if (await pathKind(basePath) !== "file") throw new ConflictError(currentSha);
  const base = await boundedRead(basePath, MAX_MARKDOWN_BYTES);
  if (sha256(base) !== baseSha) {
    throw new Error("Workpad revision does not match its provenance hash.");
  }
  const merged = [];
  for (const region of diff3Merge(lines(current), lines(base), lines(incoming), {
    excludeFalseConflicts: true
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
async function saveDocument({
  dataDir,
  docId,
  seedPath,
  actor,
  baseSha,
  markdown,
  note,
  now,
  eventId
}) {
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
      await anchorRecords(paths, records)
    );
    const currentSha = sha256(current);
    const merged = baseSha !== currentSha;
    const next = merged ? await mergedBytes({ baseSha, current, currentSha, incoming: encoded, paths }) : encoded;
    const resultSha = sha256(next);
    if (resultSha === currentSha) {
      return merged ? {
        event: null,
        markdown: next.toString("utf8"),
        merged,
        saved: false,
        sha: currentSha
      } : { event: null, merged, saved: false, sha: currentSha };
    }
    await atomicWrite(revisionPath(paths, currentSha), current);
    await atomicWrite(revisionPath(paths, resultSha), next);
    if (await fileSize(paths.activity) > ROTATE_ACTIVITY_BYTES) {
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
      verb: "edited"
    });
    await appendEvent(paths.activity, event);
    await atomicWrite(paths.document, next);
    return merged ? { event, markdown: next.toString("utf8"), merged, saved: true, sha: resultSha } : { event, merged, saved: true, sha: resultSha };
  });
}
async function appendNote({
  dataDir,
  docId,
  seedPath,
  actor,
  baseSha,
  note,
  now,
  eventId
}) {
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
      await anchorRecords(paths, records)
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
      verb: "noted"
    });
    await appendEvent(paths.activity, event);
    return { event, sha: currentSha };
  });
}
async function listDocs(dataDir) {
  let entries;
  try {
    entries = await readdir(dataDir, { withFileTypes: true });
  } catch (error) {
    if (error.code === "ENOENT") return [];
    throw error;
  }
  const docs = [];
  for (const entry of entries) {
    if (!entry.isDirectory() || !DOC_ID_PATTERN.test(entry.name)) continue;
    const root = join(dataDir, entry.name);
    if (await pathKind(join(root, "doc.md")) === "file" || await pathKind(join(root, "activity.jsonl")) === "file") {
      docs.push(entry.name);
    }
  }
  return docs.sort();
}
async function fsckDocument(ref) {
  const paths = docPaths(ref);
  await migrated(ref);
  const issues = [];
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
          MAX_MARKDOWN_BYTES
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
async function quarantineTail(path, stamp, valid) {
  if (await pathKind(path) !== "file") return null;
  const content = (await boundedRead(path, MAX_ACTIVITY_BYTES)).toString("utf8");
  const trailing = content.slice(content.lastIndexOf("\n") + 1);
  if (!trailing) return null;
  let parsed;
  try {
    parsed = JSON.parse(trailing);
  } catch {
    parsed = void 0;
  }
  if (parsed !== void 0 && valid(parsed)) {
    await atomicWrite(path, Buffer.from(`${content}
`, "utf8"));
    return `terminated the unfinished final line of ${path}`;
  }
  const quarantine = `${path}.quarantine-${stamp}`;
  await atomicWrite(quarantine, Buffer.from(trailing, "utf8"));
  await atomicWrite(
    path,
    Buffer.from(content.slice(0, content.length - trailing.length), "utf8")
  );
  return `quarantined a torn line to ${quarantine}`;
}
function activityShaped(value) {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}
async function repairDocument(ref) {
  const stamp = (/* @__PURE__ */ new Date()).toISOString();
  const actions = [];
  if (ref.sessionsPath) {
    const sessionsPath = ref.sessionsPath;
    const repaired = await sessionMutation(
      sessionsPath,
      () => quarantineTail(sessionsPath, stamp, validSessionEvent)
    );
    if (repaired) actions.push(repaired);
  }
  const docActions = await mutation(ref, async (paths) => {
    const performed = [];
    const quarantined = await quarantineTail(paths.activity, stamp, activityShaped);
    if (quarantined) performed.push(quarantined);
    const records = await anchorRecords(paths, await activityRecords(paths.activity));
    const head = chainHead(records);
    const expected = head ? head.result_sha : sha256(await boundedRead(ref.seedPath, MAX_MARKDOWN_BYTES));
    const current = await projectionBytes(ref, paths);
    if (sha256(current) === expected) return performed;
    if (!head) {
      performed.push("refused: the projection diverges with no ledgered revision");
      return performed;
    }
    let revision;
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
    repaired: actions.some((action) => !action.startsWith("refused:"))
  };
}
async function compactDocument({
  dataDir,
  docId,
  seedPath,
  actor,
  eventId,
  now
}) {
  const ref = { dataDir, docId, seedPath };
  return mutation(ref, async (paths) => {
    const current = await verifiedProjection(
      ref,
      paths,
      await anchorRecords(paths, await activityRecords(paths.activity))
    );
    return rotate({
      actor: actor ?? SYSTEM_ACTOR,
      current,
      docId,
      eventId,
      now,
      paths
    });
  });
}
async function gcRevisions(ref, { apply = false } = {}) {
  const survey = async (paths) => {
    const referenced = /* @__PURE__ */ new Set();
    for (const event of await activityRecords(paths.activity)) {
      referenced.add(event.base_sha);
      referenced.add(event.result_sha);
    }
    referenced.add(sha256(await projectionBytes(ref, paths)));
    const unreferenced = [];
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
    return { ...await survey(docPaths(ref)), deleted: [] };
  }
  return mutation(ref, async (paths) => {
    const found = await survey(paths);
    for (const sha of found.unreferenced) {
      await rm(revisionPath(paths, sha), { force: true });
    }
    return { ...found, deleted: found.unreferenced };
  });
}
function validSessionEvent(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const event = value;
  if (event.event !== "session_issued" && event.event !== "session_revoked" || typeof event.session_hash !== "string" || typeof event.ts !== "string") {
    return false;
  }
  if (event.event === "session_revoked") return true;
  if (typeof event.expires !== "string" || typeof event.invite_hash !== "string" || !Array.isArray(event.docs) || !event.docs.every((doc) => typeof doc === "string") || !event.actor || typeof event.actor !== "object" || Array.isArray(event.actor)) {
    return false;
  }
  const actor = event.actor;
  return typeof actor.id === "string" && (actor.kind === "human" || actor.kind === "agent") && (actor.role === "owner" || actor.role === "editor" || actor.role === "viewer");
}
function sessionMutation(sessionsPath, operation) {
  return serialized(sessionsPath, () => locked(dirname(sessionsPath), operation));
}

// src/cli.ts
var HELP = `workpad <command> [flags]

Commands:
  get       Print the current document
  save      Save markdown (from --file or stdin)
  note      Append a note (from a positional argument or stdin)
  log       Print activity events, newest first
  docs      List documents in --dir
  fsck      Check a document's provenance for integrity
  repair    Repair a document's recoverable issues
  compact   Checkpoint and rotate the activity ledger
  gc        Garbage-collect unreferenced revisions

Common flags:
  --dir <path>   Data directory (env WORKPAD_DIR)
  --doc <id>     Document id (default: ${DEFAULT_DOC_ID})
  --seed <path>  Seed file path (env WORKPAD_SEED_PATH)
  --as <actor>   Actor as "id[:kind[:role]]" (env WORKPAD_ACTOR, default cli:agent:editor)
  --json         Machine-readable output
  -h, --help     Show this help

save/note flags:
  --file <path>  Read markdown from this file (save only; default stdin)
  --base <sha>   Save or note against this base sha
  --latest       Save or note against the current sha
  --note <text>  Note text to attach to a save

log flags:
  --limit <n>    Max events to print (default 20)

gc flags:
  --apply        Delete unreferenced revisions (default is a dry run)
`;
var COMMANDS = /* @__PURE__ */ new Set([
  "compact",
  "docs",
  "fsck",
  "gc",
  "get",
  "log",
  "note",
  "repair",
  "save"
]);
var OPTIONS = {
  apply: { type: "boolean" },
  as: { type: "string" },
  base: { type: "string" },
  dir: { type: "string" },
  doc: { type: "string" },
  file: { type: "string" },
  help: { short: "h", type: "boolean" },
  json: { type: "boolean" },
  latest: { type: "boolean" },
  limit: { type: "string" },
  note: { type: "string" },
  seed: { type: "string" }
};
function defaultIO() {
  return { stderr: process.stderr, stdin: process.stdin, stdout: process.stdout };
}
async function readStdin(stream) {
  const chunks = [];
  for await (const chunk of stream) {
    chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk));
  }
  return Buffer.concat(chunks).toString("utf8");
}
function resolveDir(value) {
  const dir = value ?? process.env.WORKPAD_DIR;
  if (!dir) throw new Error("A data directory is required: pass --dir or set WORKPAD_DIR.");
  return dir;
}
function resolveSeed(value) {
  const seed = value ?? process.env.WORKPAD_SEED_PATH;
  if (!seed) {
    throw new Error("A seed path is required: pass --seed or set WORKPAD_SEED_PATH.");
  }
  return seed;
}
function parseActor(spec, docId) {
  const [id, kind = "agent", role = "editor"] = spec.split(":");
  if (!id) throw new Error("Actor id is required.");
  if (kind !== "human" && kind !== "agent") {
    throw new Error(`Invalid actor kind: ${kind} (expected human or agent)`);
  }
  if (role !== "owner" && role !== "editor" && role !== "viewer") {
    throw new Error(`Invalid actor role: ${role} (expected owner, editor, or viewer)`);
  }
  return { canEdit: role !== "viewer", docs: /* @__PURE__ */ new Set([docId]), id, kind, role };
}
async function resolveBaseSha(ref, flags) {
  if (flags.latest) return (await loadDocument(ref)).sha;
  if (flags.base) return flags.base;
  throw new Error("A base is required: pass --base <sha> or --latest.");
}
function writeConflict(io, json, error) {
  if (json) {
    io.stderr.write(`${JSON.stringify({ current_sha: error.currentSha, error: "conflict" })}
`);
  } else {
    io.stderr.write(`conflict: the workpad changed, current sha is ${error.currentSha}
`);
  }
  return 3;
}
async function cmdGet(ref, json, io) {
  const state = await loadDocument(ref);
  if (json) {
    io.stdout.write(
      `${JSON.stringify({ doc_id: state.doc_id, markdown: state.markdown, sha: state.sha })}
`
    );
  } else {
    io.stderr.write(`# ${state.doc_id} @ ${state.sha}
`);
    io.stdout.write(state.markdown);
  }
  return 0;
}
async function cmdSave(ref, actor, flags, json, io) {
  if (!actor.canEdit) {
    io.stderr.write(`Actor role '${actor.role}' cannot save.
`);
    return 1;
  }
  const markdown = flags.file ? await readFile2(flags.file, "utf8") : await readStdin(io.stdin);
  const baseSha = await resolveBaseSha(ref, flags);
  try {
    const result = await saveDocument({
      ...ref,
      actor,
      baseSha,
      markdown,
      note: flags.note ?? ""
    });
    if (json) {
      io.stdout.write(
        `${JSON.stringify({ merged: result.merged, saved: result.saved, sha: result.sha })}
`
      );
    } else {
      io.stdout.write(
        `saved ${result.sha}${result.merged ? " (merged with concurrent changes)" : ""}
`
      );
    }
    return 0;
  } catch (error) {
    if (error instanceof ConflictError) return writeConflict(io, json, error);
    throw error;
  }
}
async function cmdNote(ref, actor, flags, positionalText, json, io) {
  if (!actor.canEdit) {
    io.stderr.write(`Actor role '${actor.role}' cannot note.
`);
    return 1;
  }
  const note = positionalText ?? await readStdin(io.stdin);
  const baseSha = await resolveBaseSha(ref, flags);
  try {
    const result = await appendNote({ ...ref, actor, baseSha, note });
    if (json) {
      io.stdout.write(`${JSON.stringify({ noted: true, sha: result.sha })}
`);
    } else {
      io.stdout.write(`noted ${result.sha}
`);
    }
    return 0;
  } catch (error) {
    if (error instanceof ConflictError) return writeConflict(io, json, error);
    throw error;
  }
}
function logLine(event) {
  const base8 = event.base_sha.slice(0, 8);
  const result8 = event.result_sha.slice(0, 8);
  const note = event.note.slice(0, 80);
  return `${event.ts}  ${event.actor.id} (${event.actor.kind})  ${event.verb}  ${base8}\u2192${result8}  ${note}`;
}
async function cmdLog(ref, limit, json, io) {
  const state = await loadDocument(ref);
  const events = state.activity.slice(0, limit);
  if (json) {
    for (const event of events) io.stdout.write(`${JSON.stringify(event)}
`);
  } else {
    for (const event of events) io.stdout.write(`${logLine(event)}
`);
  }
  return 0;
}
async function cmdDocs(dataDir, json, io) {
  const docs = await listDocs(dataDir);
  if (json) {
    io.stdout.write(`${JSON.stringify(docs)}
`);
  } else {
    for (const doc of docs) io.stdout.write(`${doc}
`);
  }
  return 0;
}
async function cmdFsck(ref, json, io) {
  const report = await fsckDocument(ref);
  if (json) {
    io.stdout.write(`${JSON.stringify(report)}
`);
  } else {
    io.stdout.write(report.ok ? "ok\n" : "not ok\n");
    for (const issue of report.issues) io.stdout.write(`- ${issue}
`);
  }
  return report.ok ? 0 : 1;
}
async function cmdRepair(ref, json, io) {
  const report = await repairDocument(ref);
  if (json) {
    io.stdout.write(`${JSON.stringify(report)}
`);
  } else {
    io.stdout.write(`repaired: ${report.repaired}
`);
    for (const action of report.actions) io.stdout.write(`- ${action}
`);
  }
  return 0;
}
async function cmdCompact(ref, actor, json, io) {
  const result = await compactDocument({ ...ref, actor });
  if (json) {
    io.stdout.write(`${JSON.stringify(result)}
`);
  } else {
    io.stdout.write(
      `checkpoint ${result.event.result_sha} (archived: ${result.archive ?? "none"})
`
    );
  }
  return 0;
}
async function cmdGc(ref, apply, json, io) {
  const result = await gcRevisions(ref, { apply });
  if (json) {
    io.stdout.write(`${JSON.stringify(result)}
`);
    return 0;
  }
  if (apply) {
    if (result.deleted.length === 0) {
      io.stdout.write("no revisions deleted\n");
    } else {
      io.stdout.write("deleted revisions:\n");
      for (const sha of result.deleted) io.stdout.write(`- ${sha}
`);
    }
  } else if (result.unreferenced.length === 0) {
    io.stdout.write("no unreferenced revisions\n");
  } else {
    io.stdout.write("unreferenced revisions:\n");
    for (const sha of result.unreferenced) io.stdout.write(`- ${sha}
`);
  }
  return 0;
}
async function main(argv, io = {}) {
  const streams = { ...defaultIO(), ...io };
  let values;
  let positionals;
  try {
    ({ positionals, values } = parseArgs({ allowPositionals: true, args: argv, options: OPTIONS, strict: true }));
  } catch (error) {
    streams.stderr.write(`${error.message}
`);
    return 1;
  }
  if (values.help) {
    streams.stdout.write(HELP);
    return 0;
  }
  const [command, ...rest] = positionals;
  if (!command) {
    streams.stderr.write(HELP);
    return 1;
  }
  if (!COMMANDS.has(command)) {
    streams.stderr.write(`Unknown command: ${command}

${HELP}`);
    return 1;
  }
  const json = Boolean(values.json);
  const docId = values.doc ?? DEFAULT_DOC_ID;
  try {
    if (command === "docs") {
      return await cmdDocs(resolveDir(values.dir), json, streams);
    }
    const ref = {
      dataDir: resolveDir(values.dir),
      docId,
      seedPath: resolveSeed(values.seed)
    };
    const actor = parseActor(
      values.as ?? process.env.WORKPAD_ACTOR ?? "cli:agent:editor",
      docId
    );
    switch (command) {
      case "get":
        return await cmdGet(ref, json, streams);
      case "save":
        return await cmdSave(
          ref,
          actor,
          {
            base: values.base,
            file: values.file,
            latest: Boolean(values.latest),
            note: values.note
          },
          json,
          streams
        );
      case "note":
        return await cmdNote(
          ref,
          actor,
          { base: values.base, latest: Boolean(values.latest) },
          rest.length > 0 ? rest.join(" ") : void 0,
          json,
          streams
        );
      case "log":
        return await cmdLog(ref, Number.parseInt(values.limit ?? "20", 10), json, streams);
      case "fsck":
        return await cmdFsck(ref, json, streams);
      case "repair":
        return await cmdRepair(ref, json, streams);
      case "compact":
        return await cmdCompact(ref, actor, json, streams);
      case "gc":
        return await cmdGc(ref, Boolean(values.apply), json, streams);
      default:
        streams.stderr.write(`Unknown command: ${command}

${HELP}`);
        return 1;
    }
  } catch (error) {
    streams.stderr.write(`${error.message}
`);
    return 1;
  }
}
function isMain() {
  return Boolean(process.argv[1]) && import.meta.url === pathToFileURL(process.argv[1]).href;
}
if (isMain()) {
  process.exitCode = await main(process.argv.slice(2));
}
export {
  main
};
