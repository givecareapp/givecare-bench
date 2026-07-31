import assert from "node:assert/strict";
import { chmod, mkdtemp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import type { AddressInfo } from "node:net";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import { createWorkpadServer, csrfForToken } from "./server.ts";

const SEED = "# Shared workpad\n\nA readable projection with a trail underneath.\n";
const OWNER_TOKEN = "owner-token-0000000001";
const VIEWER_TOKEN = "viewer-token-0000000001";
const SECOND_TOKEN = "editor-token-0000000001";
const SHORT_TOKEN = "short-token12345";
const BOGUS_TOKEN = "bogus-invite-token-000000";

async function fixture(t: test.TestContext) {
  const root = await mkdtemp(join(tmpdir(), "workpad-server-"));
  const dataDir = join(root, "data");
  const publicDir = join(root, "public");
  const seedPath = join(root, "seed.md");
  const sessionsPath = join(root, "sessions.jsonl");
  const tokensPath = join(root, "tokens.txt");
  await mkdir(publicDir);
  await writeFile(seedPath, SEED, "utf8");
  await writeFile(join(publicDir, "workpad.js"), "console.log('workpad')", "utf8");
  await writeFile(join(publicDir, "workpad.css"), ":root{}", "utf8");
  await writeFile(
    tokensPath,
    [
      `token=${OWNER_TOKEN} role=owner id=ali docs=shared-workpad expires=2999-01-01T00:00:00Z`,
      `token=${VIEWER_TOKEN} role=viewer id=guest docs=shared-workpad expires=2999-01-01T00:00:00Z`,
      `token=${SECOND_TOKEN} role=editor id=sam docs=shared-workpad expires=2999-01-01T00:00:00Z`,
      "",
    ].join("\n"),
    "utf8",
  );
  await chmod(tokensPath, 0o600);

  const server = createWorkpadServer({
    dataDir,
    publicDir,
    seedPath,
    sessionsPath,
    tokensPath,
  });
  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
  const address = server.address() as AddressInfo;
  const origin = `http://127.0.0.1:${address.port}`;
  t.after(
    () =>
      new Promise<void>((resolve, reject) =>
        server.close((error) => (error ? reject(error) : resolve())),
      ),
  );
  t.after(() => rm(root, { recursive: true, force: true }));
  return { dataDir, origin, sessionsPath, tokensPath };
}

function cookieFrom(response: Response): string {
  const header = response.headers.get("set-cookie");
  assert.ok(header);
  return header.split(";", 1)[0];
}

function cookieToken(cookie: string): string {
  const separator = cookie.indexOf("=");
  assert.ok(separator > 0);
  return decodeURIComponent(cookie.slice(separator + 1));
}

async function redeem(origin: string, token: string, forwardedFor: string): Promise<Response> {
  return fetch(`${origin}/workpad/api/invite/redeem`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "x-forwarded-for": forwardedFor },
    body: JSON.stringify({ token }),
    redirect: "manual",
  });
}

function writeHeadersFor(origin: string, cookie: string, token: string) {
  return {
    "Content-Type": "application/json",
    "X-Workpad-CSRF": csrfForToken(token),
    cookie,
    origin,
  };
}

test("health and editable browser-local demo are public and hardened", async (t) => {
  const { origin } = await fixture(t);

  const health = await fetch(`${origin}/workpad/health`);
  const demo = await fetch(`${origin}/workpad/demo`);
  const privatePage = await fetch(`${origin}/workpad`);

  assert.deepEqual(await health.json(), {
    dialect: "workpad-v1",
    status: "ok",
    surface: "workpad",
  });
  assert.equal(demo.status, 200);
  assert.match(await demo.text(), /data-mode="demo"/);
  assert.equal(privatePage.status, 401);
  assert.equal(demo.headers.get("x-robots-tag"), "noindex, nofollow");
  assert.equal(demo.headers.get("referrer-policy"), "no-referrer");
  assert.match(demo.headers.get("content-security-policy") ?? "", /^default-src 'self'/);
});

test("GET invite page renders a confirm form without redeeming the invitation", async (t) => {
  const { origin, tokensPath } = await fixture(t);
  const before = await readFile(tokensPath, "utf8");

  const page = await fetch(`${origin}/workpad/invite/${OWNER_TOKEN}`);
  const body = await page.text();
  const after = await readFile(tokensPath, "utf8");
  const stillRedeemable = await redeem(origin, OWNER_TOKEN, "192.0.2.106");

  assert.equal(page.status, 200);
  assert.equal(page.headers.get("set-cookie"), null);
  assert.match(body, /action="\/workpad\/api\/invite\/redeem"/);
  assert.match(body, /method="POST"/);
  assert.match(body, new RegExp(`name="token" value="${OWNER_TOKEN}"`));
  assert.equal(after, before);
  assert.equal(stillRedeemable.status, 303);
});

