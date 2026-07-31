import assert from "node:assert/strict";
import {
  appendFile,
  chmod,
  lstat,
  mkdir,
  mkdtemp,
  readFile,
  readdir,
  rm,
  symlink,
  writeFile,
} from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import {
  ConflictError,
  DEFAULT_DOC_ID,
  appendNote,
  compactDocument,
  fsckDocument,
  gcRevisions,
  listDocs,
  loadDocument,
  redeemInvite,
  repairDocument,
  resolveSession,
  revokeSession,
  saveDocument,
  sha256,
  type ActivityEvent,
  type Actor,
} from "./store.ts";

const SEED = "# Shared workpad\n\nHumans and agents think here together.\n";
const OWNER: Actor = {
  canEdit: true,
  docs: new Set([DEFAULT_DOC_ID]),
  id: "ali",
  kind: "human",
  role: "owner",
};

async function fixture(t: test.TestContext, docId = DEFAULT_DOC_ID) {
  const root = await mkdtemp(join(tmpdir(), "workpad-store-"));
  const dataDir = join(root, "data");
  const seedPath = join(root, "seed.md");
  const sessionsPath = join(root, "sessions.jsonl");
  const tokensPath = join(root, "tokens.txt");
  await writeFile(seedPath, SEED, "utf8");
  t.after(() => rm(root, { recursive: true, force: true }));
  return { dataDir, docId, root, seedPath, sessionsPath, tokensPath };
}

function docFile(paths: { dataDir: string; docId: string }, ...parts: string[]): string {
  return join(paths.dataDir, paths.docId, ...parts);
}

function ledgerEvents(content: string): ActivityEvent[] {
  return content
    .split("\n")
    .filter(Boolean)
    .map((line) => JSON.parse(line) as ActivityEvent);
}

test("loads the exact seed bytes and revision", async (t) => {
  const paths = await fixture(t);

  const state = await loadDocument(paths);

  assert.equal(state.markdown, SEED);
  assert.equal(state.sha, sha256(SEED));
  assert.equal(state.doc_id, DEFAULT_DOC_ID);
  assert.deepEqual(state.activity, []);
});

test("save writes the readable projection, snapshots, and actor provenance", async (t) => {
  const paths = await fixture(t);
  const before = await loadDocument(paths);
  const revised = `${SEED}\n## Decision\n\nUse one codebase with two isolated instances.\n`;

  const saved = await saveDocument({
    ...paths,
    actor: OWNER,
    baseSha: before.sha,
    markdown: revised,
    note: "Captured the deployment boundary.",
    now: () => "2026-07-30T20:00:00.000Z",
    eventId: () => "evt:test:save",
  });

  assert.equal(saved.sha, sha256(revised));
  assert.equal(saved.merged, false);
  assert.equal(saved.markdown, undefined);
  assert.equal(await readFile(docFile(paths, "doc.md"), "utf8"), revised);
  assert.equal(
    await readFile(docFile(paths, "revisions", `${saved.sha}.md`), "utf8"),
    revised,
  );
  assert.deepEqual(saved.event, {
    actor: { id: "ali", kind: "human", role: "owner" },
    base_sha: before.sha,
    doc_id: DEFAULT_DOC_ID,
    event_id: "evt:test:save",
    note: "Captured the deployment boundary.",
    result_sha: saved.sha,
    source_refs: [],
    ts: "2026-07-30T20:00:00.000Z",
    verb: "edited",
  });
});

test("an invalid document id is refused before any filesystem work", async (t) => {
  const paths = await fixture(t, "../escape");

  await assert.rejects(loadDocument(paths), RangeError);
  await assert.rejects(loadDocument({ ...paths, docId: "Shared" }), RangeError);
  await assert.rejects(loadDocument({ ...paths, docId: "" }), RangeError);
});

