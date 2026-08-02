import assert from "node:assert/strict";
import { chmod, mkdtemp, mkdir, readFile, readdir, rm, writeFile } from "node:fs/promises";
import { createConnection, createServer as createNetServer } from "node:net";
import type { AddressInfo } from "node:net";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import { createWorkpadServer, csrfForToken } from "./server.ts";

const OWNER_TOKEN = "owner-token-0000000001";
const EXPIRED_TOKEN = "expired-token-000000001";
const EVENT_A = "a".repeat(64);
const EVENT_B = "b".repeat(64);
const RECORD_A = "c".repeat(64);
const RECORD_B = "d".repeat(64);
let redeemClient = 10;

function canonical(value: unknown): string {
  if (value === null) return "null";
  if (typeof value === "string") return JSON.stringify(value);
  if (typeof value === "boolean") return value ? "true" : "false";
  if (typeof value === "number") return String(value);
  if (Array.isArray(value)) return `[${value.map(canonical).join(",")}]`;
  const object = value as Record<string, unknown>;
  return `{${Object.keys(object)
    .sort()
    .map((key) => `${JSON.stringify(key)}:${canonical(object[key])}`)
    .join(",")}}`;
}

function ledgerRow(entryId = EVENT_A, recordId = RECORD_A, appendedAt = "2026-08-02T07:15:00.000Z") {
  return {
    entry_id: entryId,
    appended_at: appendedAt,
    producer: { owner_id: "givecare", capability: "ingest.file", run_id: "run-1" },
    operation: { capability: "ingest.file", artifact_kind: "evidence" },
    source: { provider: "legacy" },
    classification: { outcome: "completed", evidence_status: "evidence" },
    artifact: { record_id: recordId },
    lineage: { relation: "none", record_id: "lineage-1", lead_id: "none" },
    access: "workspace",
  };
}

function goodResponse(rows = [ledgerRow()], cursor?: string): Buffer {
  const body: Record<string, unknown> = {
    schema_version: "houndd.read-response.v1",
    request_id: "",
    ok: true,
    outcome: "completed",
    record_ids: rows.map((row) => row.artifact.record_id),
    entry_ids: rows.map((row) => row.entry_id),
    usage: { requests: 0, bytes: 0, cost: 0 },
    result: rows,
    projection: {
      schema_version: "houndd.intake-ledger.v1",
      integrity: "verified",
      high_watermark: "snapshot-commitment",
    },
  };
  if (cursor) body.cursor = cursor;
  return Buffer.from(canonical({ wire_version: "houndd.uds.v1", status: 200, body }), "utf8");
}

type ReplyValue = Buffer | { raw: Buffer; bindRequestId?: boolean };
type Reply = (request: Record<string, unknown>) => ReplyValue;

async function fakeHound(t: test.TestContext, reply: Reply) {
  const root = await mkdtemp(join(tmpdir(), "workpad-hound-"));
  const socketPath = join(root, "hound.sock");
  const requests: Record<string, unknown>[] = [];
  const server = createNetServer((socket) => {
    const chunks: Buffer[] = [];
    socket.on("data", (chunk) => chunks.push(Buffer.from(chunk)));
    socket.on("end", () => {
      const frame = Buffer.concat(chunks);
      const raw = frame.subarray(4);
      const request = JSON.parse(raw.toString("utf8")) as Record<string, unknown>;
      const body = request.body as Record<string, unknown>;
      const response = reply(request);
      // The test response binds to the random request ID without trusting any
      // browser-controlled identity fields.
      let encoded = Buffer.isBuffer(response) ? response : response.raw;
      if (Buffer.isBuffer(response) || response.bindRequestId !== false) {
        try {
          const value = JSON.parse(encoded.toString("utf8")) as { body?: Record<string, unknown> };
          if (value.body) value.body.request_id = body.request_id;
          encoded = Buffer.from(canonical(value), "utf8");
        } catch {
          // Malformed-wire cases intentionally skip ID binding.
        }
      }
      requests.push(request);
      const header = Buffer.allocUnsafe(4);
      header.writeUInt32BE(encoded.byteLength, 0);
      socket.end(Buffer.concat([header, encoded]));
    });
  });
  await new Promise<void>((resolve) => server.listen(socketPath, resolve));
  t.after(
    () =>
      new Promise<void>((resolve, reject) =>
        server.close((error) => (error ? reject(error) : resolve())),
      ),
  );
  t.after(() => rm(root, { recursive: true, force: true }));
  return { socketPath, requests };
}