test("POST redeem exchanges the invitation for a scoped session, one time only", async (t) => {
  const { origin } = await fixture(t);

  const first = await redeem(origin, OWNER_TOKEN, "192.0.2.107");
  const cookie = cookieFrom(first);
  const sessionToken = cookieToken(cookie);
  const page = await fetch(`${origin}/workpad`, { headers: { cookie } });
  const state = await fetch(`${origin}/workpad/api/document`, { headers: { cookie } });
  const second = await redeem(origin, OWNER_TOKEN, "192.0.2.107");

  assert.equal(first.status, 303);
  assert.equal(first.headers.get("location"), "/workpad");
  assert.doesNotMatch(first.headers.get("location") ?? "", new RegExp(OWNER_TOKEN));
  assert.notEqual(sessionToken, OWNER_TOKEN);
  assert.match(first.headers.get("set-cookie") ?? "", /HttpOnly/);
  assert.match(first.headers.get("set-cookie") ?? "", /SameSite=Lax/);
  assert.equal(page.status, 200);
  assert.doesNotMatch(await page.text(), new RegExp(OWNER_TOKEN));
  assert.deepEqual((await state.json()).actor, { id: "ali", role: "owner" });
  assert.equal(second.status, 404);
});

test("an invite token shorter than 22 characters is refused", async (t) => {
  const { origin } = await fixture(t);

  const page = await fetch(`${origin}/workpad/invite/${SHORT_TOKEN}`);
  const post = await redeem(origin, SHORT_TOKEN, "192.0.2.108");

  assert.equal(page.status, 404);
  assert.equal(post.status, 404);
});

test("more than ten redeem attempts within a minute are rate limited", async (t) => {
  const { origin } = await fixture(t);
  const forwardedFor = "192.0.2.109";

  const results: number[] = [];
  for (let attempt = 0; attempt < 11; attempt += 1) {
    const response = await redeem(origin, BOGUS_TOKEN, forwardedFor);
    results.push(response.status);
  }

  assert.deepEqual(results.slice(0, 10), Array(10).fill(404));
  assert.equal(results[10], 429);
});

test("hash-checked edit and note expose provenance, viewer writes fail", async (t) => {
  const { origin } = await fixture(t);
  const invite = await redeem(origin, OWNER_TOKEN, "192.0.2.102");
  const cookie = cookieFrom(invite);
  const sessionToken = cookieToken(cookie);
  const stateResponse = await fetch(`${origin}/workpad/api/document`, {
    headers: { cookie },
  });
  const state = (await stateResponse.json()) as { sha: string };
  const headers = writeHeadersFor(origin, cookie, sessionToken);
  const revised = `${SEED}\n## Decision\n\nKeep trust domains separate.\n`;

  const save = await fetch(`${origin}/workpad/api/document`, {
    method: "PUT",
    headers,
    body: JSON.stringify({ base_sha: state.sha, markdown: revised, note: "" }),
  });
  const saved = (await save.json()) as {
    event: { actor: { id: string }; base_sha: string; result_sha: string };
    sha: string;
  };
  const note = await fetch(`${origin}/workpad/api/note`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      base_sha: saved.sha,
      note: "Ready for a collaborator handoff.",
    }),
  });

  assert.equal(save.status, 200);
  assert.equal(saved.event.actor.id, "ali");
  assert.equal(saved.event.base_sha, state.sha);
  assert.equal(saved.event.result_sha, saved.sha);
  assert.equal(note.status, 200);

  const viewerInvite = await redeem(origin, VIEWER_TOKEN, "192.0.2.103");
  const viewerCookie = cookieFrom(viewerInvite);
  const viewerWrite = await fetch(`${origin}/workpad/api/document`, {
    method: "PUT",
    headers: {
      ...headers,
      "X-Workpad-CSRF": csrfForToken(cookieToken(viewerCookie)),
      cookie: viewerCookie,
    },
    body: JSON.stringify({ base_sha: saved.sha, markdown: "blocked", note: "" }),
  });
  assert.equal(viewerWrite.status, 403);
});

test("cross-origin and stale writes fail without overwriting", async (t) => {
  const { origin } = await fixture(t);
  const invite = await redeem(origin, OWNER_TOKEN, "192.0.2.104");
  const cookie = cookieFrom(invite);
  const sessionToken = cookieToken(cookie);
  const state = (await (
    await fetch(`${origin}/workpad/api/document`, { headers: { cookie } })
  ).json()) as { sha: string };
  const headers = writeHeadersFor(origin, cookie, sessionToken);
  const first = await fetch(`${origin}/workpad/api/document`, {
    method: "PUT",
    headers,
    body: JSON.stringify({
      base_sha: state.sha,
      markdown: `${SEED}\nFirst.\n`,
      note: "",
    }),
  });
  const firstState = (await first.json()) as { sha: string };

  const stale = await fetch(`${origin}/workpad/api/document`, {
    method: "PUT",
    headers,
    body: JSON.stringify({
      base_sha: state.sha,
      markdown: `${SEED}\nStale.\n`,
      note: "",
    }),
  });
  const crossOrigin = await fetch(`${origin}/workpad/api/document`, {
    method: "PUT",
    headers: { ...headers, origin: "https://attacker.example" },
    body: JSON.stringify({
      base_sha: firstState.sha,
      markdown: `${SEED}\nAttack.\n`,
      note: "",
    }),
  });

  assert.equal(stale.status, 409);
  assert.equal((await stale.json()).current_sha, firstState.sha);
  assert.equal(crossOrigin.status, 403);
});