test("documents in one data directory stay isolated", async (t) => {
  const base = await fixture(t);
  const notes = { ...base, docId: "field-notes" };
  const shared = await loadDocument(base);

  const savedShared = await saveDocument({
    ...base,
    actor: OWNER,
    baseSha: shared.sha,
    markdown: `${SEED}\nShared only.\n`,
    note: "",
  });
  const savedNotes = await saveDocument({
    ...notes,
    actor: OWNER,
    baseSha: (await loadDocument(notes)).sha,
    markdown: `${SEED}\nNotes only.\n`,
    note: "",
  });

  assert.notEqual(savedShared.sha, savedNotes.sha);
  assert.equal((await loadDocument(base)).markdown, `${SEED}\nShared only.\n`);
  assert.equal((await loadDocument(notes)).markdown, `${SEED}\nNotes only.\n`);
  assert.equal((await loadDocument(base)).activity.length, 1);
  assert.equal((await loadDocument(notes)).activity[0]?.doc_id, "field-notes");
  assert.deepEqual(await listDocs(base.dataDir), ["field-notes", DEFAULT_DOC_ID]);
  assert.deepEqual(await listDocs(join(base.root, "missing")), []);
});

test("the legacy single-document layout migrates on first access", async (t) => {
  const paths = await fixture(t);
  const revised = `${SEED}\nWritten before the multi-document layout.\n`;
  const event = {
    actor: { id: "ali", kind: "human", role: "owner" },
    base_sha: sha256(SEED),
    doc_id: DEFAULT_DOC_ID,
    event_id: "evt:legacy",
    note: "Legacy edit.",
    result_sha: sha256(revised),
    source_refs: [],
    ts: "2026-07-29T10:00:00.000Z",
    verb: "edited",
  };
  await mkdir(join(paths.dataDir, "revisions"), { recursive: true });
  await writeFile(join(paths.dataDir, `${DEFAULT_DOC_ID}.md`), revised, "utf8");
  await writeFile(
    join(paths.dataDir, "revisions", `${sha256(revised)}.md`),
    revised,
    "utf8",
  );
  await writeFile(
    join(paths.dataDir, `${DEFAULT_DOC_ID}.activity.jsonl`),
    `${JSON.stringify(event)}\n`,
    "utf8",
  );

  const state = await loadDocument(paths);

  assert.equal(state.markdown, revised);
  assert.equal(state.activity[0]?.event_id, "evt:legacy");
  assert.equal(await readFile(docFile(paths, "doc.md"), "utf8"), revised);
  assert.equal(
    await readFile(docFile(paths, "revisions", `${sha256(revised)}.md`), "utf8"),
    revised,
  );
  assert.deepEqual(await readdir(paths.dataDir), [DEFAULT_DOC_ID]);

  const again = await loadDocument(paths);
  assert.equal(again.markdown, revised);
});

test("a stale save merges cleanly when both editors changed different regions", async (t) => {
  const paths = await fixture(t);
  const before = await loadDocument(paths);
  const theirs = `> Context added by the stale editor.\n\n${SEED}`;
  const ours = `${SEED}\n## Decision\n\nShip the workpad.\n`;
  const first = await saveDocument({
    ...paths,
    actor: OWNER,
    baseSha: before.sha,
    markdown: ours,
    note: "",
  });

  const merged = await saveDocument({
    ...paths,
    actor: OWNER,
    baseSha: before.sha,
    markdown: theirs,
    note: "Merged from a stale base.",
    now: () => "2026-07-30T21:00:00.000Z",
    eventId: () => "evt:test:merge",
  });

  assert.equal(merged.merged, true);
  assert.equal(merged.saved, true);
  assert.equal(
    merged.markdown,
    `> Context added by the stale editor.\n\n${SEED}\n## Decision\n\nShip the workpad.\n`,
  );
  assert.equal(merged.sha, sha256(merged.markdown ?? ""));
  assert.equal(merged.event?.base_sha, first.sha);
  assert.equal(merged.event?.verb, "edited");
  assert.equal(await readFile(docFile(paths, "doc.md"), "utf8"), merged.markdown);
  assert.deepEqual(await fsckDocument(paths), { issues: [], ok: true });
});