async function fixture(
  t: test.TestContext,
  houndSocket: string,
  ledgerOverrides: Partial<Parameters<typeof createWorkpadServer>[0]> = {},
) {
  const root = await mkdtemp(join(tmpdir(), "workpad-ledger-"));
  const publicDir = join(root, "public");
  const dataDir = join(root, "documents-never-touched");
  const seedPath = join(root, "seed.md");
  const sessionsPath = join(root, "sessions.jsonl");
  const tokensPath = join(root, "tokens.txt");
  await mkdir(publicDir);
  await writeFile(seedPath, "# Workpad\n", "utf8");
  await writeFile(join(publicDir, "workpad.js"), "", "utf8");
  await writeFile(join(publicDir, "workpad.css"), "", "utf8");
  await writeFile(join(publicDir, "intake-ledger.js"), "", "utf8");
  await writeFile(join(publicDir, "intake-ledger.css"), "", "utf8");
  await writeFile(
    tokensPath,
    [
      `token=${OWNER_TOKEN} role=owner id=ali docs=shared-workpad expires=2999-01-01T00:00:00Z`,
      `token=${EXPIRED_TOKEN} role=viewer id=expired docs=shared-workpad expires=2000-01-01T00:00:00Z`,
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
    houndSocket,
    houndProducerOwnerId: "workpad-ledger",
    houndProducerRunId: "review-ui",
    houndPolicyId: "ledger-policy",
    houndRequestedAccess: "workspace",
    houndLedgerLimit: 50,
    ...ledgerOverrides,
  });
  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
  const address = server.address() as AddressInfo;
  t.after(
    () =>
      new Promise<void>((resolve, reject) =>
        server.close((error) => (error ? reject(error) : resolve())),
      ),
  );
  t.after(() => rm(root, { recursive: true, force: true }));
  return { dataDir, origin: `http://127.0.0.1:${address.port}` };
}

async function ownerCookie(origin: string): Promise<string> {
  redeemClient += 1;
  const response = await fetch(`${origin}/workpad/api/invite/redeem`, {
    method: "POST",
    headers: { "content-type": "application/json", "x-forwarded-for": `192.0.2.${redeemClient}` },
    body: JSON.stringify({ token: OWNER_TOKEN }),
    redirect: "manual",
  });
  assert.equal(response.status, 303);
  const cookie = response.headers.get("set-cookie");
  assert.ok(cookie);
  return cookie.split(";", 1)[0];
}

test("intake ledger is session-gated before any Unix socket call", async (t) => {
  const hound = await fakeHound(t, () => goodResponse());
  const { origin } = await fixture(t, hound.socketPath);

  const page = await fetch(`${origin}/workpad/intake-ledger`);
  const api = await fetch(`${origin}/workpad/api/intake-ledger`);
  const invalid = await fetch(`${origin}/workpad/api/intake-ledger`, {
    headers: { cookie: "givecare_workpad=not-a-session-token-000" },
  });
  const expired = await fetch(`${origin}/workpad/api/invite/redeem`, {
    method: "POST",
    headers: { "content-type": "application/json", "x-forwarded-for": "192.0.2.220" },
    body: JSON.stringify({ token: EXPIRED_TOKEN }),
    redirect: "manual",
  });

  const cookie = await ownerCookie(origin);
  const token = decodeURIComponent(cookie.slice(cookie.indexOf("=") + 1));
  const logout = await fetch(`${origin}/workpad/api/logout`, {
    method: "POST",
    headers: {
      cookie,
      origin,
      "x-workpad-csrf": csrfForToken(token),
    },
  });
  const revoked = await fetch(`${origin}/workpad/api/intake-ledger`, { headers: { cookie } });

  assert.equal(page.status, 404);
  assert.equal(api.status, 404);
  assert.equal(invalid.status, 404);
  assert.equal(expired.status, 404);
  assert.equal(logout.status, 200);
  assert.equal(revoked.status, 404);
  assert.deepEqual(hound.requests, []);
});

test("intake ledger uses one fixed canonical Unix request and ignores browser claims", async (t) => {
  const hound = await fakeHound(t, () => goodResponse([ledgerRow(EVENT_A, "record-1", "2026-08-02T07:15:00Z")], "cursor-next"));
  const { origin, dataDir } = await fixture(t, hound.socketPath);
  const cookie = await ownerCookie(origin);

  const response = await fetch(`${origin}/workpad/api/intake-ledger?cursor=opaque-cursor`, {
    headers: { cookie },
  });
  const rejected = await fetch(
    `${origin}/workpad/api/intake-ledger?cursor=opaque-cursor&policy_id=browser-override`,
    { headers: { cookie } },
  );

  assert.equal(response.status, 200);
  assert.equal(rejected.status, 400);
  assert.equal(hound.requests.length, 1);
  const request = hound.requests[0];
  assert.deepEqual(Object.keys(request).sort(), ["body", "method", "path", "wire_version"]);
  assert.equal(request.method, "GET");
  assert.equal(request.path, "/v1/journal");
  const body = request.body as Record<string, unknown>;
  assert.deepEqual(body.producer, {
    owner_id: "workpad-ledger",
    capability: "journal.query",
    run_id: "review-ui",
  });
  assert.equal(body.policy_id, "ledger-policy");
  assert.equal(body.requested_access, "workspace");
  assert.deepEqual((body.operation as Record<string, unknown>).payload, {
    cursor: "opaque-cursor",
    filter: {},
    limit: 50,
    view: "intake-ledger.v1",
  });
  await assert.rejects(readFile(dataDir), /ENOENT/);
});

