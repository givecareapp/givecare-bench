import assert from "node:assert/strict";
import { mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { Readable } from "node:stream";
import test from "node:test";

import { main, type CliIO } from "./cli.ts";

const SEED = "# Shared workpad\n\nHumans and agents think here together.\n";

async function fixture(t: test.TestContext) {
  const root = await mkdtemp(join(tmpdir(), "workpad-cli-"));
  const dataDir = join(root, "data");
  const seedPath = join(root, "seed.md");
  await writeFile(seedPath, SEED, "utf8");
  t.after(() => rm(root, { recursive: true, force: true }));
  return { dataDir, root, seedPath };
}

function sink() {
  const lines: string[] = [];
  return { lines, write: (chunk: string) => lines.push(chunk) };
}

function io(overrides: Partial<CliIO> = {}): CliIO & { stdout: ReturnType<typeof sink>; stderr: ReturnType<typeof sink> } {
  return {
    stderr: sink(),
    stdin: Readable.from([]),
    stdout: sink(),
    ...overrides,
  } as CliIO & { stdout: ReturnType<typeof sink>; stderr: ReturnType<typeof sink> };
}

function baseArgs(paths: { dataDir: string; seedPath: string }): string[] {
  return ["--dir", paths.dataDir, "--seed", paths.seedPath];
}

test("get round-trips the seeded document", async (t) => {
  const paths = await fixture(t);
  const streams = io();

  const code = await main(["get", ...baseArgs(paths)], streams);

  assert.equal(code, 0);
  assert.equal(streams.stdout.lines.join(""), SEED);
  assert.match(streams.stderr.lines.join(""), /^# shared-workpad @ [0-9a-f]{64}\n$/);
});

test("get --json prints doc_id, sha, and markdown", async (t) => {
  const paths = await fixture(t);
  const streams = io();

  const code = await main(["get", "--json", ...baseArgs(paths)], streams);

  assert.equal(code, 0);
  const parsed = JSON.parse(streams.stdout.lines.join(""));
  assert.equal(parsed.doc_id, "shared-workpad");
  assert.equal(parsed.markdown, SEED);
  assert.match(parsed.sha, /^[0-9a-f]{64}$/);
});

test("save --latest writes markdown and reports the new sha", async (t) => {
  const paths = await fixture(t);
  const file = join(paths.root, "revised.md");
  const revised = `${SEED}\n## Decision\n\nShip it.\n`;
  await writeFile(file, revised, "utf8");
  const streams = io();

  const code = await main(
    ["save", "--latest", "--file", file, "--note", "shipped", "--json", ...baseArgs(paths)],
    streams,
  );

  assert.equal(code, 0);
  const result = JSON.parse(streams.stdout.lines.join(""));
  assert.equal(result.saved, true);
  assert.equal(result.merged, false);

  const after = io();
  await main(["get", "--json", ...baseArgs(paths)], after);
  assert.equal(JSON.parse(after.stdout.lines.join("")).markdown, revised);
});

test("save --base with a stale sha auto-merges non-overlapping edits", async (t) => {
  const paths = await fixture(t);
  const getState = io();
  await main(["get", "--json", ...baseArgs(paths)], getState);
  const staleSha = JSON.parse(getState.stdout.lines.join("")).sha as string;

  const first = join(paths.root, "first.md");
  await writeFile(first, SEED.replace("# Shared workpad", "# Shared workpad (v2)"), "utf8");
  await main(["save", "--base", staleSha, "--file", first, ...baseArgs(paths)], io());

  const second = join(paths.root, "second.md");
  await writeFile(second, SEED.replace("think here together.", "think here together, always."), "utf8");
  const streams = io();
  const code = await main(
    ["save", "--base", staleSha, "--file", second, "--json", ...baseArgs(paths)],
    streams,
  );

  assert.equal(code, 0);
  const result = JSON.parse(streams.stdout.lines.join(""));
  assert.equal(result.saved, true);
  assert.equal(result.merged, true);
});

test("save --base with a genuine conflict exits 3", async (t) => {
  const paths = await fixture(t);
  const getState = io();
  await main(["get", "--json", ...baseArgs(paths)], getState);
  const staleSha = JSON.parse(getState.stdout.lines.join("")).sha as string;

  const first = join(paths.root, "first.md");
  await writeFile(first, "Completely different content, first writer.\n", "utf8");
  await main(["save", "--base", staleSha, "--file", first, ...baseArgs(paths)], io());

  const second = join(paths.root, "second.md");
  await writeFile(second, "Completely different content, second writer.\n", "utf8");
  const streams = io();
  const code = await main(
    ["save", "--base", staleSha, "--file", second, "--json", ...baseArgs(paths)],
    streams,
  );

  assert.equal(code, 3);
  const error = JSON.parse(streams.stderr.lines.join(""));
  assert.equal(error.error, "conflict");
  assert.match(error.current_sha, /^[0-9a-f]{64}$/);
});

test("a viewer actor is rejected on write", async (t) => {
  const paths = await fixture(t);
  const file = join(paths.root, "revised.md");
  await writeFile(file, "New content.\n", "utf8");
  const streams = io();

  const code = await main(
    ["save", "--latest", "--file", file, "--as", "reader:human:viewer", ...baseArgs(paths)],
    streams,
  );

  assert.equal(code, 1);
  assert.match(streams.stderr.lines.join(""), /viewer/);
});

test("note appends without changing the document, and log shows it", async (t) => {
  const paths = await fixture(t);
  const streams = io();

  const code = await main(
    ["note", "--latest", "--as", "reviewer:human:editor", "Looks good to me.", ...baseArgs(paths)],
    streams,
  );
  assert.equal(code, 0);
  assert.match(streams.stdout.lines.join(""), /^noted [0-9a-f]{64}\n$/);

  const logStreams = io();
  const logCode = await main(["log", "--json", ...baseArgs(paths)], logStreams);
  assert.equal(logCode, 0);
  const events = logStreams.stdout.lines.map((line) => JSON.parse(line));
  assert.equal(events.length, 1);
  assert.equal(events[0].verb, "noted");
  assert.equal(events[0].actor.id, "reviewer");
  assert.equal(events[0].note, "Looks good to me.");
});

test("docs lists documents present in the data directory", async (t) => {
  const paths = await fixture(t);
  await main(["note", "--latest", "note one", ...baseArgs(paths)], io());
  const streams = io();

  const code = await main(["docs", "--dir", paths.dataDir], streams);

  assert.equal(code, 0);
  assert.deepEqual(streams.stdout.lines, ["shared-workpad\n"]);
});

test("fsck reports ok on a healthy document", async (t) => {
  const paths = await fixture(t);
  await main(["note", "--latest", "hello", ...baseArgs(paths)], io());
  const streams = io();

  const code = await main(["fsck", "--json", ...baseArgs(paths)], streams);

  assert.equal(code, 0);
  const report = JSON.parse(streams.stdout.lines.join(""));
  assert.equal(report.ok, true);
  assert.deepEqual(report.issues, []);
});

test("gc dry run lists nothing unreferenced after a fresh save", async (t) => {
  const paths = await fixture(t);
  const file = join(paths.root, "revised.md");
  await writeFile(file, `${SEED}\nMore.\n`, "utf8");
  await main(["save", "--latest", "--file", file, ...baseArgs(paths)], io());
  const streams = io();

  const code = await main(["gc", "--json", ...baseArgs(paths)], streams);

  assert.equal(code, 0);
  const result = JSON.parse(streams.stdout.lines.join(""));
  assert.deepEqual(result.unreferenced, []);
  assert.deepEqual(result.deleted, []);
});