test("a conflicting stale save changes neither the projection nor the ledger", async (t) => {
  const paths = await fixture(t);
  const before = await loadDocument(paths);
  const first = await saveDocument({
    ...paths,
    actor: OWNER,
    baseSha: before.sha,
    markdown: `${SEED}\nFirst.\n`,
    note: "",
  });
  const documentBefore = await readFile(docFile(paths, "doc.md"));
  const ledgerBefore = await readFile(docFile(paths, "activity.jsonl"));

  await assert.rejects(
    saveDocument({
      ...paths,
      actor: OWNER,
      baseSha: before.sha,
      markdown: `${SEED}\nStale.\n`,
      note: "",
    }),
    (error: unknown) =>
      error instanceof ConflictError && error.currentSha === first.sha,
  );

  assert.deepEqual(await readFile(docFile(paths, "doc.md")), documentBefore);
  assert.deepEqual(await readFile(docFile(paths, "activity.jsonl")), ledgerBefore);
});

test("a stale save without its base revision conflicts instead of guessing", async (t) => {
  const paths = await fixture(t);
  const before = await loadDocument(paths);
  const first = await saveDocument({
    ...paths,
    actor: OWNER,
    baseSha: before.sha,
    markdown: `${SEED}\nFirst.\n`,
    note: "",
  });

  await assert.rejects(
    saveDocument({
      ...paths,
      actor: OWNER,
      baseSha: sha256("a base this workpad never held"),
      markdown: `${SEED}\nUnrelated.\n`,
      note: "",
    }),
    (error: unknown) =>
      error instanceof ConflictError && error.currentSha === first.sha,
  );
  await assert.rejects(
    saveDocument({
      ...paths,
      actor: OWNER,
      baseSha: "not-a-sha",
      markdown: `${SEED}\nUnrelated.\n`,
      note: "",
    }),
    ConflictError,
  );

  await writeFile(docFile(paths, "revisions", `${before.sha}.md`), "Tampered.\n", "utf8");
  await assert.rejects(
    saveDocument({
      ...paths,
      actor: OWNER,
      baseSha: before.sha,
      markdown: `${SEED}\nMerged against a tampered base.\n`,
      note: "",
    }),
    /provenance hash/,
  );
  assert.equal(await readFile(docFile(paths, "doc.md"), "utf8"), `${SEED}\nFirst.\n`);
  assert.equal(first.sha, sha256(`${SEED}\nFirst.\n`));
});

test("a note keeps strict agreement and never merges", async (t) => {
  const paths = await fixture(t);
  const before = await loadDocument(paths);
  await saveDocument({
    ...paths,
    actor: OWNER,
    baseSha: before.sha,
    markdown: `${SEED}\nMoved on.\n`,
    note: "",
  });

  await assert.rejects(
    appendNote({ ...paths, actor: OWNER, baseSha: before.sha, note: "Stale note." }),
    ConflictError,
  );
});

test("a failed projection write is recovered from its durable provenance event", async (t) => {
  const paths = await fixture(t);
  const before = await loadDocument(paths);
  const revised = `${SEED}\nRecovered after interruption.\n`;
  await mkdir(docFile(paths, "doc.md"), { recursive: true });

  await assert.rejects(
    saveDocument({
      ...paths,
      actor: OWNER,
      baseSha: before.sha,
      markdown: revised,
      note: "This event must exist before the projection changes.",
      now: () => "2026-07-30T20:01:00.000Z",
      eventId: () => "evt:test:interrupted",
    }),
  );

  assert.deepEqual(
    ledgerEvents(await readFile(docFile(paths, "activity.jsonl"), "utf8")),
    [
      {
        actor: { id: "ali", kind: "human", role: "owner" },
        base_sha: before.sha,
        doc_id: DEFAULT_DOC_ID,
        event_id: "evt:test:interrupted",
        note: "This event must exist before the projection changes.",
        result_sha: sha256(revised),
        source_refs: [],
        ts: "2026-07-30T20:01:00.000Z",
        verb: "edited",
      },
    ],
  );

  await rm(docFile(paths, "doc.md"), { recursive: true });
  const recovered = await loadDocument(paths);

  assert.equal(recovered.markdown, revised);
  assert.equal(recovered.sha, sha256(revised));
  assert.equal(await readFile(docFile(paths, "doc.md"), "utf8"), revised);
});

test("an unledgered projection is refused rather than trusted", async (t) => {
  const paths = await fixture(t);
  const before = await loadDocument(paths);
  await saveDocument({
    ...paths,
    actor: OWNER,
    baseSha: before.sha,
    markdown: `${SEED}\nLedgered.\n`,
    note: "",
  });
  await writeFile(docFile(paths, "doc.md"), `${SEED}\nSmuggled in.\n`, "utf8");

  await assert.rejects(loadDocument(paths), /unledgered/i);
});

