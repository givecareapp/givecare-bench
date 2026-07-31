import { Editor } from "@tiptap/core";
import { Markdown } from "@tiptap/markdown";
import StarterKit from "@tiptap/starter-kit";
import "./workpad.css";

type ActivityEvent = {
  actor?: { id?: string; kind?: string; role?: string };
  base_sha?: string;
  doc_id?: string;
  event_id?: string;
  note?: string;
  result_sha?: string;
  source_refs?: string[];
  ts?: string;
  verb?: string;
};

type DocumentState = {
  activity: ActivityEvent[];
  actor: { id: string; role: string };
  can_edit: boolean;
  doc_id: string;
  markdown: string;
  sha: string;
};

type SaveResult = {
  event: ActivityEvent | null;
  markdown?: string;
  merged?: boolean;
  saved?: boolean;
  sha: string;
};

const root = document.querySelector<HTMLElement>("#workpad-app");
if (!root) throw new Error("Workpad root is missing.");
const app: HTMLElement = root;

const mode = app.dataset.mode ?? "locked";
if (mode !== "locked") void start();

async function start() {
  renderShell();

  const state =
    mode === "demo"
      ? await loadDemoState()
      : await requestJSON<DocumentState>("/workpad/api/document");

  let baseSha = state.sha;
  let activity = state.activity;
  let sourceMode = false;
  let saveTimer: number | undefined;
  let saveInFlight: Promise<boolean> | null = null;
  let dirty = false;

  const editorHost = required<HTMLElement>("#editor");
  const source = required<HTMLTextAreaElement>("#source-editor");
  const trail = required<HTMLElement>("#trail");
  const trailCount = required<HTMLElement>("#trail-count");
  const actorLabel = required<HTMLElement>("#actor-label");
  const noteForm = required<HTMLFormElement>("#note-form");
  const noteInput = required<HTMLTextAreaElement>("#note-input");
  const editability = mode === "demo" || state.can_edit;

  source.readOnly = !editability;
  noteInput.disabled = !editability;
  noteForm.hidden = !editability;
  document.body.classList.toggle("read-only", !editability);

  actorLabel.textContent =
    mode === "demo" ? "Local demo" : `${state.actor.id} · ${state.actor.role}`;

  const editor = new Editor({
    element: editorHost,
    extensions: [
      StarterKit.configure({
        link: {
          autolink: true,
          defaultProtocol: "https",
          openOnClick: false,
        },
      }),
      Markdown.configure({
        indentation: { style: "space", size: 2 },
        markedOptions: { gfm: true },
      }),
    ],
    content: state.markdown,
    contentType: "markdown",
    editable: editability,
    editorProps: {
      attributes: {
        "aria-label": "Shared Workpad document",
        spellcheck: "true",
      },
    },
    onUpdate: ({ editor: current }) => {
      source.value = current.getMarkdown();
      dirty = true;
      setStatus("Unsaved", "dirty");
      scheduleSave();
      updateToolbar();
    },
    onSelectionUpdate: updateToolbar,
  });

  source.value = state.markdown;
  renderRevision();
  renderActivity();
  updateToolbar();
  setStatus(mode === "demo" ? "Saved locally" : "Saved", "saved");

  document.querySelectorAll<HTMLButtonElement>("[data-command]").forEach((button) => {
    button.addEventListener("click", () => runCommand(button.dataset.command ?? ""));
  });

  required<HTMLButtonElement>("#source-toggle").addEventListener("click", () => {
    sourceMode = !sourceMode;
    if (sourceMode) {
      source.value = editor.getMarkdown();
      editorHost.hidden = true;
      source.hidden = false;
      required("#source-toggle").setAttribute("aria-pressed", "true");
      source.focus();
    } else if (editability) {
      editor.commands.setContent(editor.markdown!.parse(source.value), {
        emitUpdate: false,
      });
      source.hidden = true;
      editorHost.hidden = false;
      required("#source-toggle").setAttribute("aria-pressed", "false");
      dirty = true;
      setStatus("Unsaved", "dirty");
      scheduleSave();
      editor.commands.focus();
    } else {
      source.hidden = true;
      editorHost.hidden = false;
      required("#source-toggle").setAttribute("aria-pressed", "false");
      editor.commands.focus();
    }
    updateToolbar();
  });

  source.addEventListener("input", () => {
    dirty = true;
    setStatus("Unsaved", "dirty");
    scheduleSave();
  });

  const trailToggle = required<HTMLButtonElement>("#trail-toggle");
  const trailClose = required<HTMLButtonElement>("#trail-close");

  function closeTrail() {
    document.body.classList.remove("trail-open");
    trailToggle.setAttribute("aria-expanded", "false");
    trail.setAttribute("aria-hidden", "true");
    trail.inert = true;
    trailToggle.focus();
  }

  function openTrail() {
    trail.inert = false;
    trail.setAttribute("aria-hidden", "false");
    document.body.classList.add("trail-open");
    trailToggle.setAttribute("aria-expanded", "true");
    trailClose.focus();
  }

  trailToggle.addEventListener("click", () => {
    if (document.body.classList.contains("trail-open")) closeTrail();
    else openTrail();
  });

  trailClose.addEventListener("click", closeTrail);
  required<HTMLElement>("#trail-scrim").addEventListener("click", closeTrail);
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && document.body.classList.contains("trail-open")) {
      closeTrail();
    }
  });

  required<HTMLButtonElement>("#reload-document").addEventListener("click", () => {
    window.open(window.location.href, "_blank", "noopener,noreferrer");
  });

  const brand = required<HTMLAnchorElement>(".brand");
  brand.addEventListener("click", async (event) => {
    if (!hasPendingSave()) return;
    event.preventDefault();
    const destination = brand.href;
    if (await save()) window.location.assign(destination);
  });

  document.querySelector<HTMLButtonElement>("#logout-button")?.addEventListener(
    "click",
    async (event) => {
      const button = event.currentTarget as HTMLButtonElement;
      if (hasPendingSave() && !(await save())) return;
      button.disabled = true;
      setStatus("Signing out…", "saving");
      try {
        await requestJSON<{ logged_out: boolean }>("/workpad/api/logout", {
          method: "POST",
          headers: writeHeaders(),
        });
        window.location.assign("/workpad");
      } catch (error) {
        button.disabled = false;
        setStatus("Couldn’t sign out", "error");
        console.error(error);
      }
    },
  );

  window.addEventListener("beforeunload", (event) => {
    if (!hasPendingSave()) return;
    event.preventDefault();
    event.returnValue = "";
  });

  noteForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const note = noteInput.value.trim();
    if (!note) return;
    setStatus("Adding note…", "saving");
    try {
      const result =
        mode === "demo"
          ? await addDemoNote(baseSha, note)
          : await requestJSON<SaveResult>("/workpad/api/note", {
              method: "POST",
              headers: writeHeaders(),
              body: JSON.stringify({ base_sha: baseSha, note }),
            });
      if (result.event) activity = [result.event, ...activity];
      noteInput.value = "";
      renderActivity();
      setStatus("Note added", "saved");
    } catch (error) {
      handleWriteError(error);
    }
  });

  function runCommand(command: string) {
    if (!editability || sourceMode) return;
    const chain = editor.chain().focus();
    switch (command) {
      case "paragraph":
        chain.setParagraph().run();
        break;
      case "h1":
        chain.toggleHeading({ level: 1 }).run();
        break;
      case "h2":
        chain.toggleHeading({ level: 2 }).run();
        break;
      case "bold":
        chain.toggleBold().run();
        break;
      case "italic":
        chain.toggleItalic().run();
        break;
      case "strike":
        chain.toggleStrike().run();
        break;
      case "code":
        chain.toggleCode().run();
        break;
      case "bullet":
        chain.toggleBulletList().run();
        break;
      case "ordered":
        chain.toggleOrderedList().run();
        break;
      case "quote":
        chain.toggleBlockquote().run();
        break;
      case "rule":
        chain.setHorizontalRule().run();
        break;
      case "undo":
        chain.undo().run();
        break;
      case "redo":
        chain.redo().run();
        break;
    }
  }

  function updateToolbar() {
    const states: Record<string, boolean> = {
      paragraph: editor.isActive("paragraph"),
      h1: editor.isActive("heading", { level: 1 }),
      h2: editor.isActive("heading", { level: 2 }),
      bold: editor.isActive("bold"),
      italic: editor.isActive("italic"),
      strike: editor.isActive("strike"),
      code: editor.isActive("code"),
      bullet: editor.isActive("bulletList"),
      ordered: editor.isActive("orderedList"),
      quote: editor.isActive("blockquote"),
    };
    document.querySelectorAll<HTMLButtonElement>("[data-command]").forEach((button) => {
      button.setAttribute(
        "aria-pressed",
        String(Boolean(states[button.dataset.command ?? ""])),
      );
      button.disabled = !editability || sourceMode;
    });
  }

  function scheduleSave() {
    if (!editability) return;
    window.clearTimeout(saveTimer);
    if (saveInFlight) return;
    saveTimer = window.setTimeout(() => void save(), 700);
  }

  function hasPendingSave() {
    return dirty || saveInFlight !== null;
  }

  async function save(): Promise<boolean> {
    window.clearTimeout(saveTimer);
    if (saveInFlight) return saveInFlight;
    if (!dirty) return true;

    const drain = (async () => {
      while (dirty) {
        const markdown = sourceMode ? source.value : editor.getMarkdown();
        dirty = false;
        setStatus("Saving…", "saving");
        try {
          const result =
            mode === "demo"
              ? await saveDemo(baseSha, markdown)
              : await requestJSON<SaveResult>("/workpad/api/document", {
                  method: "PUT",
                  headers: writeHeaders(),
                  body: JSON.stringify({ base_sha: baseSha, markdown, note: "" }),
                });
          baseSha = result.sha;
          if (result.event) activity = [result.event, ...activity];
          if (result.merged && !dirty && result.markdown !== undefined) {
            editor.commands.setContent(editor.markdown!.parse(result.markdown), {
              emitUpdate: false,
            });
            source.value = result.markdown;
          }
          renderRevision();
          renderActivity();
          if (!dirty) {
            setStatus(
              result.merged
                ? "Merged"
                : result.saved === false
                  ? "No changes"
                  : mode === "demo"
                    ? "Saved locally"
                    : "Saved",
              "saved",
            );
          }
        } catch (error) {
          dirty = true;
          handleWriteError(error);
          return false;
        }
      }
      return true;
    })();

    saveInFlight = drain;
    try {
      return await drain;
    } finally {
      if (saveInFlight === drain) saveInFlight = null;
    }
  }

  function handleWriteError(error: unknown) {
    if (error instanceof RequestError && error.status === 409) {
      document.body.classList.add("conflicted");
      setStatus("Newer revision available", "conflict");
      return;
    }
    setStatus("Couldn’t save", "error");
    console.error(error);
  }

  function writeHeaders(): Record<string, string> {
    return {
      "Content-Type": "application/json",
      "X-Workpad-CSRF": app.dataset.csrf ?? "",
    };
  }

  function renderRevision() {
    required("#revision").textContent = `rev ${baseSha.slice(0, 8)}`;
  }

  function renderActivity() {
    trailCount.textContent = String(activity.length);
    const list = required<HTMLElement>("#activity-list");
    const previousTop = list.querySelector(".activity-item")?.getAttribute("data-event");
    list.replaceChildren();
    if (activity.length === 0) {
      const empty = document.createElement("p");
      empty.className = "activity-empty";
      empty.textContent = "The trail begins with your first save or note.";
      list.append(empty);
      return;
    }
    let first = true;
    for (const event of activity) {
      const item = document.createElement("article");
      item.className = "activity-item";
      if (event.event_id) item.setAttribute("data-event", event.event_id);
      if (first && previousTop && event.event_id && event.event_id !== previousTop) {
        item.classList.add("is-new");
      }
      first = false;

      const marker = document.createElement("span");
      marker.className = `activity-marker ${event.verb === "noted" ? "is-note" : ""}`;

      const header = document.createElement("div");
      header.className = "activity-header";
      const actor = document.createElement("strong");
      actor.textContent = event.actor?.id ?? "Unknown actor";
      const time = document.createElement("time");
      time.dateTime = event.ts ?? "";
      time.textContent = formatTime(event.ts);
      header.append(actor, time);

      const verb = document.createElement("p");
      verb.className = "activity-verb";
      verb.textContent =
        event.verb === "noted"
          ? "left a note"
          : `saved ${shortSha(event.base_sha)} → ${shortSha(event.result_sha)}`;

      item.append(marker, header, verb);
      if (event.note) {
        const note = document.createElement("p");
        note.className = "activity-note";
        note.textContent = event.note;
        item.append(note);
      }
      list.append(item);
    }
  }

  if (mode === "private") {
    const liveEvents = new EventSource("/workpad/api/events");
    liveEvents.addEventListener("change", (event) => {
      let sha: string | undefined;
      try {
        sha = (JSON.parse((event as MessageEvent).data) as { sha?: string }).sha;
      } catch {
        return;
      }
      if (!sha || sha === baseSha) return;
      if (dirty) {
        document.body.classList.add("conflicted");
        setStatus("Newer revision available", "conflict");
        return;
      }
      if (saveInFlight) return;
      void applyRemoteDocument();
    });
  }

  async function applyRemoteDocument() {
    try {
      const fresh = await requestJSON<DocumentState>("/workpad/api/document");
      if (dirty || saveInFlight) return;
      const paper = document.querySelector(".paper");
      paper?.classList.add("remote-swap");
      baseSha = fresh.sha;
      activity = fresh.activity;
      editor.commands.setContent(editor.markdown!.parse(fresh.markdown), {
        emitUpdate: false,
      });
      source.value = fresh.markdown;
      renderRevision();
      renderActivity();
      const from = fresh.activity[0]?.actor?.id;
      setStatus(from ? `Updated · ${from}` : "Updated", "saved");
      window.setTimeout(() => paper?.classList.remove("remote-swap"), 220);
    } catch {
      // Ignore transient fetch errors; EventSource auto-reconnects and the
      // next change event retries.
    }
  }
}

