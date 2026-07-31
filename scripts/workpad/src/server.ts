import { createHash } from "node:crypto";
import { mkdir, readFile } from "node:fs/promises";
import { watch, type FSWatcher } from "node:fs";
import { createServer, type IncomingMessage, type ServerResponse } from "node:http";
import { type AddressInfo } from "node:net";
import { basename, dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

import {
  ConflictError,
  DEFAULT_DOC_ID,
  appendNote,
  loadDocument,
  redeemInvite,
  resolveSession,
  revokeSession,
  saveDocument,
  sha256,
  type Actor,
  type DocRef,
} from "./store.ts";

export type WorkpadConfig = {
  dataDir: string;
  publicDir: string;
  seedPath: string;
  sessionsPath: string;
  tokensPath: string;
};

const COOKIE_NAME = "givecare_workpad";
const MAX_BODY_BYTES = 200 * 1024;
const MAX_MARKDOWN_BYTES = 192 * 1024;
const TOKEN_RE = /^[A-Za-z0-9_-]{22,160}$/;
const REDEEM_WINDOW_MS = 60_000;
const REDEEM_MAX_ATTEMPTS = 10;
const SSE_HEARTBEAT_MS = 30_000;
const WATCH_DEBOUNCE_MS = 250;

export function csrfForToken(token: string): string {
  return createHash("sha256").update(`givecare-workpad-csrf:${token}`).digest("hex");
}

function docRef(config: WorkpadConfig): DocRef {
  return { dataDir: config.dataDir, docId: DEFAULT_DOC_ID, seedPath: config.seedPath };
}

function securityHeaders(response: ServerResponse) {
  response.setHeader("X-Robots-Tag", "noindex, nofollow");
  response.setHeader("Cache-Control", "no-store, private, max-age=0");
  response.setHeader("Pragma", "no-cache");
  response.setHeader("Referrer-Policy", "no-referrer");
  response.setHeader("X-Content-Type-Options", "nosniff");
  response.setHeader(
    "Content-Security-Policy",
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; " +
      "img-src 'self' data:; connect-src 'self'; font-src 'self'; " +
      "frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
  );
  response.setHeader(
    "Permissions-Policy",
    "camera=(), microphone=(), geolocation=(), payment=()",
  );
}

function send(
  response: ServerResponse,
  status: number,
  value: string | Uint8Array,
  contentType: string,
) {
  securityHeaders(response);
  response.statusCode = status;
  response.setHeader("Content-Type", contentType);
  response.end(value);
}

function json(response: ServerResponse, status: number, value: unknown) {
  send(
    response,
    status,
    JSON.stringify(value),
    "application/json; charset=utf-8",
  );
}

function escapeHtml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function shell(
  response: ServerResponse,
  mode: "demo" | "private" | "locked",
  actor?: Actor,
  csrf = "",
) {
  const locked =
    mode === "locked"
      ? '<main class="access-gate"><p class="eyebrow">GiveCare Workpad</p>' +
        "<h1>An invitation opens this workspace.</h1>" +
        "<p>Use your private invitation, or explore the browser-only demo.</p>" +
        '<a class="access-button" href="/workpad/demo">Open the demo</a></main>'
      : "";
  const html =
    "<!doctype html><html lang=en><head><meta charset=utf-8>" +
    "<meta name=viewport content='width=device-width,initial-scale=1'>" +
    "<meta name=robots content='noindex,nofollow'>" +
    "<title>Workpad — GiveCare Review</title>" +
    '<link rel=stylesheet href="/workpad/assets/workpad.css"></head><body>' +
    `<div id="workpad-app" data-mode="${mode}" ` +
    `data-actor="${escapeHtml(actor?.id ?? "")}" ` +
    `data-role="${escapeHtml(actor?.role ?? "")}" ` +
    `data-can-edit="${actor?.canEdit ? "true" : "false"}" ` +
    `data-csrf="${escapeHtml(csrf)}">${locked}` +
    "<noscript>Workpad requires JavaScript.</noscript></div>" +
    '<script type=module src="/workpad/assets/workpad.js"></script></body></html>';
  send(response, mode === "locked" ? 401 : 200, html, "text/html; charset=utf-8");
}

function invitePage(token: string): string {
  return (
    "<!doctype html><html lang=en><head><meta charset=utf-8>" +
    "<meta name=viewport content='width=device-width,initial-scale=1'>" +
    "<meta name=robots content='noindex,nofollow'>" +
    "<title>Workpad — Open invitation</title>" +
    '<link rel=stylesheet href="/workpad/assets/workpad.css"></head><body>' +
    '<main class="access-gate"><p class="eyebrow">GiveCare Workpad</p>' +
    "<h1>An invitation is ready to open.</h1>" +
    "<p>Confirm below to open this workpad in your browser.</p>" +
    `<form method="POST" action="/workpad/api/invite/redeem">` +
    `<input type="hidden" name="token" value="${escapeHtml(token)}">` +
    '<button class="access-button" type="submit">Open the workpad</button>' +
    "</form></main>" +
    "<noscript>Workpad requires JavaScript.</noscript></body></html>"
  );
}

function parseCookies(request: IncomingMessage): Map<string, string> {
  const cookies = new Map<string, string>();
  for (const part of (request.headers.cookie ?? "").split(";")) {
    const separator = part.indexOf("=");
    if (separator <= 0) continue;
    const key = part.slice(0, separator).trim();
    try {
      cookies.set(key, decodeURIComponent(part.slice(separator + 1).trim()));
    } catch {
      // Ignore malformed cookie values.
    }
  }
  return cookies;
}

function expectedOrigin(request: IncomingMessage): string {
  const forwarded = request.headers["x-forwarded-proto"];
  const protocol =
    typeof forwarded === "string" ? forwarded.split(",", 1)[0].trim() : "http";
  return `${protocol}://${request.headers.host ?? "localhost"}`;
}

function clientKey(request: IncomingMessage): string {
  const forwarded = request.headers["x-forwarded-for"];
  const first = typeof forwarded === "string" ? forwarded.split(",", 1)[0].trim() : "";
  return first || request.socket.remoteAddress || "unknown";
}

function validWriteRequest(request: IncomingMessage, token: string): boolean {
  return (
    request.headers.origin === expectedOrigin(request) &&
    request.headers["x-workpad-csrf"] === csrfForToken(token)
  );
}

async function readBody(request: IncomingMessage, limit: number): Promise<Buffer> {
  const chunks: Buffer[] = [];
  let size = 0;
  for await (const chunk of request) {
    const buffer = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
    size += buffer.byteLength;
    if (size > limit) throw new RangeError("Request body is too large.");
    chunks.push(buffer);
  }
  return Buffer.concat(chunks);
}

async function bodyJson(request: IncomingMessage): Promise<Record<string, unknown>> {
  const raw = await readBody(request, MAX_BODY_BYTES);
  const parsed: unknown = JSON.parse(raw.toString("utf8"));
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new TypeError("JSON object required.");
  }
  return parsed as Record<string, unknown>;
}