test("note adds reasoning without mutating document bytes", async (t) => {
  const paths = await fixture(t);
  const before = await loadDocument(paths);

  const result = await appendNote({
    ...paths,
    actor: OWNER,
    baseSha: before.sha,
    note: "Ask Helen to verify the handoff.",
    now: () => "2026-07-30T20:05:00.000Z",
    eventId: () => "evt:test:note",
  });
  const after = await loadDocument(paths);

  assert.equal(after.markdown, before.markdown);
  assert.equal(result.event.verb, "noted");
  assert.equal(result.event.base_sha, before.sha);
  assert.equal(result.event.result_sha, before.sha);
  assert.equal(after.activity[0]?.note, "Ask Helen to verify the handoff.");
});

test("activity ignores malformed lines and is newest first", async (t) => {
  const paths = await fixture(t);
  await mkdir(docFile(paths), { recursive: true });
  await writeFile(
    docFile(paths, "activity.jsonl"),
    [
      '{"event_id":"one","ts":"2026-07-30T01:00:00Z"}',
      "not-json",
      '{"event_id":"two","ts":"2026-07-30T02:00:00Z"}',
      "",
    ].join("\n"),
    "utf8",
  );

  const state = await loadDocument(paths);

  assert.deepEqual(
    state.activity.map((event) => event.event_id),
    ["two", "one"],
  );
});

test("a torn final ledger line never blocks the workpad", async (t) => {
  const paths = await fixture(t);
  const before = await loadDocument(paths);
  const revised = `${SEED}\nDurable.\n`;
  await saveDocument({
    ...paths,
    actor: OWNER,
    baseSha: before.sha,
    markdown: revised,
    note: "",
  });
  await appendFile(docFile(paths, "activity.jsonl"), '{"verb":"edi', "utf8");

  const state = await loadDocument(paths);

  assert.equal(state.markdown, revised);
  assert.equal(state.activity.length, 1);
});

test("an oversized ledger rotates into an archive with a checkpoint root", async (t) => {
  const paths = await fixture(t);
  const before = await loadDocument(paths);
  const first = await saveDocument({
    ...paths,
    actor: OWNER,
    baseSha: before.sha,
    markdown: `${SEED}\nFirst.\n`,
    note: "",
  });
  await appendFile(
    docFile(paths, "activity.jsonl"),
    `${JSON.stringify({
      actor: { id: "ali", kind: "human", role: "owner" },
      base_sha: first.sha,
      doc_id: DEFAULT_DOC_ID,
      event_id: "evt:filler",
      note: "x".repeat(1_100_000),
      result_sha: first.sha,
      source_refs: [],
      ts: "2026-07-30T20:10:00.000Z",
      verb: "noted",
    })}\n`,
    "utf8",
  );

  const second = await saveDocument({
    ...paths,
    actor: OWNER,
    baseSha: first.sha,
    markdown: `${SEED}\nFirst.\nSecond.\n`,
    note: "Rotated.",
  });

  const archived = ledgerEvents(
    await readFile(docFile(paths, "archive", "activity.1.jsonl"), "utf8"),
  );
  const active = ledgerEvents(await readFile(docFile(paths, "activity.jsonl"), "utf8"));
  assert.equal(archived.length, 2);
  assert.equal(active.length, 2);
  assert.deepEqual(active[0], {
    actor: { id: "workpad", kind: "agent", role: "owner" },
    base_sha: first.sha,
    doc_id: DEFAULT_DOC_ID,
    event_id: active[0]?.event_id,
    note: "",
    result_sha: first.sha,
    source_refs: [],
    ts: active[0]?.ts,
    verb: "checkpoint",
  });
  assert.equal(active[1]?.event_id, second.event?.event_id);

  const state = await loadDocument(paths);
  assert.equal(state.markdown, `${SEED}\nFirst.\nSecond.\n`);
  assert.deepEqual(
    state.activity.map((event) => event.verb),
    ["edited", "checkpoint"],
  );
  assert.deepEqual(await fsckDocument(paths), { issues: [], ok: true });
});

