/**
 * A deliberately small, server-side-only bridge to Hound's private ledger
 * projection.  This module has no HTTP, child-process, or filesystem API:
 * the caller gives it one fixed Unix socket path and it opens exactly one
 * AF_UNIX stream for one framed exchange.
 */

import { randomUUID } from "node:crypto";
import { createConnection } from "node:net";

export const HOUND_WIRE_VERSION = "houndd.uds.v1";
export const HOUND_READ_SCHEMA = "houndd.read-request.v1";
export const HOUND_RESPONSE_SCHEMA = "houndd.read-response.v1";
export const INTAKE_LEDGER_VIEW = "intake-ledger.v1";
export const MAX_HOUND_FRAME_BYTES = 1_048_576;
export const MAX_CURSOR_BYTES = 8_192;

export type LedgerBridgeConfig = {
  socketPath: string;
  producerOwnerId: string;
  producerRunId: string;
  policyId: string;
  requestedAccess: "public" | "workspace" | "restricted";
  limit: number;
  timeoutMs?: number;
};

export type LedgerLineage = {
  relation: string;
  record_id: string;
  lead_id: string;
};

export type IntakeLedgerRow = {
  entry_id: string;
  appended_at: string;
  producer: { owner_id: string; capability: string; run_id: string };
  operation: { capability: string; artifact_kind: string };
  source: { provider: string };
  classification: { outcome: string; evidence_status: string };
  artifact: { record_id: string };
  lineage: LedgerLineage;
  access: "public" | "workspace" | "restricted";
};

export type IntakeLedgerPage = {
  projection: {
    schema_version: "houndd.intake-ledger.v1";
    integrity: "verified";
    high_watermark: string;
  };
  rows: IntakeLedgerRow[];
  cursor?: string;
};

export class LedgerUnavailableError extends Error {
  constructor() {
    super("The intake ledger is unavailable.");
  }
}

export class LedgerNotFoundError extends Error {
  constructor() {
    super("Not found.");
  }
}

function text(value: unknown, max = MAX_HOUND_FRAME_BYTES): value is string {
  return typeof value === "string" && value.length > 0 && value.length <= max;
}

function exactObject(value: unknown, fields: readonly string[]): value is Record<string, unknown> {
  return (
    value !== null &&
    typeof value === "object" &&
    !Array.isArray(value) &&
    Object.keys(value as Record<string, unknown>).length === fields.length &&
    fields.every((field) => Object.hasOwn(value as Record<string, unknown>, field))
  );
}

function canonicalJson(value: unknown): string {
  if (value === null) return "null";
  if (typeof value === "string") return JSON.stringify(value);
  if (typeof value === "boolean") return value ? "true" : "false";
  if (typeof value === "number") {
    if (!Number.isSafeInteger(value) || value < 0) throw new LedgerUnavailableError();
    return String(value);
  }
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`;
  if (value && typeof value === "object") {
    const record = value as Record<string, unknown>;
    return `{${Object.keys(record)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${canonicalJson(record[key])}`)
      .join(",")}}`;
  }
  throw new LedgerUnavailableError();
}

function canonicalParse(raw: Buffer): unknown {
  let value: unknown;
  try {
    value = JSON.parse(raw.toString("utf8"));
  } catch {
    throw new LedgerUnavailableError();
  }
  if (Buffer.from(canonicalJson(value), "utf8").compare(raw) !== 0) {
    throw new LedgerUnavailableError();
  }
  return value;
}

function entryId(value: unknown): value is string {
  return typeof value === "string" && /^[0-9a-f]{64}$/.test(value);
}

function timestampNanoseconds(value: unknown): bigint | null {
  if (typeof value !== "string") return null;
  const match = /^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.(\d{1,9}))?Z$/.exec(value);
  if (!match) return null;
  const milliseconds = Date.parse(`${match[1]}Z`);
  if (Number.isNaN(milliseconds)) return null;
  if (new Date(milliseconds).toISOString().slice(0, 19) !== match[1]) return null;
  const fraction = (match[2] ?? "").padEnd(9, "0");
  return BigInt(milliseconds) * 1_000_000n + BigInt(fraction || "0");
}

function usage(value: unknown): boolean {
  return (
    exactObject(value, ["requests", "bytes", "cost"]) &&
    Object.values(value).every((item) => Number.isSafeInteger(item) && (item as number) >= 0)
  );
}

function safeError(value: unknown, retryable: boolean): boolean {
  return (
    exactObject(value, ["code", "retryable", "message"]) &&
    text(value.code) &&
    value.retryable === retryable &&
    text(value.message)
  );
}