async function bodyToken(request: IncomingMessage): Promise<string> {
  const raw = await readBody(request, MAX_BODY_BYTES);
  const contentType = request.headers["content-type"] ?? "";
  if (contentType.includes("application/json")) {
    if (raw.byteLength === 0) return "";
    const parsed: unknown = JSON.parse(raw.toString("utf8"));
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      throw new TypeError("JSON object required.");
    }
    const token = (parsed as Record<string, unknown>).token;
    return typeof token === "string" ? token : "";
  }
  return new URLSearchParams(raw.toString("utf8")).get("token") ?? "";
}

// Rolling 60s attempt window per client, keyed by the first hop of
// x-forwarded-for (falling back to the socket address). Swept on every call
// since traffic to this single endpoint is low.
const redeemAttempts = new Map<string, number[]>();

function redeemRateLimited(key: string, now: number): boolean {
  for (const [k, attempts] of redeemAttempts) {
    const fresh = attempts.filter((ts) => now - ts < REDEEM_WINDOW_MS);
    if (fresh.length === 0) redeemAttempts.delete(k);
    else redeemAttempts.set(k, fresh);
  }
  const attempts = redeemAttempts.get(key) ?? [];
  if (attempts.length >= REDEEM_MAX_ATTEMPTS) return true;
  attempts.push(now);
  redeemAttempts.set(key, attempts);
  return false;
}