test("compaction forces a checkpoint and frees unreferenced revisions", async (t) => {
  const paths = await fixture(t);
  const before = await loadDocument(paths);
  const first = await saveDocument({
    ...paths,
    actor: OWNER,
    baseSha: before.sha,
    markdown: `${SEED}\nFirst.\n`,
    note: "",
  });
  const second = await saveDocument({
    ...paths,
    actor: OWNER,
    baseSha: first.sha,
    markdown: `${SEED}\nSecond.\n`,
    note: "",
  });

  const compacted = await compactDocument({ ...paths, now: () => "2026-07-30T22:00:00.000Z" });

  assert.equal(compacted.archive, docFile(paths, "archive", "activity.1.jsonl"));
  assert.equal(compacted.event.verb, "checkpoint");
  assert.equal(compacted.event.result_sha, second.sha);
  assert.equal(compacted.event.ts, "2026-07-30T22:00:00.000Z");

  const dry = await gcRevisions(paths, { apply: false });
  assert.equal(dry.referenced, 1);
  assert.deepEqual(dry.unreferenced.sort(), [before.sha, first.sha].sort());
  assert.deepEqual(dry.deleted, []);
  assert.equal(
    (await readdir(docFile(paths, "revisions"))).length,
    3,
    "a dry run deletes nothing",
  );

  const applied = await gcRevisions(paths, { apply: true });
  assert.deepEqual(applied.deleted.sort(), dry.unreferenced.sort());
  assert.deepEqual(await readdir(docFile(paths, "revisions")), [`${second.sha}.md`]);
  assert.equal((await loadDocument(paths)).markdown, `${SEED}\nSecond.\n`);
});

test("fsck reports a tampered revision and a diverged projection", async (t) => {
  const paths = await fixture(t);
  const before = await loadDocument(paths);
  const saved = await saveDocument({
    ...paths,
    actor: OWNER,
    baseSha: before.sha,
    markdown: `${SEED}\nAuthentic.\n`,
    note: "",
  });
  assert.deepEqual(await fsckDocument(paths), { issues: [], ok: true });

  await writeFile(
    docFile(paths, "revisions", `${saved.sha}.md`),
    `${SEED}\nTampered.\n`,
    "utf8",
  );

  const report = await fsckDocument(paths);
  assert.equal(report.ok, false);
  assert.equal(report.issues.length, 1);
  assert.match(report.issues[0], /revision does not match its provenance hash/);

  await writeFile(docFile(paths, "doc.md"), `${SEED}\nOut of band.\n`, "utf8");
  const diverged = await fsckDocument(paths);
  assert.equal(diverged.issues.length, 2);
  assert.match(diverged.issues[1], /projection does not match the replayed ledger state/);
});

test("repair quarantines a torn tail and rematerializes the projection", async (t) => {
  const paths = await fixture(t);
  const before = await loadDocument(paths);
  const revised = `${SEED}\nAuthoritative.\n`;
  await saveDocument({
    ...paths,
    actor: OWNER,
    baseSha: before.sha,
    markdown: revised,
    note: "",
  });
  await appendFile(docFile(paths, "activity.jsonl"), '{"verb":"edit', "utf8");
  await writeFile(docFile(paths, "doc.md"), "Overwritten out of band.\n", "utf8");

  const repair = await repairDocument(paths);

  assert.equal(repair.repaired, true);
  assert.equal(repair.actions.length, 2);
  assert.match(repair.actions[0], /quarantined a torn line to .*activity\.jsonl\.quarantine-/);
  assert.match(repair.actions[1], /rematerialized the projection/);
  const quarantine = (await readdir(docFile(paths))).find((name) =>
    name.startsWith("activity.jsonl.quarantine-"),
  );
  assert.ok(quarantine);
  assert.equal(await readFile(docFile(paths, quarantine), "utf8"), '{"verb":"edit');
  assert.equal(await readFile(docFile(paths, "doc.md"), "utf8"), revised);
  assert.deepEqual(await fsckDocument(paths), { issues: [], ok: true });
  assert.deepEqual(await repairDocument(paths), { actions: [], repaired: false });
});

