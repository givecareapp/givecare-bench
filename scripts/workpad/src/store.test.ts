import assert from "node:assert/strict";
import {
  chmod,
  lstat,
  mkdir,
  mkdtemp,
  readFile,
  rm,
  symlink,
  writeFile,
} from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import {
  ConflictError,
  appendNote,
  loadDocument,
  redeemInvite,
  resolveSession,
  revokeSession,
  saveDocument,
  sha256,
  type Actor,
} from "./store.ts";

const SEED = "# Shared workpad\n\nHumans and agents think here together.\n";
const OWNER: Actor = {
  canEdit: true,
  docs: new Set(["shared-workpad"]),
  id: "ali",
  kind: "human",
  role: "owner",
};

async function fixture(t: test.TestContext) {
  const root = await mkdtemp(join(tmpdir(), "workpad-store-"));
  const dataDir = join(root, "data");
  const seedPath = join(root, "seed.md");
  const sessionsPath = join(root, "sessions.jsonl");
  const tokensPath = join(root, "tokens.txt");
  await writeFile(seedPath, SEED, "utf8");
  t.after(() => rm(root, { recursive: true, force: true }));
  return { dataDir, root, seedPath, sessionsPath, tokensPath };
}

test("loads the exact seed bytes and revision", async (t) => {
  const paths = await fixture(t);

  const state = await loadDocument(paths);

  assert.equal(state.markdown, SEED);
  assert.equal(state.sha, sha256(SEED));
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
  assert.equal(
    await readFile(join(paths.dataDir, "shared-workpad.md"), "utf8"),
    revised,
  );
  assert.equal(
    await readFile(join(paths.dataDir, "revisions", `${saved.sha}.md`), "utf8"),
    revised,
  );
  assert.deepEqual(saved.event, {
    actor: { id: "ali", kind: "human", role: "owner" },
    base_sha: before.sha,
    doc_id: "shared-workpad",
    event_id: "evt:test:save",
    note: "Captured the deployment boundary.",
    result_sha: saved.sha,
    source_refs: [],
    ts: "2026-07-30T20:00:00.000Z",
    verb: "edited",
  });
});

test("stale save fails without changing the projection or ledger", async (t) => {
  const paths = await fixture(t);
  const before = await loadDocument(paths);
  const first = await saveDocument({
    ...paths,
    actor: OWNER,
    baseSha: before.sha,
    markdown: `${SEED}\nFirst.\n`,
    note: "",
  });
  const documentBefore = await readFile(join(paths.dataDir, "shared-workpad.md"));
  const ledgerBefore = await readFile(
    join(paths.dataDir, "shared-workpad.activity.jsonl"),
  );

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

  assert.deepEqual(
    await readFile(join(paths.dataDir, "shared-workpad.md")),
    documentBefore,
  );
  assert.deepEqual(
    await readFile(join(paths.dataDir, "shared-workpad.activity.jsonl")),
    ledgerBefore,
  );
});

test("a failed projection write is recovered from its durable provenance event", async (t) => {
  const paths = await fixture(t);
  const before = await loadDocument(paths);
  const revised = `${SEED}\nRecovered after interruption.\n`;
  await mkdir(paths.dataDir, { recursive: true });
  await mkdir(join(paths.dataDir, "shared-workpad.md"));

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

  const eventsBeforeRecovery = (
    await readFile(join(paths.dataDir, "shared-workpad.activity.jsonl"), "utf8")
  )
    .trim()
    .split("\n")
    .map((line) => JSON.parse(line) as { event_id: string; result_sha: string });
  assert.deepEqual(eventsBeforeRecovery, [
    {
      actor: { id: "ali", kind: "human", role: "owner" },
      base_sha: before.sha,
      doc_id: "shared-workpad",
      event_id: "evt:test:interrupted",
      note: "This event must exist before the projection changes.",
      result_sha: sha256(revised),
      source_refs: [],
      ts: "2026-07-30T20:01:00.000Z",
      verb: "edited",
    },
  ]);

  await rm(join(paths.dataDir, "shared-workpad.md"), { recursive: true });
  const recovered = await loadDocument(paths);

  assert.equal(recovered.markdown, revised);
  assert.equal(recovered.sha, sha256(revised));
  assert.equal(
    await readFile(join(paths.dataDir, "shared-workpad.md"), "utf8"),
    revised,
  );
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
  await writeFile(
    join(paths.root, "activity-source"),
    [
      '{"event_id":"one","ts":"2026-07-30T01:00:00Z"}',
      "not-json",
      '{"event_id":"two","ts":"2026-07-30T02:00:00Z"}',
      "",
    ].join("\n"),
    "utf8",
  );
  await import("node:fs/promises").then(({ mkdir, copyFile }) =>
    mkdir(paths.dataDir, { recursive: true }).then(() =>
      copyFile(
        join(paths.root, "activity-source"),
        join(paths.dataDir, "shared-workpad.activity.jsonl"),
      ),
    ),
  );

  const state = await loadDocument(paths);

  assert.deepEqual(
    state.activity.map((event) => event.event_id),
    ["two", "one"],
  );
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

test("document symlinks are refused", async (t) => {
  const paths = await fixture(t);
  await mkdir(paths.dataDir, { recursive: true });
  await symlink(paths.seedPath, join(paths.dataDir, "shared-workpad.md"));

  await assert.rejects(loadDocument(paths), /symlink/i);
});