// One fs.watch per document path, shared across all connected SSE clients for
// that path. Watches the containing directory (not the file itself) so an
// atomic rename-over-target does not orphan the watch.
type WatcherEntry = {
  debounce: NodeJS.Timeout | null;
  listeners: Set<(sha: string) => void>;
  watcher: FSWatcher;
};

const docWatchers = new Map<string, WatcherEntry>();

async function notifyDocWatchers(path: string, entry: WatcherEntry): Promise<void> {
  try {
    const content = await readFile(path);
    const sha = sha256(content);
    for (const listener of entry.listeners) listener(sha);
  } catch {
    // The file may be mid-write or briefly missing; the next change event
    // will retry.
  }
}

function watchDocument(path: string, onChange: (sha: string) => void): () => void {
  let entry = docWatchers.get(path);
  if (!entry) {
    const target = basename(path);
    const listeners = new Set<(sha: string) => void>();
    const created: WatcherEntry = {
      debounce: null,
      listeners,
      watcher: watch(dirname(path), { persistent: false }, (_event, filename) => {
        if (filename && filename !== target) return;
        if (created.debounce) clearTimeout(created.debounce);
        created.debounce = setTimeout(() => {
          created.debounce = null;
          void notifyDocWatchers(path, created);
        }, WATCH_DEBOUNCE_MS);
      }),
    };
    entry = created;
    docWatchers.set(path, entry);
  }
  entry.listeners.add(onChange);
  return () => {
    const current = docWatchers.get(path);
    if (!current) return;
    current.listeners.delete(onChange);
    if (current.listeners.size === 0) {
      if (current.debounce) clearTimeout(current.debounce);
      current.watcher.close();
      docWatchers.delete(path);
    }
  };
}

async function seedState(seedPath: string) {
  const seed = await readFile(seedPath);
  if (seed.byteLength > MAX_MARKDOWN_BYTES) {
    throw new RangeError("Seed exceeds Workpad limit.");
  }
  return {
    activity: [],
    actor: { id: "you", role: "demo" },
    can_edit: true,
    doc_id: DEFAULT_DOC_ID,
    markdown: seed.toString("utf8"),
    sha: sha256(seed),
  };
}

async function actorFor(
  request: IncomingMessage,
  config: WorkpadConfig,
): Promise<{ actor: Actor; token: string } | null> {
  const token = parseCookies(request).get(COOKIE_NAME) ?? "";
  if (!token || !TOKEN_RE.test(token)) return null;
  const actor = await resolveSession(config.sessionsPath, token);
  return actor ? { actor, token } : null;
}

async function asset(response: ServerResponse, config: WorkpadConfig, name: string) {
  if (name !== "workpad.js" && name !== "workpad.css") {
    json(response, 404, { error: "Not found." });
    return;
  }
  try {
    const content = await readFile(join(config.publicDir, name));
    send(
      response,
      200,
      content,
      name.endsWith(".js")
        ? "text/javascript; charset=utf-8"
        : "text/css; charset=utf-8",
    );
  } catch {
    json(response, 404, { error: "Not found." });
  }
}

function writeError(response: ServerResponse, error: unknown) {
  if (error instanceof ConflictError) {
    json(response, 409, { error: error.message, current_sha: error.currentSha });
    return;
  }
  if (
    error instanceof RangeError ||
    error instanceof TypeError ||
    error instanceof SyntaxError
  ) {
    json(response, 400, { error: error.message });
    return;
  }
  console.error(error);
  json(response, 500, { error: "Workpad could not complete the request." });
}