test("missing or malformed fixed Hound ledger configuration is unavailable and never falls back", async (t) => {
  const hound = await fakeHound(t, () => goodResponse());
  const invalidConfigs: Array<Partial<Parameters<typeof createWorkpadServer>[0]>> = [
    { houndSocket: undefined },
    { houndSocket: "relative.sock" },
    { houndPolicyId: undefined },
    { houndProducerOwnerId: "owner " },
    { houndProducerRunId: undefined },
    { houndRequestedAccess: "public " as "public" },
    { houndLedgerLimit: 1.5 },
  ];
  for (const override of invalidConfigs) {
    const { origin } = await fixture(t, hound.socketPath, override);
    const cookie = await ownerCookie(origin);
    const response = await fetch(`${origin}/workpad/api/intake-ledger`, { headers: { cookie } });
    assert.equal(response.status, 503);
  }
  assert.deepEqual(hound.requests, []);
});

function rawHttp(origin: string, request: string): Promise<string> {
  const endpoint = new URL(origin);
  return new Promise((resolve, reject) => {
    const socket = createConnection({ host: endpoint.hostname, port: Number(endpoint.port) });
    const chunks: Buffer[] = [];
    socket.once("connect", () => socket.write(request));
    socket.on("data", (chunk) => chunks.push(Buffer.from(chunk)));
    socket.once("error", reject);
    socket.once("end", () => resolve(Buffer.concat(chunks).toString("utf8")));
  });
}

test("intake ledger refuses raw GET body framing before Unix dispatch", async (t) => {
  const hound = await fakeHound(t, () => goodResponse());
  const { origin } = await fixture(t, hound.socketPath);
  const cookie = await ownerCookie(origin);
  const endpoint = new URL(origin);
  const common = `Host: ${endpoint.host}\r\nCookie: ${cookie}\r\nConnection: close\r\n`;
  const contentLength = await rawHttp(
    origin,
    `GET /workpad/api/intake-ledger HTTP/1.1\r\n${common}Content-Length: 1\r\n\r\nx`,
  );
  const transferEncoding = await rawHttp(
    origin,
    `GET /workpad/api/intake-ledger HTTP/1.1\r\n${common}Transfer-Encoding: chunked\r\n\r\n1\r\nx\r\n0\r\n\r\n`,
  );
  assert.match(contentLength, /^HTTP\/1\.1 400 /);
  assert.match(transferEncoding, /^HTTP\/1\.1 400 /);
  assert.deepEqual(hound.requests, []);
});

test("intake ledger maps malformed and unavailable Hound replies to safe statuses without leaks", async (t) => {
  const cases: Array<{ status: number; reply: Reply }> = [
    { status: 503, reply: () => Buffer.from("{}") },
    { status: 503, reply: () => goodResponse([ledgerRow(EVENT_A, "record-1", "2026-08-02T07:15:00+01:00")]) },
    {
      status: 503,
      reply: () =>
        Buffer.from(
          canonical({
            wire_version: "houndd.uds.v1",
            status: 400,
            body: {
              schema_version: "houndd.read-response.v1",
              request_id: "",
              ok: false,
              outcome: "invalid",
              record_ids: [],
              entry_ids: [],
              usage: { requests: 0, bytes: 0, cost: 0 },
              error: { code: "bad_cursor", retryable: false, message: "cursor contents" },
            },
          }),
          "utf8",
        ),
    },
    { status: 503, reply: () => ({ raw: Buffer.concat([goodResponse(), Buffer.from("\n")]), bindRequestId: false }) },
    { status: 503, reply: () => Buffer.alloc(1_048_577, 0x61) },
    {
      status: 503,
      reply: () =>
        Buffer.from(
          canonical({
            wire_version: "houndd.uds.v1",
            status: 503,
            body: {
              schema_version: "houndd.read-response.v1",
              request_id: "",
              ok: false,
              outcome: "unavailable",
              record_ids: [],
              entry_ids: [],
              usage: { requests: 0, bytes: 0, cost: 0 },
              error: { code: "provider_raw", retryable: true, message: "/secret/path native_id=leak" },
            },
          }),
          "utf8",
        ),
    },
    {
      status: 404,
      reply: () =>
        Buffer.from(
          canonical({
            wire_version: "houndd.uds.v1",
            status: 404,
            body: {
              schema_version: "houndd.read-response.v1",
              request_id: "",
              ok: false,
              outcome: "not_found",
              record_ids: [],
              entry_ids: [],
              usage: { requests: 0, bytes: 0, cost: 0 },
            },
          }),
          "utf8",
        ),
    },
  ];
  for (const item of cases) {
    const hound = await fakeHound(t, item.reply);
    const { origin } = await fixture(t, hound.socketPath);
    const cookie = await ownerCookie(origin);
    const response = await fetch(`${origin}/workpad/api/intake-ledger`, { headers: { cookie } });
    const body = await response.text();
    assert.equal(response.status, item.status);
    assert.doesNotMatch(body, /secret|native_id|provider_raw/i);
  }
});