function row(value: unknown): value is IntakeLedgerRow {
  if (
    !exactObject(value, [
      "entry_id",
      "appended_at",
      "producer",
      "operation",
      "source",
      "classification",
      "artifact",
      "lineage",
      "access",
    ]) ||
    !entryId(value.entry_id) ||
    timestampNanoseconds(value.appended_at) === null ||
    !exactObject(value.producer, ["owner_id", "capability", "run_id"]) ||
    !text(value.producer.owner_id) ||
    !text(value.producer.capability) ||
    !text(value.producer.run_id) ||
    !exactObject(value.operation, ["capability", "artifact_kind"]) ||
    !text(value.operation.capability) ||
    !text(value.operation.artifact_kind) ||
    !exactObject(value.source, ["provider"]) ||
    !text(value.source.provider) ||
    !exactObject(value.classification, ["outcome", "evidence_status"]) ||
    !text(value.classification.outcome) ||
    !text(value.classification.evidence_status) ||
    !exactObject(value.artifact, ["record_id"]) ||
    !text(value.artifact.record_id) ||
    !exactObject(value.lineage, ["relation", "record_id", "lead_id"]) ||
    !text(value.lineage.relation) ||
    !text(value.lineage.record_id) ||
    !text(value.lineage.lead_id) ||
    (value.access !== "public" && value.access !== "workspace" && value.access !== "restricted")
  ) {
    return false;
  }
  return true;
}

function rowsChronological(rows: IntakeLedgerRow[]): boolean {
  let previous: bigint | null = null;
  for (const item of rows) {
    // The canonical service ordering also includes a private sequence number.
    // This deliberately redacted projection cannot re-derive tie order, but it
    // can reject an obvious timestamp regression without inventing a second
    // ordering rule in Workpad.
    const current = timestampNanoseconds(item.appended_at);
    if (current === null || (previous !== null && current < previous)) return false;
    previous = current;
  }
  return true;
}

function parsePage(raw: Buffer, requestId: string): IntakeLedgerPage {
  const frame = canonicalParse(raw);
  if (
    !exactObject(frame, ["wire_version", "status", "body"]) ||
    frame.wire_version !== HOUND_WIRE_VERSION ||
    (frame.status !== 200 && frame.status !== 400 && frame.status !== 404 && frame.status !== 503) ||
    !exactObject(frame.body, Object.keys(frame.body as Record<string, unknown>))
  ) {
    throw new LedgerUnavailableError();
  }
  const body = frame.body as Record<string, unknown>;
  if (frame.status === 404) {
    if (
      !exactObject(body, ["schema_version", "request_id", "ok", "outcome", "record_ids", "entry_ids", "usage"]) ||
      body.schema_version !== HOUND_RESPONSE_SCHEMA ||
      body.request_id !== requestId ||
      body.ok !== false ||
      body.outcome !== "not_found" ||
      !Array.isArray(body.record_ids) ||
      !Array.isArray(body.entry_ids) ||
      body.record_ids.length !== 0 ||
      body.entry_ids.length !== 0 ||
      !usage(body.usage)
    ) {
      throw new LedgerUnavailableError();
    }
    throw new LedgerNotFoundError();
  }
  if (frame.status === 400 || frame.status === 503) {
    const retryable = frame.status === 503;
    const outcome = retryable ? "unavailable" : "invalid";
    if (
      !exactObject(body, ["schema_version", "request_id", "ok", "outcome", "record_ids", "entry_ids", "usage", "error"]) ||
      body.schema_version !== HOUND_RESPONSE_SCHEMA ||
      body.request_id !== requestId ||
      body.ok !== false ||
      body.outcome !== outcome ||
      !Array.isArray(body.record_ids) ||
      !Array.isArray(body.entry_ids) ||
      body.record_ids.length !== 0 ||
      body.entry_ids.length !== 0 ||
      !usage(body.usage) ||
      !safeError(body.error, retryable)
    ) {
      throw new LedgerUnavailableError();
    }
    throw new LedgerUnavailableError();
  }
  const required = [
    "schema_version",
    "request_id",
    "ok",
    "outcome",
    "record_ids",
    "entry_ids",
    "usage",
    "result",
    "projection",
  ];
  const optional = new Set(["cursor"]);
  if (
    !Object.keys(body).every((key) => required.includes(key) || optional.has(key)) ||
    !required.every((key) => Object.hasOwn(body, key)) ||
    body.schema_version !== HOUND_RESPONSE_SCHEMA ||
    body.request_id !== requestId ||
    body.ok !== true ||
    body.outcome !== "completed" ||
    !Array.isArray(body.result) ||
    !Array.isArray(body.entry_ids) ||
    !Array.isArray(body.record_ids) ||
    !usage(body.usage) ||
    !exactObject(body.projection, ["schema_version", "integrity", "high_watermark"]) ||
    body.projection.schema_version !== "houndd.intake-ledger.v1" ||
    body.projection.integrity !== "verified" ||
    !text(body.projection.high_watermark) ||
    (Object.hasOwn(body, "cursor") && !text(body.cursor, MAX_CURSOR_BYTES))
  ) {
    throw new LedgerUnavailableError();
  }
  const rows = body.result as IntakeLedgerRow[];
  const entryIds = body.entry_ids as unknown[];
  const recordIds = body.record_ids as unknown[];
  if (
    !rows.every(row) ||
    !rowsChronological(rows) ||
    !entryIds.every(entryId) ||
    !recordIds.every((recordId) => text(recordId))
  ) {
    throw new LedgerUnavailableError();
  }
  if (
    entryIds.length !== rows.length ||
    recordIds.length !== rows.length ||
    rows.some((item, index) => item.entry_id !== entryIds[index] || item.artifact.record_id !== recordIds[index]) ||
    new Set(rows.map((item) => item.entry_id)).size !== rows.length
  ) {
    throw new LedgerUnavailableError();
  }
  return {
    projection: {
      schema_version: "houndd.intake-ledger.v1",
      integrity: "verified",
      high_watermark: body.projection.high_watermark,
    },
    rows,
    ...(typeof body.cursor === "string" ? { cursor: body.cursor } : {}),
  };
}