test("single-use invitations mint separate expiring and revocable sessions", async (t) => {
  const paths = await fixture(t);
  await writeFile(
    paths.tokensPath,
    [
      "token=one-use-editor-invite role=editor id=sam docs=shared-workpad expires=2999-01-01T00:00:00Z",
      "token=viewer role=viewer id=lee docs=shared-workpad expires=2999-01-01T00:00:00Z",
      "token=wrong role=editor id=pat docs=other",
      "token=expired role=owner id=old docs=shared-workpad expires=2000-01-01T00:00:00Z",
      "token=forever role=owner id=old docs=shared-workpad",
      "token=admin role=admin id=root docs=shared-workpad",
      "",
    ].join("\n"),
    "utf8",
  );
  await chmod(paths.tokensPath, 0o600);
  const now = new Date("2026-07-30T20:00:00Z");

  const redeemed = await redeemInvite({
    now,
    sessionToken: () => "separate-session-token",
    sessionsPath: paths.sessionsPath,
    token: "one-use-editor-invite",
    tokensPath: paths.tokensPath,
  });
  assert.deepEqual(redeemed, {
    actor: {
      canEdit: true,
      docs: new Set(["shared-workpad"]),
      id: "sam",
      kind: "human",
      role: "editor",
    },
    expires: "2026-08-06T20:00:00.000Z",
    token: "separate-session-token",
  });
  assert.deepEqual(
    await resolveSession(paths.sessionsPath, "separate-session-token", now),
    {
      canEdit: true,
      docs: new Set(["shared-workpad"]),
      id: "sam",
      kind: "human",
      role: "editor",
    },
  );
  assert.equal(
    await redeemInvite({
      now,
      sessionToken: () => "second-session-token",
      sessionsPath: paths.sessionsPath,
      token: "one-use-editor-invite",
      tokensPath: paths.tokensPath,
    }),
    null,
  );
  assert.equal(
    (await resolveSession(paths.sessionsPath, "one-use-editor-invite", now)),
    null,
  );
  assert.equal(
    await redeemInvite({
      now,
      sessionsPath: paths.sessionsPath,
      token: "wrong",
      tokensPath: paths.tokensPath,
    }),
    null,
  );
  assert.equal(
    await redeemInvite({
      now,
      sessionsPath: paths.sessionsPath,
      token: "expired",
      tokensPath: paths.tokensPath,
    }),
    null,
  );
  assert.equal(
    await redeemInvite({
      now,
      sessionsPath: paths.sessionsPath,
      token: "forever",
      tokensPath: paths.tokensPath,
    }),
    null,
  );
  assert.equal(
    await redeemInvite({
      now,
      sessionsPath: paths.sessionsPath,
      token: "admin",
      tokensPath: paths.tokensPath,
    }),
    null,
  );

  assert.equal((await lstat(paths.sessionsPath)).mode & 0o777, 0o600);
  const authLedger = await readFile(paths.sessionsPath, "utf8");
  assert.doesNotMatch(authLedger, /one-use-editor-invite|separate-session-token/);

  assert.equal(
    await revokeSession({
      now: new Date("2026-07-30T20:05:00Z"),
      sessionsPath: paths.sessionsPath,
      token: "separate-session-token",
    }),
    true,
  );
  assert.equal(
    await resolveSession(paths.sessionsPath, "separate-session-token", now),
    null,
  );
});

test("concurrent redemption issues exactly one session", async (t) => {
  const paths = await fixture(t);
  await writeFile(
    paths.tokensPath,
    "token=one-use role=editor id=sam docs=shared-workpad expires=2999-01-01T00:00:00Z\n",
    "utf8",
  );
  await chmod(paths.tokensPath, 0o600);
  let sequence = 0;

  const results = await Promise.all([
    redeemInvite({
      now: new Date("2026-07-30T20:00:00Z"),
      sessionToken: () => `session-${++sequence}`,
      sessionsPath: paths.sessionsPath,
      token: "one-use",
      tokensPath: paths.tokensPath,
    }),
    redeemInvite({
      now: new Date("2026-07-30T20:00:00Z"),
      sessionToken: () => `session-${++sequence}`,
      sessionsPath: paths.sessionsPath,
      token: "one-use",
      tokensPath: paths.tokensPath,
    }),
  ]);

  assert.equal(results.filter(Boolean).length, 1);
  assert.equal(
    (await readFile(paths.sessionsPath, "utf8")).trim().split("\n").length,
    1,
  );
});