test("intake ledger allows chronological, empty, and cursor pages while rejecting hidden fields", async (t) => {
  let calls = 0;
  const hound = await fakeHound(t, () => {
    calls += 1;
    return calls === 1
      ? goodResponse([ledgerRow(EVENT_A, RECORD_A), ledgerRow(EVENT_B, RECORD_B, "2026-08-02T07:16:00.000Z")], "next")
      : goodResponse([]);
  });
  const { origin } = await fixture(t, hound.socketPath);
  const cookie = await ownerCookie(origin);
  const first = await fetch(`${origin}/workpad/api/intake-ledger`, { headers: { cookie } });
  const second = await fetch(`${origin}/workpad/api/intake-ledger?cursor=next`, { headers: { cookie } });
  const firstBody = (await first.json()) as { rows: Array<Record<string, unknown>>; cursor?: string };

  assert.equal(first.status, 200);
  assert.equal(second.status, 200);
  assert.equal(firstBody.rows.length, 2);
  assert.equal(firstBody.cursor, "next");
  assert.deepEqual(Object.keys(firstBody.rows[0]).sort(), [
    "access",
    "appended_at",
    "artifact",
    "classification",
    "entry_id",
    "lineage",
    "operation",
    "producer",
    "source",
  ]);
});

test("intake ledger repeated unavailable exchanges are FD-flat and client/UI sources have no data sinks", async (t) => {
  const hound = await fakeHound(t, () => Buffer.from("not-json", "utf8"));
  const { origin } = await fixture(t, hound.socketPath);
  const cookie = await ownerCookie(origin);
  // Warm the browser-side HTTP agent before taking the descriptor baseline;
  // only the repeated UDS failures are under test below.
  assert.equal((await fetch(`${origin}/workpad/api/intake-ledger`, { headers: { cookie } })).status, 503);
  await new Promise((resolve) => setTimeout(resolve, 20));
  const before = (await readdir("/proc/self/fd")).length;
  for (let index = 0; index < 20; index += 1) {
    const response = await fetch(`${origin}/workpad/api/intake-ledger`, { headers: { cookie } });
    assert.equal(response.status, 503);
  }
  const after = (await readdir("/proc/self/fd")).length;
  assert.ok(after <= before + 1, `FD growth ${before} -> ${after}`);
  const client = await readFile(new URL("./intake-ledger-client.ts", import.meta.url), "utf8");
  assert.doesNotMatch(client, /innerHTML|localStorage|EventSource|href\s*=|native_id|canonical_url|authorized_uri|content_sha256|object_key/i);
  assert.match(client, /textContent/);
});

test("ledger shell and build sources provide a narrow, reduced-motion-safe readable view", async (t) => {
  const hound = await fakeHound(t, () => goodResponse());
  const { origin } = await fixture(t, hound.socketPath);
  const cookie = await ownerCookie(origin);
  const page = await fetch(`${origin}/workpad/intake-ledger`, { headers: { cookie } });
  const source = await readFile(new URL("./intake-ledger.css", import.meta.url), "utf8");
  const builtClient = await readFile(new URL("../public/intake-ledger.js", import.meta.url), "utf8");
  const builtCss = await readFile(new URL("../public/intake-ledger.css", import.meta.url), "utf8");

  assert.equal(page.status, 200);
  assert.match(await page.text(), /intake-ledger\.js/);
  assert.match(source, /max-width: 760px/);
  assert.match(source, /prefers-reduced-motion: reduce/);
  assert.match(source, /ledger-row/);
  assert.match(builtClient, /intake-ledger/);
  assert.match(builtCss, /prefers-reduced-motion/);
});