function renderShell() {
  app.innerHTML = `
    <header class="app-bar">
      <a class="brand" href="/" aria-label="GiveCare Review home">
        <span class="brand-mark" aria-hidden="true">+</span>
        <span>GiveCare</span>
      </a>
      <span class="bar-rule" aria-hidden="true"></span>
      <div class="document-identity">
        <span class="document-name">Shared workpad</span>
        <span class="mode-badge">${mode === "demo" ? "browser demo" : "private"}</span>
      </div>
      <div class="save-state">
        <span class="save-dot" aria-hidden="true"></span>
        <span id="save-status" role="status" aria-live="polite">Loading…</span>
        <span id="revision"></span>
      </div>
      <div class="bar-actions">
        <span id="actor-label" class="actor-label"></span>
        <button id="trail-toggle" class="trail-button" type="button"
          aria-controls="trail" aria-expanded="false">
          Trail <span id="trail-count" class="trail-count">0</span>
        </button>
      </div>
    </header>

    <div class="conflict-banner" role="alert">
      This page changed somewhere else. Your draft stays in this tab.
      <button id="reload-document" type="button">Open latest in new tab</button>
    </div>

    <main class="workspace">
      <section class="page-wrap" aria-label="Workpad document">
        <nav class="format-bar" aria-label="Text formatting">
          <button type="button" data-command="paragraph"
            title="Paragraph">Text</button>
          <button type="button" data-command="h1"
            title="Heading 1">H1</button>
          <button type="button" data-command="h2"
            title="Heading 2">H2</button>
          <span class="tool-separator" aria-hidden="true"></span>
          <button type="button" data-command="bold" aria-label="Bold"
            title="Bold"><strong>B</strong></button>
          <button type="button" data-command="italic" aria-label="Italic"
            title="Italic"><em>I</em></button>
          <button type="button" data-command="strike" aria-label="Strikethrough"
            title="Strikethrough"><s>S</s></button>
          <button type="button" data-command="code" aria-label="Inline code"
            title="Inline code">&lt;/&gt;</button>
          <span class="tool-separator" aria-hidden="true"></span>
          <button type="button" data-command="bullet"
            title="Bullet list">• List</button>
          <button type="button" data-command="ordered"
            title="Numbered list">1. List</button>
          <button type="button" data-command="quote" aria-label="Block quote"
            title="Block quote">“ ”</button>
          <button type="button" data-command="rule" aria-label="Divider"
            title="Divider">―</button>
          <span class="tool-spacer"></span>
          <button id="source-toggle" type="button" aria-label="Toggle Markdown source"
            aria-pressed="false">Markdown</button>
          <button type="button" data-command="undo" aria-label="Undo"
            title="Undo">↶</button>
          <button type="button" data-command="redo" aria-label="Redo"
            title="Redo">↷</button>
        </nav>

        <div class="paper">
          <div class="margin-rule" aria-hidden="true"></div>
          <div id="editor"></div>
          <textarea id="source-editor" hidden spellcheck="false"
            aria-label="Markdown source"></textarea>
        </div>
        <p class="document-footnote">
          Markdown is the readable projection. Each save leaves an exact revision handle.
        </p>
      </section>

      <div id="trail-scrim" class="trail-scrim" aria-hidden="true"></div>
      <aside id="trail" class="trail" inert aria-hidden="true"
        aria-label="Provenance trail">
        <div class="trail-heading">
          <div>
            <p class="eyebrow">Provenance</p>
            <h2>Document trail</h2>
          </div>
          <button id="trail-close" class="icon-button" type="button"
            aria-label="Close document trail">×</button>
        </div>
        <p class="trail-intro">
          Human and agent contributions share one chronology. Notes preserve reasoning;
          saves preserve exact before and after revisions.
        </p>
        ${
          mode === "private"
            ? '<button id="logout-button" class="logout-button" type="button">' +
              "Sign out of this workpad</button>"
            : ""
        }
        <form id="note-form" class="note-form">
          <label for="note-input">Leave context underneath</label>
          <textarea id="note-input" maxlength="4000"
            placeholder="A decision, question, or handoff…"></textarea>
          <button type="submit">Add to trail</button>
        </form>
        <div id="activity-list" class="activity-list"></div>
      </aside>
    </main>
  `;
}