function responseFrame(socketPath: string, frame: Buffer, timeoutMs: number): Promise<Buffer> {
  return new Promise((resolve, reject) => {
    let settled = false;
    const chunks: Buffer[] = [];
    let size = 0;
    const done = (error?: Error, value?: Buffer) => {
      if (settled) return;
      settled = true;
      socket.removeAllListeners();
      socket.destroy();
      if (error) reject(error);
      else resolve(value as Buffer);
    };
    const socket = createConnection({ path: socketPath });
    socket.setTimeout(timeoutMs);
    socket.once("connect", () => socket.end(frame));
    socket.on("data", (chunk: Buffer) => {
      size += chunk.byteLength;
      if (size > MAX_HOUND_FRAME_BYTES + 4) {
        done(new LedgerUnavailableError());
        return;
      }
      chunks.push(chunk);
    });
    socket.once("timeout", () => done(new LedgerUnavailableError()));
    socket.once("error", () => done(new LedgerUnavailableError()));
    socket.once("end", () => {
      const response = Buffer.concat(chunks);
      if (response.byteLength < 4) return done(new LedgerUnavailableError());
      const length = response.readUInt32BE(0);
      if (length === 0 || length > MAX_HOUND_FRAME_BYTES || response.byteLength !== length + 4) {
        return done(new LedgerUnavailableError());
      }
      done(undefined, response.subarray(4));
    });
  });
}

export async function requestIntakeLedger(
  config: LedgerBridgeConfig,
  cursor?: string,
): Promise<IntakeLedgerPage> {
  if (
    !config.socketPath.startsWith("/") ||
    !text(config.producerOwnerId) ||
    !text(config.producerRunId) ||
    !text(config.policyId) ||
    !Number.isSafeInteger(config.limit) ||
    config.limit < 1 ||
    config.limit > 100 ||
    (config.requestedAccess !== "public" &&
      config.requestedAccess !== "workspace" &&
      config.requestedAccess !== "restricted") ||
    (cursor !== undefined && (!text(cursor, MAX_CURSOR_BYTES) || /[\u0000-\u001f]/.test(cursor)))
  ) {
    throw new LedgerUnavailableError();
  }
  const requestId = randomUUID();
  const payload: Record<string, unknown> = {
    filter: {},
    limit: config.limit,
    view: INTAKE_LEDGER_VIEW,
  };
  if (cursor !== undefined) payload.cursor = cursor;
  const request = {
    wire_version: HOUND_WIRE_VERSION,
    method: "GET",
    path: "/v1/journal",
    body: {
      schema_version: HOUND_READ_SCHEMA,
      request_id: requestId,
      producer: {
        owner_id: config.producerOwnerId,
        capability: "journal.query",
        run_id: config.producerRunId,
      },
      requested_access: config.requestedAccess,
      policy_id: config.policyId,
      operation: { name: "journal.query", payload },
    },
  };
  const raw = Buffer.from(canonicalJson(request), "utf8");
  if (raw.byteLength > MAX_HOUND_FRAME_BYTES) throw new LedgerUnavailableError();
  const frame = Buffer.allocUnsafe(raw.byteLength + 4);
  frame.writeUInt32BE(raw.byteLength, 0);
  raw.copy(frame, 4);
  return parsePage(
    await responseFrame(config.socketPath, frame, config.timeoutMs ?? 1_000),
    requestId,
  );
}