function issueSessionCookie(
  response: ServerResponse,
  session: { expires: string; token: string },
) {
  securityHeaders(response);
  response.statusCode = 303;
  response.setHeader("Location", "/workpad");
  response.setHeader(
    "Set-Cookie",
    `${COOKIE_NAME}=${encodeURIComponent(session.token)}; ` +
      `Max-Age=${Math.max(
        1,
        Math.floor((new Date(session.expires).valueOf() - Date.now()) / 1_000),
      )}; ` +
      "Path=/workpad; HttpOnly; Secure; SameSite=Lax",
  );
  response.end();
}

export function createWorkpadServer(config: WorkpadConfig) {
  return createServer(async (request, response) => {
    try {
      const method = request.method ?? "GET";
      const url = new URL(request.url ?? "/", expectedOrigin(request));
      const path = url.pathname;

      if (method === "GET" && path === "/workpad/health") {
        json(response, 200, {
          dialect: "workpad-v1",
          status: "ok",
          surface: "workpad",
        });
        return;
      }
      if (method === "GET" && path === "/workpad/demo") {
        shell(response, "demo");
        return;
      }
      if (method === "GET" && path === "/workpad/api/demo") {
        json(response, 200, await seedState(config.seedPath));
        return;
      }
      if (method === "GET" && path.startsWith("/workpad/assets/")) {
        await asset(response, config, path.slice("/workpad/assets/".length));
        return;
      }
      if (method === "GET" && path.startsWith("/workpad/invite/")) {
        let token: string;
        try {
          token = decodeURIComponent(path.slice("/workpad/invite/".length));
        } catch {
          json(response, 404, { error: "Not found." });
          return;
        }
        if (!TOKEN_RE.test(token)) {
          json(response, 404, { error: "Not found." });
          return;
        }
        send(response, 200, invitePage(token), "text/html; charset=utf-8");
        return;
      }
      if (method === "POST" && path === "/workpad/api/invite/redeem") {
        if (redeemRateLimited(clientKey(request), Date.now())) {
          json(response, 429, { error: "Too many attempts. Try again later." });
          return;
        }
        let token: string;
        try {
          token = await bodyToken(request);
        } catch (error) {
          writeError(response, error);
          return;
        }
        if (!TOKEN_RE.test(token)) {
          json(response, 404, { error: "Not found." });
          return;
        }
        const session = await redeemInvite({
          sessionsPath: config.sessionsPath,
          token,
          tokensPath: config.tokensPath,
        });
        if (!session) {
          json(response, 404, { error: "Not found." });
          return;
        }
        issueSessionCookie(response, session);
        return;
      }
      if (method === "GET" && path === "/workpad") {
        const access = await actorFor(request, config);
        if (!access) {
          shell(response, "locked");
          return;
        }
        shell(response, "private", access.actor, csrfForToken(access.token));
        return;
      }

      const access = await actorFor(request, config);
      if (!access) {
        json(response, 404, { error: "Not found." });
        return;
      }

      if (method === "GET" && path === "/workpad/api/document") {
        const state = await loadDocument(docRef(config));
        json(response, 200, {
          ...state,
          actor: { id: access.actor.id, role: access.actor.role },
          can_edit: access.actor.canEdit,
        });
        return;
      }

      if (method === "GET" && path === "/workpad/api/events") {
        const docPath = join(config.dataDir, DEFAULT_DOC_ID, "doc.md");
        await mkdir(dirname(docPath), { recursive: true });
        securityHeaders(response);
        response.statusCode = 200;
        response.setHeader("Content-Type", "text/event-stream; charset=utf-8");
        response.flushHeaders?.();

        const unsubscribe = watchDocument(docPath, (sha) => {
          response.write(`event: change\ndata: ${JSON.stringify({ sha })}\n\n`);
        });
        const heartbeat = setInterval(() => {
          response.write(": ping\n\n");
        }, SSE_HEARTBEAT_MS);
        let cleaned = false;
        const cleanup = () => {
          if (cleaned) return;
          cleaned = true;
          clearInterval(heartbeat);
          unsubscribe();
        };
        response.once("close", cleanup);
        return;
      }

      if (method === "POST" && path === "/workpad/api/logout") {
        if (!validWriteRequest(request, access.token)) {
          json(response, 403, { error: "Logout not allowed." });
          return;
        }
        if (!(await revokeSession({ sessionsPath: config.sessionsPath, token: access.token }))) {
          json(response, 404, { error: "Not found." });
          return;
        }
        response.setHeader(
          "Set-Cookie",
          `${COOKIE_NAME}=; Max-Age=0; Path=/workpad; HttpOnly; Secure; SameSite=Lax`,
        );
        json(response, 200, { logged_out: true });
        return;
      }

      if (
        (method === "PUT" && path === "/workpad/api/document") ||
        (method === "POST" && path === "/workpad/api/note")
      ) {
        if (!access.actor.canEdit || !validWriteRequest(request, access.token)) {
          json(response, 403, { error: "Write not allowed." });
          return;
        }
        let payload: Record<string, unknown>;
        try {
          payload = await bodyJson(request);
        } catch (error) {
          writeError(response, error);
          return;
        }
        const baseSha = payload.base_sha;
        if (typeof baseSha !== "string" || !/^[0-9a-f]{64}$/.test(baseSha)) {
          json(response, 400, { error: "Valid base_sha required." });
          return;
        }
        try {
          if (method === "PUT") {
            if (typeof payload.markdown !== "string" || typeof payload.note !== "string") {
              throw new TypeError("Markdown and note strings are required.");
            }
            json(
              response,
              200,
              await saveDocument({
                ...docRef(config),
                actor: access.actor,
                baseSha,
                markdown: payload.markdown,
                note: payload.note,
              }),
            );
          } else {
            if (typeof payload.note !== "string") {
              throw new TypeError("Note string is required.");
            }
            json(
              response,
              200,
              await appendNote({
                ...docRef(config),
                actor: access.actor,
                baseSha,
                note: payload.note,
              }),
            );
          }
        } catch (error) {
          writeError(response, error);
        }
        return;
      }

      json(response, 404, { error: "Not found." });
    } catch (error) {
      console.error(error);
      json(response, 500, { error: "Workpad could not complete the request." });
    }
  });
}

