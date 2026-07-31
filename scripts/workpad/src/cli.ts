import { readFile } from "node:fs/promises";
import { parseArgs } from "node:util";
import { pathToFileURL } from "node:url";

import {
  ConflictError,
  DEFAULT_DOC_ID,
  appendNote,
  compactDocument,
  fsckDocument,
  gcRevisions,
  listDocs,
  loadDocument,
  repairDocument,
  saveDocument,
  type Actor,
  type ActivityEvent,
  type DocRef,
} from "./store.ts";

export type CliIO = {
  stdin: NodeJS.ReadableStream;
  stdout: { write(chunk: string): unknown };
  stderr: { write(chunk: string): unknown };
};

const HELP = `workpad <command> [flags]

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

const COMMANDS = new Set([
  "compact",
  "docs",
  "fsck",
  "gc",
  "get",
  "log",
  "note",
  "repair",
  "save",
]);

const OPTIONS = {
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
  seed: { type: "string" },
} as const;

function defaultIO(): CliIO {
  return { stderr: process.stderr, stdin: process.stdin, stdout: process.stdout };
}

async function readStdin(stream: NodeJS.ReadableStream): Promise<string> {
  const chunks: Buffer[] = [];
  for await (const chunk of stream) {
    chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk));
  }
  return Buffer.concat(chunks).toString("utf8");
}

function resolveDir(value: string | undefined): string {
  const dir = value ?? process.env.WORKPAD_DIR;
  if (!dir) throw new Error("A data directory is required: pass --dir or set WORKPAD_DIR.");
  return dir;
}

function resolveSeed(value: string | undefined): string {
  const seed = value ?? process.env.WORKPAD_SEED_PATH;
  if (!seed) {
    throw new Error("A seed path is required: pass --seed or set WORKPAD_SEED_PATH.");
  }
  return seed;
}

function parseActor(spec: string, docId: string): Actor {
  const [id, kind = "agent", role = "editor"] = spec.split(":");
  if (!id) throw new Error("Actor id is required.");
  if (kind !== "human" && kind !== "agent") {
    throw new Error(`Invalid actor kind: ${kind} (expected human or agent)`);
  }
  if (role !== "owner" && role !== "editor" && role !== "viewer") {
    throw new Error(`Invalid actor role: ${role} (expected owner, editor, or viewer)`);
  }
  return { canEdit: role !== "viewer", docs: new Set([docId]), id, kind, role };
}

async function resolveBaseSha(
  ref: DocRef,
  flags: { base?: string; latest?: boolean },
): Promise<string> {
  if (flags.latest) return (await loadDocument(ref)).sha;
  if (flags.base) return flags.base;
  throw new Error("A base is required: pass --base <sha> or --latest.");
}

function writeConflict(io: CliIO, json: boolean, error: ConflictError): number {
  if (json) {
    io.stderr.write(`${JSON.stringify({ current_sha: error.currentSha, error: "conflict" })}\n`);
  } else {
    io.stderr.write(`conflict: the workpad changed, current sha is ${error.currentSha}\n`);
  }
  return 3;
}

async function cmdGet(ref: DocRef, json: boolean, io: CliIO): Promise<number> {
  const state = await loadDocument(ref);
  if (json) {
    io.stdout.write(
      `${JSON.stringify({ doc_id: state.doc_id, markdown: state.markdown, sha: state.sha })}\n`,
    );
  } else {
    io.stderr.write(`# ${state.doc_id} @ ${state.sha}\n`);
    io.stdout.write(state.markdown);
  }
  return 0;
}

async function cmdSave(
  ref: DocRef,
  actor: Actor,
  flags: { base?: string; file?: string; latest?: boolean; note?: string },
  json: boolean,
  io: CliIO,
): Promise<number> {
  if (!actor.canEdit) {
    io.stderr.write(`Actor role '${actor.role}' cannot save.\n`);
    return 1;
  }
  const markdown = flags.file ? await readFile(flags.file, "utf8") : await readStdin(io.stdin);
  const baseSha = await resolveBaseSha(ref, flags);
  try {
    const result = await saveDocument({
      ...ref,
      actor,
      baseSha,
      markdown,
      note: flags.note ?? "",
    });
    if (json) {
      io.stdout.write(
        `${JSON.stringify({ merged: result.merged, saved: result.saved, sha: result.sha })}\n`,
      );
    } else {
      io.stdout.write(
        `saved ${result.sha}${result.merged ? " (merged with concurrent changes)" : ""}\n`,
      );
    }
    return 0;
  } catch (error) {
    if (error instanceof ConflictError) return writeConflict(io, json, error);
    throw error;
  }
}

async function cmdNote(
  ref: DocRef,
  actor: Actor,
  flags: { base?: string; latest?: boolean },
  positionalText: string | undefined,
  json: boolean,
  io: CliIO,
): Promise<number> {
  if (!actor.canEdit) {
    io.stderr.write(`Actor role '${actor.role}' cannot note.\n`);
    return 1;
  }
  const note = positionalText ?? (await readStdin(io.stdin));
  const baseSha = await resolveBaseSha(ref, flags);
  try {
    const result = await appendNote({ ...ref, actor, baseSha, note });
    if (json) {
      io.stdout.write(`${JSON.stringify({ noted: true, sha: result.sha })}\n`);
    } else {
      io.stdout.write(`noted ${result.sha}\n`);
    }
    return 0;
  } catch (error) {
    if (error instanceof ConflictError) return writeConflict(io, json, error);
    throw error;
  }
}