test("logout revokes the server-side session and clears its cookie", async (t) => {
  const { origin } = await fixture(t);
  const invite = await redeem(origin, VIEWER_TOKEN, "192.0.2.105");
  const cookie = cookieFrom(invite);
  const sessionToken = cookieToken(cookie);

  const logout = await fetch(`${origin}/workpad/api/logout`, {
    method: "POST",
    headers: {
      "X-Workpad-CSRF": csrfForToken(sessionToken),
      cookie,
      origin,
    },
  });
  const after = await fetch(`${origin}/workpad/api/document`, {
    headers: { cookie },
  });

  assert.equal(logout.status, 200);
  assert.deepEqual(await logout.json(), { logged_out: true });
  assert.match(logout.headers.get("set-cookie") ?? "", /Max-Age=0/);
  assert.equal(after.status, 404);
});

test("a stale save merges with a concurrent editor's save and returns merged markdown", async (t) => {
  const { origin } = await fixture(t);

  const inviteA = await redeem(origin, OWNER_TOKEN, "192.0.2.110");
  const cookieA = cookieFrom(inviteA);
  const tokenA = cookieToken(cookieA);
  const inviteB = await redeem(origin, SECOND_TOKEN, "192.0.2.111");
  const cookieB = cookieFrom(inviteB);
  const tokenB = cookieToken(cookieB);

  const stateA = (await (
    await fetch(`${origin}/workpad/api/document`, { headers: { cookie: cookieA } })
  ).json()) as { sha: string };
  const stateB = (await (
    await fetch(`${origin}/workpad/api/document`, { headers: { cookie: cookieB } })
  ).json()) as { sha: string };
  assert.equal(stateA.sha, stateB.sha);

  const saveB = await fetch(`${origin}/workpad/api/document`, {
    method: "PUT",
    headers: writeHeadersFor(origin, cookieB, tokenB),
    body: JSON.stringify({
      base_sha: stateB.sha,
      markdown: `${SEED}\n## Decision\n\nShip the workpad.\n`,
      note: "",
    }),
  });
  const savedB = (await saveB.json()) as { merged: boolean };
  assert.equal(saveB.status, 200);
  assert.equal(savedB.merged, false);

  const saveA = await fetch(`${origin}/workpad/api/document`, {
    method: "PUT",
    headers: writeHeadersFor(origin, cookieA, tokenA),
    body: JSON.stringify({
      base_sha: stateA.sha,
      markdown: `> Context added by a collaborator.\n\n${SEED}`,
      note: "",
    }),
  });
  const savedA = (await saveA.json()) as {
    markdown?: string;
    merged: boolean;
    sha: string;
  };

  assert.equal(saveA.status, 200);
  assert.equal(savedA.merged, true);
  assert.equal(
    savedA.markdown,
    `> Context added by a collaborator.\n\n${SEED}\n## Decision\n\nShip the workpad.\n`,
  );
  assert.match(savedA.sha, /^[0-9a-f]{64}$/);
});

test("SSE events endpoint requires a session and emits a change after a save", async (t) => {
  const { origin } = await fixture(t);

  const unauthorized = await fetch(`${origin}/workpad/api/events`);
  assert.equal(unauthorized.status, 404);

  const invite = await redeem(origin, OWNER_TOKEN, "192.0.2.112");
  const cookie = cookieFrom(invite);
  const sessionToken = cookieToken(cookie);

  const controller = new AbortController();
  const stream = await fetch(`${origin}/workpad/api/events`, {
    headers: { cookie },
    signal: controller.signal,
  });
  assert.equal(stream.status, 200);
  assert.equal(stream.headers.get("content-type"), "text/event-stream; charset=utf-8");

  const reader = stream.body?.getReader();
  assert.ok(reader);
  const decoder = new TextDecoder();
  let received = "";

  const readUntilChange = (async () => {
    while (!received.includes("event: change")) {
      const { value, done } = await reader.read();
      if (done) break;
      received += decoder.decode(value, { stream: true });
    }
  })();

  // Give the SSE connection a moment to attach its watcher before saving.
  await new Promise((resolve) => setTimeout(resolve, 100));

  const state = (await (
    await fetch(`${origin}/workpad/api/document`, { headers: { cookie } })
  ).json()) as { sha: string };
  await fetch(`${origin}/workpad/api/document`, {
    method: "PUT",
    headers: writeHeadersFor(origin, cookie, sessionToken),
    body: JSON.stringify({
      base_sha: state.sha,
      markdown: `${SEED}\nLive reload check.\n`,
      note: "",
    }),
  });

  try {
    await Promise.race([
      readUntilChange,
      new Promise((_resolve, reject) =>
        setTimeout(() => reject(new Error("timed out waiting for SSE change event")), 5_000),
      ),
    ]);
    assert.match(received, /event: change/);
    assert.match(received, /"sha":"[0-9a-f]{64}"/);
  } finally {
    controller.abort();
  }
});