function defaultConfig(): WorkpadConfig {
  const packageRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
  const dataDir =
    process.env.WORKPAD_DIR ?? resolve(packageRoot, "../../internal/review/workpads");
  return {
    dataDir,
    publicDir: process.env.WORKPAD_PUBLIC_DIR ?? join(packageRoot, "public"),
    seedPath: process.env.WORKPAD_SEED_PATH ?? join(packageRoot, "seed.md"),
    sessionsPath: process.env.WORKPAD_SESSIONS_PATH ?? join(dataDir, "sessions.jsonl"),
    tokensPath: process.env.WORKPAD_TOKENS_PATH ?? join(dataDir, "tokens.txt"),
  };
}

function isMain(): boolean {
  return Boolean(process.argv[1]) && import.meta.url === pathToFileURL(process.argv[1]).href;
}

if (isMain()) {
  const host = process.env.WORKPAD_HOST ?? "127.0.0.1";
  const port = Number.parseInt(process.env.WORKPAD_PORT ?? "3092", 10);
  const server = createWorkpadServer(defaultConfig());
  server.listen(port, host, () => {
    const address = server.address() as AddressInfo;
    console.log(
      JSON.stringify({
        event: "workpad.started",
        host: address.address,
        port: address.port,
      }),
    );
  });
  const close = () => server.close(() => process.exit(0));
  process.on("SIGINT", close);
  process.on("SIGTERM", close);
}
