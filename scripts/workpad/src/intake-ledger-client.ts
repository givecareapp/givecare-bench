import "./intake-ledger.css";
import { LedgerPagination } from "./intake-ledger-pagination.ts";

type Lineage = { relation: string; record_id: string; lead_id: string };
type Row = {
  entry_id: string;
  appended_at: string;
  producer: { owner_id: string; capability: string; run_id: string };
  operation: { capability: string; artifact_kind: string };
  source: { provider: string };
  classification: { outcome: string; evidence_status: string };
  artifact: { record_id: string };
  lineage: Lineage;
  access: string;
};
type Page = {
  status: "ready";
  projection: { schema_version: "houndd.intake-ledger.v1"; integrity: "verified"; high_watermark: string };
  rows: Row[];
  cursor?: string;
};

const root = document.querySelector<HTMLElement>("#intake-ledger-app");
if (!root) throw new Error("Missing intake-ledger root.");
const app: HTMLElement = root;

function element<K extends keyof HTMLElementTagNameMap>(
  name: K,
  className?: string,
  text?: string,
): HTMLElementTagNameMap[K] {
  const item = document.createElement(name);
  if (className) item.className = className;
  if (text !== undefined) item.textContent = text;
  return item;
}

function shortId(value: string): string {
  return value.slice(0, 12);
}

function displayTime(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.valueOf())
    ? "Unknown time"
    : new Intl.DateTimeFormat(undefined, {
        dateStyle: "medium",
        timeStyle: "short",
        timeZone: "UTC",
      }).format(date) + " UTC";
}

function statusStrip(projection: Page["projection"]): HTMLElement {
  const strip = element("div", "ledger-status", "");
  strip.setAttribute("role", "status");
  const integrity = element("span", "ledger-chip ledger-chip--good", "Journal integrity: verified");
  const ready = element("span", "ledger-chip ledger-chip--good", "Service readiness: ready");
  const hwm = element("span", "ledger-hwm", "Snapshot: " + shortId(projection.high_watermark));
  hwm.title = "Opaque snapshot high-watermark commitment";
  strip.append(integrity, ready, hwm);
  return strip;
}

function identifier(label: string, value: string): HTMLElement {
  const cell = element("span", "ledger-id");
  const labelElement = element("span", "ledger-id__label", label);
  const valueElement = element("code", "ledger-id__value", shortId(value));
  valueElement.title = value;
  cell.append(labelElement, valueElement);
  return cell;
}

function rowElement(value: Row): HTMLElement {
  const row = element("article", "ledger-row");
  const time = element("time", "ledger-time", displayTime(value.appended_at));
  time.dateTime = value.appended_at;
  const source = element("span", "ledger-source", value.source.provider);
  const operation = element(
    "span",
    "ledger-operation",
    `${value.operation.capability} · ${value.operation.artifact_kind}`,
  );
  const outcome = element(
    "span",
    "ledger-outcome",
    `${value.classification.outcome} · ${value.classification.evidence_status}`,
  );
  const producer = element(
    "span",
    "ledger-producer",
    `${value.producer.owner_id} / ${value.producer.capability} / ${value.producer.run_id}`,
  );
  const meta = element("div", "ledger-meta");
  meta.append(source, operation, outcome, producer);
  const ids = element("div", "ledger-identifiers");
  ids.append(identifier("Event", value.entry_id), identifier("Record", value.artifact.record_id));
  const lineage = element("span", "ledger-lineage");
  lineage.append(
    element("span", "ledger-lineage__relation", value.lineage.relation),
    identifier("Lineage record", value.lineage.record_id),
    identifier("Lead", value.lineage.lead_id),
  );
  ids.append(lineage);
  ids.append(element("span", "ledger-access", value.access));
  row.append(time, meta, ids);
  return row;
}

function button(label: string, listener: () => void): HTMLButtonElement {
  const item = element("button", "ledger-load-more", label);
  item.type = "button";
  item.addEventListener("click", listener);
  return item;
}

async function fetchPage(cursor?: string): Promise<Page> {
  const url = new URL("/workpad/api/intake-ledger", window.location.origin);
  if (cursor) url.searchParams.set("cursor", cursor);
  const response = await fetch(url, { credentials: "same-origin", headers: { Accept: "application/json" } });
  if (!response.ok) throw new Error("unavailable");
  return (await response.json()) as Page;
}

let nextCursor: string | undefined;
const pagination = new LedgerPagination();

async function load(cursor?: string): Promise<void> {
  const generation = pagination.begin();
  if (generation === null) return;
  app.querySelector(".ledger-load-more")?.remove();
  app.setAttribute("aria-busy", "true");
  const existing = app.querySelector<HTMLElement>(".ledger-list");
  const pending = element("p", "ledger-loading", cursor ? "Loading older entries…" : "Loading verified intake ledger…");
  app.append(pending);
  try {
    const page = await fetchPage(cursor);
    if (!pagination.isCurrent(generation)) {
      pending.remove();
      return;
    }
    if (!pagination.accept(generation, cursor !== undefined, page.rows)) {
      pending.remove();
      throw new Error("invalid ledger page");
    }
    if (!cursor) {
      app.replaceChildren();
      const header = element("header", "ledger-header");
      header.append(
        element("p", "ledger-kicker", "GiveCare · private review"),
        element("h1", "ledger-title", "Intake ledger"),
        element("p", "ledger-intro", "A read-only chronology of authorized Hound journal entries."),
      );
      app.append(header, statusStrip(page.projection));
    }
    let list = existing ?? app.querySelector<HTMLElement>(".ledger-list");
    if (!list) {
      list = element("section", "ledger-list");
      list.setAttribute("aria-label", "Chronological intake ledger");
      app.append(list);
    }
    pending.remove();
    if (page.rows.length === 0 && !cursor) {
      list.append(element("p", "ledger-empty", "No authorized entries in this snapshot."));
    } else {
      for (const value of page.rows) list.append(rowElement(value));
    }
    nextCursor = page.cursor;
    if (nextCursor) app.append(button("Load more", () => void load(nextCursor)));
  } catch {
    pending.remove();
    if (!cursor) {
      app.replaceChildren();
      const panel = element("section", "ledger-unavailable");
      panel.setAttribute("role", "status");
      panel.append(
        element("p", "ledger-kicker", "GiveCare · private review"),
        element("h1", "ledger-title", "Intake ledger unavailable"),
        element("p", "ledger-intro", "The verified journal cannot be read right now. No cached entries are shown."),
        button("Try again", () => void load()),
      );
      app.append(panel);
    } else {
      const message = element("p", "ledger-load-error", "Older entries could not be loaded. Try again.");
      app.append(message, button("Try again", () => void load(cursor)));
    }
  } finally {
    pagination.finish(generation);
    app.setAttribute("aria-busy", "false");
  }
}

void load();
