import assert from "node:assert/strict";
import { chmod, mkdtemp, mkdir, rm, writeFile } from "node:fs/promises";
import type { AddressInfo } from "node:net";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import { createWorkpadServer, csrfForToken } from "./server.ts";

const SEED = "# Shared workpad\n\nA readable projection with a trail underneath.\n";

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
      "token=owner-token role=owner id=ali docs=shared-workpad expires=2999-01-01T00:00:00Z",
      "token=viewer-token role=viewer id=guest docs=shared-workpad expires=2999-01-01T00:00:00Z",
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
  return { dataDir, origin };
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

test("single-use invite exchanges URL credential for separate scoped session", async (t) => {
  const { origin } = await fixture(t);

  const invite = await fetch(`${origin}/workpad/invite/owner-token`, {
    redirect: "manual",
  });
  const cookie = cookieFrom(invite);
  const sessionToken = cookieToken(cookie);
  const page = await fetch(`${origin}/workpad`, { headers: { cookie } });
  const state = await fetch(`${origin}/workpad/api/document`, {
    headers: { cookie },
  });
  const reusedInvite = await fetch(`${origin}/workpad/invite/owner-token`, {
    redirect: "manual",
  });

  assert.equal(invite.status, 303);
  assert.equal(invite.headers.get("location"), "/workpad");
  assert.doesNotMatch(invite.headers.get("location") ?? "", /owner-token/);
  assert.notEqual(sessionToken, "owner-token");
  assert.match(invite.headers.get("set-cookie") ?? "", /HttpOnly/);
  assert.match(invite.headers.get("set-cookie") ?? "", /SameSite=Lax/);
  assert.equal(page.status, 200);
  assert.doesNotMatch(await page.text(), /owner-token/);
  assert.deepEqual((await state.json()).actor, { id: "ali", role: "owner" });
  assert.equal(reusedInvite.status, 404);
});

test("hash-checked edit and note expose provenance, viewer writes fail", async (t) => {
  const { origin } = await fixture(t);
  const invite = await fetch(`${origin}/workpad/invite/owner-token`, {
    redirect: "manual",
  });
  const cookie = cookieFrom(invite);
  const sessionToken = cookieToken(cookie);
  const stateResponse = await fetch(`${origin}/workpad/api/document`, {
    headers: { cookie },
  });
  const state = (await stateResponse.json()) as { sha: string };
  const headers = {
    "Content-Type": "application/json",
    "X-Workpad-CSRF": csrfForToken(sessionToken),
    cookie,
    origin,
  };
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

  const viewerInvite = await fetch(`${origin}/workpad/invite/viewer-token`, {
    redirect: "manual",
  });
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
  const invite = await fetch(`${origin}/workpad/invite/owner-token`, {
    redirect: "manual",
  });
  const cookie = cookieFrom(invite);
  const sessionToken = cookieToken(cookie);
  const state = (await (
    await fetch(`${origin}/workpad/api/document`, { headers: { cookie } })
  ).json()) as { sha: string };
  const headers = {
    "Content-Type": "application/json",
    "X-Workpad-CSRF": csrfForToken(sessionToken),
    cookie,
    origin,
  };
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
  const invite = await fetch(`${origin}/workpad/invite/viewer-token`, {
    redirect: "manual",
  });
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