async function loadDemoState(): Promise<DocumentState> {
  const seed = await requestJSON<DocumentState>("/workpad/api/demo");
  const markdown = localStorage.getItem("givecare.workpad.demo.markdown") ?? seed.markdown;
  const rawActivity = localStorage.getItem("givecare.workpad.demo.activity");
  let activity: ActivityEvent[] = [];
  if (rawActivity) {
    try {
      const parsed = JSON.parse(rawActivity);
      if (Array.isArray(parsed)) activity = parsed;
    } catch {
      localStorage.removeItem("givecare.workpad.demo.activity");
    }
  }
  return { ...seed, markdown, sha: await digest(markdown), activity };
}

async function saveDemo(baseSha: string, markdown: string): Promise<SaveResult> {
  const resultSha = await digest(markdown);
  if (resultSha === baseSha) return { event: null, saved: false, sha: baseSha };
  const event: ActivityEvent = {
    actor: { id: "you", kind: "human", role: "demo" },
    base_sha: baseSha,
    doc_id: "shared-workpad",
    event_id: `evt:demo:${Date.now()}`,
    note: "",
    result_sha: resultSha,
    source_refs: [],
    ts: new Date().toISOString(),
    verb: "edited",
  };
  localStorage.setItem("givecare.workpad.demo.markdown", markdown);
  const activity = readDemoActivity();
  activity.unshift(event);
  localStorage.setItem(
    "givecare.workpad.demo.activity",
    JSON.stringify(activity.slice(0, 200)),
  );
  return { event, saved: true, sha: resultSha };
}