function logLine(event: ActivityEvent): string {
  const base8 = event.base_sha.slice(0, 8);
  const result8 = event.result_sha.slice(0, 8);
  const note = event.note.slice(0, 80);
  return `${event.ts}  ${event.actor.id} (${event.actor.kind})  ${event.verb}  ${base8}→${result8}  ${note}`;
}

async function cmdLog(ref: DocRef, limit: number, json: boolean, io: CliIO): Promise<number> {
  const state = await loadDocument(ref);
  const events = state.activity.slice(0, limit);
  if (json) {
    for (const event of events) io.stdout.write(`${JSON.stringify(event)}\n`);
  } else {
    for (const event of events) io.stdout.write(`${logLine(event)}\n`);
  }
  return 0;
}

async function cmdDocs(dataDir: string, json: boolean, io: CliIO): Promise<number> {
  const docs = await listDocs(dataDir);
  if (json) {
    io.stdout.write(`${JSON.stringify(docs)}\n`);
  } else {
    for (const doc of docs) io.stdout.write(`${doc}\n`);
  }
  return 0;
}

async function cmdFsck(ref: DocRef, json: boolean, io: CliIO): Promise<number> {
  const report = await fsckDocument(ref);
  if (json) {
    io.stdout.write(`${JSON.stringify(report)}\n`);
  } else {
    io.stdout.write(report.ok ? "ok\n" : "not ok\n");
    for (const issue of report.issues) io.stdout.write(`- ${issue}\n`);
  }
  return report.ok ? 0 : 1;
}

async function cmdRepair(ref: DocRef, json: boolean, io: CliIO): Promise<number> {
  const report = await repairDocument(ref);
  if (json) {
    io.stdout.write(`${JSON.stringify(report)}\n`);
  } else {
    io.stdout.write(`repaired: ${report.repaired}\n`);
    for (const action of report.actions) io.stdout.write(`- ${action}\n`);
  }
  return 0;
}

async function cmdCompact(ref: DocRef, actor: Actor, json: boolean, io: CliIO): Promise<number> {
  const result = await compactDocument({ ...ref, actor });
  if (json) {
    io.stdout.write(`${JSON.stringify(result)}\n`);
  } else {
    io.stdout.write(
      `checkpoint ${result.event.result_sha} (archived: ${result.archive ?? "none"})\n`,
    );
  }
  return 0;
}

async function cmdGc(ref: DocRef, apply: boolean, json: boolean, io: CliIO): Promise<number> {
  const result = await gcRevisions(ref, { apply });
  if (json) {
    io.stdout.write(`${JSON.stringify(result)}\n`);
    return 0;
  }
  if (apply) {
    if (result.deleted.length === 0) {
      io.stdout.write("no revisions deleted\n");
    } else {
      io.stdout.write("deleted revisions:\n");
      for (const sha of result.deleted) io.stdout.write(`- ${sha}\n`);
    }
  } else if (result.unreferenced.length === 0) {
    io.stdout.write("no unreferenced revisions\n");
  } else {
    io.stdout.write("unreferenced revisions:\n");
    for (const sha of result.unreferenced) io.stdout.write(`- ${sha}\n`);
  }
  return 0;
}

export async function main(argv: string[], io: Partial<CliIO> = {}): Promise<number> {
  const streams: CliIO = { ...defaultIO(), ...io };

  let values: Partial<Record<keyof typeof OPTIONS, string | boolean>>;
  let positionals: string[];
  try {
    ({ positionals, values } = parseArgs({ allowPositionals: true, args: argv, options: OPTIONS, strict: true }));
  } catch (error) {
    streams.stderr.write(`${(error as Error).message}\n`);
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
    streams.stderr.write(`Unknown command: ${command}\n\n${HELP}`);
    return 1;
  }

  const json = Boolean(values.json);
  const docId = (values.doc as string | undefined) ?? DEFAULT_DOC_ID;

  try {
    if (command === "docs") {
      return await cmdDocs(resolveDir(values.dir as string | undefined), json, streams);
    }

    const ref: DocRef = {
      dataDir: resolveDir(values.dir as string | undefined),
      docId,
      seedPath: resolveSeed(values.seed as string | undefined),
    };
    const actor = parseActor(
      (values.as as string | undefined) ?? process.env.WORKPAD_ACTOR ?? "cli:agent:editor",
      docId,
    );

    switch (command) {
      case "get":
        return await cmdGet(ref, json, streams);
      case "save":
        return await cmdSave(
          ref,
          actor,
          {
            base: values.base as string | undefined,
            file: values.file as string | undefined,
            latest: Boolean(values.latest),
            note: values.note as string | undefined,
          },
          json,
          streams,
        );
      case "note":
        return await cmdNote(
          ref,
          actor,
          { base: values.base as string | undefined, latest: Boolean(values.latest) },
          rest.length > 0 ? rest.join(" ") : undefined,
          json,
          streams,
        );
      case "log":
        return await cmdLog(ref, Number.parseInt((values.limit as string | undefined) ?? "20", 10), json, streams);
      case "fsck":
        return await cmdFsck(ref, json, streams);
      case "repair":
        return await cmdRepair(ref, json, streams);
      case "compact":
        return await cmdCompact(ref, actor, json, streams);
      case "gc":
        return await cmdGc(ref, Boolean(values.apply), json, streams);
      default:
        streams.stderr.write(`Unknown command: ${command}\n\n${HELP}`);
        return 1;
    }
  } catch (error) {
    streams.stderr.write(`${(error as Error).message}\n`);
    return 1;
  }
}

function isMain(): boolean {
  return Boolean(process.argv[1]) && import.meta.url === pathToFileURL(process.argv[1]).href;
}

if (isMain()) {
  process.exitCode = await main(process.argv.slice(2));
}