test("invitation and session stores fail closed unless mode 600", async (t) => {
  const paths = await fixture(t);
  await writeFile(
    paths.tokensPath,
    "token=editor role=editor id=sam docs=shared-workpad expires=2999-01-01T00:00:00Z\n",
    "utf8",
  );
  await chmod(paths.tokensPath, 0o644);
  assert.equal(
    await redeemInvite({
      now: new Date("2026-07-30T20:00:00Z"),
      sessionsPath: paths.sessionsPath,
      token: "editor",
      tokensPath: paths.tokensPath,
    }),
    null,
  );

  await chmod(paths.tokensPath, 0o600);
  await writeFile(paths.sessionsPath, "", { encoding: "utf8", mode: 0o644 });
  await chmod(paths.sessionsPath, 0o644);
  assert.equal(
    await redeemInvite({
      now: new Date("2026-07-30T20:00:00Z"),
      sessionsPath: paths.sessionsPath,
      token: "editor",
      tokensPath: paths.tokensPath,
    }),
    null,
  );
  assert.equal(
    await resolveSession(paths.sessionsPath, "any-session-token"),
    null,
  );
});

test("a torn final session line is tolerated but interior damage fails closed", async (t) => {
  const paths = await fixture(t);
  await writeFile(
    paths.tokensPath,
    "token=one-use role=editor id=sam docs=shared-workpad expires=2999-01-01T00:00:00Z\n",
    "utf8",
  );
  await chmod(paths.tokensPath, 0o600);
  const now = new Date("2026-07-30T20:00:00Z");
  await redeemInvite({
    now,
    sessionToken: () => "live-session-token",
    sessionsPath: paths.sessionsPath,
    token: "one-use",
    tokensPath: paths.tokensPath,
  });
  const issued = await readFile(paths.sessionsPath, "utf8");

  await appendFile(paths.sessionsPath, '{"event":"session_iss', "utf8");
  assert.equal(
    (await resolveSession(paths.sessionsPath, "live-session-token", now))?.id,
    "sam",
  );

  const repair = await repairDocument(paths);
  assert.equal(repair.repaired, true);
  assert.match(repair.actions[0], /quarantined a torn line to .*sessions\.jsonl\.quarantine-/);
  assert.equal(await readFile(paths.sessionsPath, "utf8"), issued);

  await writeFile(paths.sessionsPath, `{"event":"torn"\n${issued}`, {
    encoding: "utf8",
    mode: 0o600,
  });
  await chmod(paths.sessionsPath, 0o600);
  assert.equal(await resolveSession(paths.sessionsPath, "live-session-token", now), null);
});

test("session records preserve exact actor kind and document scope", async (t) => {
  const paths = await fixture(t);
  await writeFile(
    paths.tokensPath,
    "token=agent-token role=editor id=helen kind=agent docs=shared-workpad expires=2999-01-01T00:00:00Z\n",
    "utf8",
  );
  await chmod(paths.tokensPath, 0o600);

  const redeemed = await redeemInvite({
    now: new Date("2026-07-30T20:00:00Z"),
    sessionToken: () => "helen-session-token",
    sessionsPath: paths.sessionsPath,
    token: "agent-token",
    tokensPath: paths.tokensPath,
  });

  assert.deepEqual(redeemed?.actor, {
    canEdit: true,
    docs: new Set(["shared-workpad"]),
    id: "helen",
    kind: "agent",
    role: "editor",
  });
});

test("document symlinks are refused in both layouts", async (t) => {
  const paths = await fixture(t);
  await mkdir(docFile(paths), { recursive: true });
  await symlink(paths.seedPath, docFile(paths, "doc.md"));

  await assert.rejects(loadDocument(paths), /symlink/i);

  const legacy = await fixture(t);
  await mkdir(legacy.dataDir, { recursive: true });
  await symlink(legacy.seedPath, join(legacy.dataDir, `${DEFAULT_DOC_ID}.md`));

  await assert.rejects(loadDocument(legacy), /symlink/i);
});