async function addDemoNote(baseSha: string, note: string): Promise<SaveResult> {
  const event: ActivityEvent = {
    actor: { id: "you", kind: "human", role: "demo" },
    base_sha: baseSha,
    doc_id: "shared-workpad",
    event_id: `evt:demo:${Date.now()}`,
    note,
    result_sha: baseSha,
    ts: new Date().toISOString(),
    verb: "noted",
  };
  const activity = readDemoActivity();
  activity.unshift(event);
  localStorage.setItem(
    "givecare.workpad.demo.activity",
    JSON.stringify(activity.slice(0, 200)),
  );
  return { event, sha: baseSha };
}

function readDemoActivity(): ActivityEvent[] {
  try {
    const parsed = JSON.parse(
      localStorage.getItem("givecare.workpad.demo.activity") ?? "[]",
    );
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

async function digest(markdown: string): Promise<string> {
  const bytes = new TextEncoder().encode(markdown);
  const hash = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(hash))
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}

function setStatus(message: string, state: string) {
  const element = required<HTMLElement>("#save-status");
  element.textContent = message;
  element.closest(".save-state")?.setAttribute("data-state", state);
}

function shortSha(value?: string): string {
  return value ? value.slice(0, 8) : "initial";
}

function formatTime(value?: string): string {
  if (!value) return "unknown time";
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return value;
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function required<T extends Element = Element>(selector: string): T {
  const element = document.querySelector<T>(selector);
  if (!element) throw new Error(`Missing Workpad element: ${selector}`);
  return element;
}

class RequestError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function requestJSON<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    credentials: "same-origin",
    ...init,
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new RequestError(
      typeof payload.error === "string"
        ? payload.error
        : `Request failed (${response.status})`,
      response.status,
    );
  }
  return payload as T;
}
