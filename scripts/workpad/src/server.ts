import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import { createServer, type IncomingMessage, type ServerResponse } from "node:http";
import { type AddressInfo } from "node:net";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

import {
  ConflictError,
  DOC_ID,
  appendNote,
  loadDocument,
  redeemInvite,
  resolveSession,
  revokeSession,
  saveDocument,
  sha256,
  type Actor,
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
const TOKEN_RE = /^[A-Za-z0-9_-]{8,160}$/;

export function csrfForToken(token: string): string {
  return createHash("sha256").update(`givecare-workpad-csrf:${token}`).digest("hex");
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

function validWriteRequest(request: IncomingMessage, token: string): boolean {
  return (
    request.headers.origin === expectedOrigin(request) &&
    request.headers["x-workpad-csrf"] === csrfForToken(token)
  );
}

async function bodyJson(request: IncomingMessage): Promise<Record<string, unknown>> {
  const chunks: Buffer[] = [];
  let size = 0;
  for await (const chunk of request) {
    const buffer = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
    size += buffer.byteLength;
    if (size > MAX_BODY_BYTES) throw new RangeError("Request body is too large.");
    chunks.push(buffer);
  }
  const parsed: unknown = JSON.parse(Buffer.concat(chunks).toString("utf8"));
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new TypeError("JSON object required.");
  }
  return parsed as Record<string, unknown>;
}

async function seedState(seedPath: string) {
  const seed = await readFile(seedPath);
  if (seed.byteLength > 192 * 1024) throw new RangeError("Seed exceeds Workpad limit.");
  return {
    activity: [],
    actor: { id: "you", role: "demo" },
    can_edit: true,
    doc_id: DOC_ID,
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
        const session = await redeemInvite({
          sessionsPath: config.sessionsPath,
          token,
          tokensPath: config.tokensPath,
        });
        if (!session) {
          json(response, 404, { error: "Not found." });
          return;
        }
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
        return;
      }
      if (method === "GET" && path === "/workpad") {
        const access = await actorFor(request, config);
        if (!access) {
          shell(response, parseCookies(request).has(COOKIE_NAME) ? "locked" : "locked");
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
        const state = await loadDocument(config);
        json(response, 200, {
          ...state,
          actor: { id: access.actor.id, role: access.actor.role },
          can_edit: access.actor.canEdit,
        });
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
                ...config,
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
                ...config,
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
