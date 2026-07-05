#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["flask>=3.0"]
# ///
"""Gold-card human-review server (self-contained; run via ``uv run``).

A single-file Flask app for the blind gold-card annotation session. It serves
the batch built by ``export_batch.py`` (``internal/review/batch.json``), records
verdicts to SQLite (``internal/review/reviews.db``), and exports the collected
labels in the dual-annotator schema ``invisiblebench.evaluation.calibration``
ingests.

Run:
    uv run --script scripts/review_ui/app.py           # binds 127.0.0.1:3090
    REVIEW_PORT=3090 uv run --script scripts/review_ui/app.py

Config (env): REVIEW_PORT (default 3090), REVIEW_HOST (default 127.0.0.1),
REVIEW_DIR (default <repo>/internal/review). Tokens live in
``<REVIEW_DIR>/tokens.txt`` (gitignored) and map a URL token to a reviewer
(id + calibration slot + shuffle seed) or the admin surface.

No prior label is ever shown: blindness is enforced upstream by export_batch.
Every response carries ``X-Robots-Tag: noindex``.
"""

from __future__ import annotations

import json
import os
import random
import re
import sqlite3
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any

from flask import Flask, Response, abort, g, jsonify, request

REPO_ROOT = Path(__file__).resolve().parents[2]
REVIEW_DIR = Path(os.environ.get("REVIEW_DIR", REPO_ROOT / "internal" / "review"))
BATCH_PATH = REVIEW_DIR / "batch.json"
DB_PATH = REVIEW_DIR / "reviews.db"
TOKENS_PATH = REVIEW_DIR / "tokens.txt"
WALKTHROUGH_PATH = (
    REPO_ROOT / "internal" / "evals" / "verifier" / "golden_set" / "annotator_walkthrough.md"
)

VERDICTS = ("FAIL", "PASS", "UNCLEAR", "NOT_APPLICABLE")
RATIONALE_REQUIRED = frozenset({"FAIL", "UNCLEAR"})

app = Flask(__name__)


# --------------------------------------------------------------------------- #
# Data loading (batch, tokens) — tiny files, re-read per request so a new token
# or a re-export is picked up without a service restart.
# --------------------------------------------------------------------------- #
def load_batch() -> list[dict[str, Any]]:
    return json.loads(BATCH_PATH.read_text(encoding="utf-8"))


def load_tokens() -> dict[str, dict[str, str]]:
    """Parse tokens.txt into ``{token: {role, id, slot, seed, ...}}``."""
    tokens: dict[str, dict[str, str]] = {}
    if not TOKENS_PATH.exists():
        return tokens
    for line in TOKENS_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        fields: dict[str, str] = {}
        for part in line.split():
            if "=" in part:
                key, value = part.split("=", 1)
                fields[key] = value
        token = fields.get("token")
        if token:
            tokens[token] = fields
    return tokens


def resolve_token(token: str) -> dict[str, str]:
    entry = load_tokens().get(token)
    if entry is None:
        abort(404)
    return entry


def shuffle_order(n: int, seed: int) -> list[int]:
    """Deterministic per-seed order — identical to export_batch.shuffle_order."""
    order = list(range(n))
    random.Random(seed).shuffle(order)
    return order


def reviewer_order(entry: dict[str, str], batch: list[dict[str, Any]]) -> list[int]:
    seed = int(entry.get("seed", "0"))
    return shuffle_order(len(batch), seed)


# --------------------------------------------------------------------------- #
# SQLite
# --------------------------------------------------------------------------- #
def get_db() -> sqlite3.Connection:
    if "db" not in g:
        REVIEW_DIR.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS annotations (
                reviewer_id TEXT NOT NULL,
                card_id     TEXT NOT NULL,
                verdict     TEXT,
                rationale   TEXT,
                note        TEXT,
                flagged     INTEGER NOT NULL DEFAULT 0,
                created_at  TEXT NOT NULL,
                updated_at  TEXT NOT NULL,
                PRIMARY KEY (reviewer_id, card_id)
            )
            """
        )
        conn.commit()
        g.db = conn
    return g.db


@app.teardown_appcontext
def close_db(_exc: BaseException | None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def answers_for(reviewer_id: str) -> dict[str, sqlite3.Row]:
    rows = get_db().execute(
        "SELECT * FROM annotations WHERE reviewer_id = ?", (reviewer_id,)
    ).fetchall()
    return {row["card_id"]: row for row in rows}


def is_complete(row: sqlite3.Row | None) -> bool:
    if row is None or not row["verdict"]:
        return False
    if row["verdict"] in RATIONALE_REQUIRED and not (row["rationale"] or "").strip():
        return False
    return True


# --------------------------------------------------------------------------- #
# Response headers
# --------------------------------------------------------------------------- #
@app.after_request
def set_headers(resp: Response) -> Response:
    resp.headers["X-Robots-Tag"] = "noindex, nofollow"
    resp.headers["Referrer-Policy"] = "no-referrer"
    return resp


# --------------------------------------------------------------------------- #
# Minimal, dependency-free Markdown → HTML for the annotator handbook.
# --------------------------------------------------------------------------- #
def md_to_html(md: str) -> str:
    out: list[str] = []
    in_code = False
    in_list = False

    def inline(text: str) -> str:
        text = escape(text)
        # `code`
        parts = text.split("`")
        for i in range(1, len(parts), 2):
            parts[i] = f"<code>{parts[i]}</code>"
        text = "".join(parts)
        # **bold**
        return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)

    for raw in md.splitlines():
        if raw.startswith("```"):
            if in_code:
                out.append("</pre>")
                in_code = False
            else:
                if in_list:
                    out.append("</ul>")
                    in_list = False
                out.append("<pre class='code'>")
                in_code = True
            continue
        if in_code:
            out.append(escape(raw))
            continue
        stripped = raw.strip()
        if not stripped:
            if in_list:
                out.append("</ul>")
                in_list = False
            continue
        if stripped.startswith("#"):
            if in_list:
                out.append("</ul>")
                in_list = False
            level = len(stripped) - len(stripped.lstrip("#"))
            level = min(max(level, 1), 6)
            out.append(f"<h{level + 1}>{inline(stripped.lstrip('#').strip())}</h{level + 1}>")
        elif stripped[0] in "-*" and stripped[1:2] == " ":
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{inline(stripped[2:])}</li>")
        elif stripped.startswith("|"):
            out.append(f"<div class='tablerow'>{inline(stripped)}</div>")
        else:
            out.append(f"<p>{inline(stripped)}</p>")
    if in_list:
        out.append("</ul>")
    if in_code:
        out.append("</pre>")
    return "\n".join(out)


def handbook_html() -> str:
    if not WALKTHROUGH_PATH.exists():
        return "<p>Handbook not found.</p>"
    return md_to_html(WALKTHROUGH_PATH.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# HTML rendering (server-side, inline CSS/JS — no build step)
# --------------------------------------------------------------------------- #
_STYLE = """
:root{--bg:#0f1115;--panel:#181b22;--line:#2a2f3a;--fg:#e6e9ef;--mut:#9aa4b2;
--user:#1f2a3a;--asst:#20262f;--accent:#4f8cff;--fail:#e5534b;--pass:#3fb950;
--unclear:#d29922;--na:#8b949e;--cue:#5a3d00;}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
font:15px/1.55 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
a{color:var(--accent)}
.wrap{max-width:1180px;margin:0 auto;padding:18px}
.topbar{display:flex;align-items:center;gap:16px;position:sticky;top:0;z-index:5;
background:var(--bg);padding:10px 0;border-bottom:1px solid var(--line)}
.topbar h1{font-size:16px;margin:0;font-weight:600}
.progress{flex:1;height:8px;background:var(--panel);border-radius:6px;overflow:hidden}
.progress>span{display:block;height:100%;background:var(--accent);width:0}
.count{color:var(--mut);font-size:13px;white-space:nowrap}
.grid{display:grid;grid-template-columns:1fr 360px;gap:20px;margin-top:16px}
@media(max-width:900px){.grid{grid-template-columns:1fr}}
.transcript{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:16px}
.bubble{border-radius:12px;padding:10px 14px;margin:10px 0;white-space:pre-wrap;
word-wrap:break-word;border:1px solid var(--line)}
.bubble .role{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--mut);
margin-bottom:4px}
.bubble.user{background:var(--user)}
.bubble.assistant{background:var(--asst)}
.bubble.cue{border-color:#a87700;box-shadow:0 0 0 1px #a8770055 inset;background:var(--cue)}
.side{position:sticky;top:70px;align-self:start;display:flex;flex-direction:column;gap:14px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:16px}
.card h3{margin:0 0 8px;font-size:13px;color:var(--mut);text-transform:uppercase;
letter-spacing:.05em}
.rubric b{color:var(--fg)}
.rubric .rule{margin:8px 0;padding:8px 10px;border-radius:8px;background:#12151b;
border:1px solid var(--line)}
.rule.pass{border-left:3px solid var(--pass)}
.rule.fail{border-left:3px solid var(--fail)}
.tags span{display:inline-block;font-size:11px;background:#12151b;border:1px solid var(--line);
border-radius:20px;padding:2px 9px;margin:2px 4px 2px 0;color:var(--mut)}
.verdicts{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.vbtn{padding:11px;border-radius:9px;border:1px solid var(--line);background:#12151b;
color:var(--fg);font-weight:600;cursor:pointer;font-size:14px}
.vbtn .k{color:var(--mut);font-weight:400;font-size:12px}
.vbtn[data-v=FAIL].on{background:var(--fail);border-color:var(--fail);color:#fff}
.vbtn[data-v=PASS].on{background:var(--pass);border-color:var(--pass);color:#04210c}
.vbtn[data-v=UNCLEAR].on{background:var(--unclear);border-color:var(--unclear);color:#231a00}
.vbtn[data-v=NOT_APPLICABLE].on{background:var(--na);border-color:var(--na);color:#0d0d0d}
textarea{width:100%;background:#12151b;color:var(--fg);border:1px solid var(--line);
border-radius:8px;padding:9px;font:14px/1.5 inherit;resize:vertical;min-height:64px}
label{display:block;font-size:12px;color:var(--mut);margin:10px 0 4px}
.req{color:var(--fail)}
.row{display:flex;gap:8px;align-items:center;margin-top:12px;flex-wrap:wrap}
.btn{padding:9px 14px;border-radius:8px;border:1px solid var(--line);background:#12151b;
color:var(--fg);cursor:pointer;text-decoration:none;font-size:14px}
.btn.primary{background:var(--accent);border-color:var(--accent);color:#fff}
.btn.flag.on{background:#5a1f1a;border-color:var(--fail);color:#fff}
.saved{font-size:12px;color:var(--pass);min-height:16px}
.warn{font-size:12px;color:var(--unclear);min-height:16px}
.hb{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:8px 16px;
margin-top:16px}
.hb h2,.hb h3,.hb h4{color:var(--fg)}
.hb pre.code{background:#0b0d11;border:1px solid var(--line);border-radius:8px;padding:10px;
overflow:auto;font-size:12px;white-space:pre}
.hb .tablerow{font-family:ui-monospace,Menlo,monospace;font-size:12px;color:var(--mut);
white-space:pre-wrap}
table{border-collapse:collapse;width:100%;font-size:13px}
td,th{border:1px solid var(--line);padding:6px 9px;text-align:left}
"""


def _page(title: str, body: str, script: str = "") -> Response:
    html = (
        "<!doctype html><html lang=en><head><meta charset=utf-8>"
        "<meta name=viewport content='width=device-width,initial-scale=1'>"
        "<meta name=robots content='noindex,nofollow'>"
        f"<title>{escape(title)}</title><style>{_STYLE}</style></head>"
        f"<body><div class=wrap>{body}</div>{script}</body></html>"
    )
    return Response(html, mimetype="text/html")


# --------------------------------------------------------------------------- #
# Reviewer routes
# --------------------------------------------------------------------------- #
@app.get("/health")
def health() -> Response:
    ok = BATCH_PATH.exists()
    return jsonify(status="ok" if ok else "degraded", cards=len(load_batch()) if ok else 0)


@app.get("/")
def index() -> Response:
    abort(404)


@app.get("/r/<token>")
def landing(token: str) -> Response:
    entry = resolve_token(token)
    if entry.get("role") != "reviewer":
        abort(404)
    batch = load_batch()
    answers = answers_for(entry["id"])
    order = reviewer_order(entry, batch)
    done = sum(1 for i in order if is_complete(answers.get(batch[i]["card_id"])))
    resume = 0
    for pos, i in enumerate(order):
        if not is_complete(answers.get(batch[i]["card_id"])):
            resume = pos
            break
    else:
        resume = 0
    body = (
        f"<div class=topbar><h1>Gold-card review</h1>"
        f"<div class=count>{done} / {len(batch)} complete</div></div>"
        "<p>You are grading model transcripts against a single safety check each. "
        "Read the whole window, apply the <b>human rubric</b> in the side panel "
        "(not any machine label — there are none here), and record a verdict. "
        "A rationale is required for <b>FAIL</b> and <b>UNCLEAR</b>.</p>"
        "<div class=row>"
        f"<a class='btn primary' href='/r/{escape(token)}/card/{resume}'>"
        f"{'Resume' if done else 'Begin'} review &rarr;</a></div>"
        "<div class=hb><details><summary style='cursor:pointer;padding:8px 0'>"
        "<b>Full annotation handbook</b> (open before your first pass)</summary>"
        f"{handbook_html()}</details></div>"
    )
    return _page("Gold-card review", body)


def _bubble(turn: dict[str, Any], cue_turn: int | None) -> str:
    role = turn.get("role", "assistant")
    is_cue = cue_turn is not None and turn.get("turn") == cue_turn and role == "user"
    klass = f"bubble {escape(role)}" + (" cue" if is_cue else "")
    label = f"Turn {turn.get('turn', '?')} · {escape(role)}"
    return f"<div class='{klass}'><div class=role>{label}</div>{escape(turn.get('content',''))}</div>"


@app.get("/r/<token>/card/<int:pos>")
def card_view(token: str, pos: int) -> Response:
    entry = resolve_token(token)
    if entry.get("role") != "reviewer":
        abort(404)
    batch = load_batch()
    order = reviewer_order(entry, batch)
    if pos < 0 or pos >= len(order):
        abort(404)
    card = batch[order[pos]]
    answers = answers_for(entry["id"])
    row = answers.get(card["card_id"])
    done = sum(1 for i in order if is_complete(answers.get(batch[i]["card_id"])))

    cue = card.get("cue") or {}
    cue_turn = cue.get("cue_turn")
    bubbles = "".join(_bubble(t, cue_turn) for t in card.get("turns", []))

    chk = card.get("check", {})
    rubric = (
        f"<div class=rubric><b>{escape(str(chk.get('name','')))}</b> "
        f"<span class=count>({escape(str(chk.get('severity','')))}"
        f"{' · hard fail' if chk.get('hard_fail') else ''})</span>"
        f"<div class='rule pass'><b>PASS when:</b> {escape(str(chk.get('pass_rule','')))}</div>"
        f"<div class='rule fail'><b>FAIL when:</b> {escape(str(chk.get('fail_rule','')))}</div>"
    )
    if chk.get("caregiver_benefit"):
        rubric += f"<p class=count>Why it matters: {escape(str(chk['caregiver_benefit']))}</p>"
    rubric += "</div>"

    tags = "".join(f"<span>{escape(t)}</span>" for t in card.get("source_tags", []))
    vbtns = "".join(
        f"<button class=vbtn data-v={v} type=button>"
        f"{v.replace('NOT_APPLICABLE','N/A')} <span class=k>{i + 1}</span></button>"
        for i, v in enumerate(VERDICTS)
    )
    prev_dis = "disabled" if pos == 0 else ""
    next_dis = "disabled" if pos == len(order) - 1 else ""

    state = {
        "token": token,
        "pos": pos,
        "total": len(order),
        "done": done,
        "card_id": card["card_id"],
        "verdict": row["verdict"] if row else "",
        "rationale": (row["rationale"] if row else "") or "",
        "note": (row["note"] if row else "") or "",
        "flagged": bool(row["flagged"]) if row else False,
    }

    body = (
        "<div class=topbar><h1>Gold-card review</h1>"
        "<div class=progress><span id=bar></span></div>"
        f"<div class=count id=count>{done} / {len(order)}</div></div>"
        "<div class=grid>"
        f"<div class=transcript>{bubbles}</div>"
        "<div class=side>"
        f"<div class=card><h3>Check rubric</h3>{rubric}<div class=tags>{tags}</div></div>"
        "<div class=card><h3>Your verdict</h3>"
        f"<div class=verdicts>{vbtns}</div>"
        "<label>Rationale <span class=req id=ratreq></span></label>"
        "<textarea id=rationale placeholder='Why? (required for FAIL / UNCLEAR)'></textarea>"
        "<label>Note (optional)</label>"
        "<textarea id=note placeholder='Anything else worth recording'></textarea>"
        "<div class=row>"
        "<button class='btn flag' id=flag type=button>&#9873; Flag bad data</button></div>"
        "<div class=saved id=saved></div><div class=warn id=warn></div>"
        "<div class=row>"
        f"<a class='btn' id=prev href='/r/{escape(token)}/card/{pos - 1}' {prev_dis}>&larr; Prev</a>"
        f"<a class='btn primary' id=next href='/r/{escape(token)}/card/{pos + 1}' {next_dis}>"
        "Next &rarr;</a>"
        f"<a class='btn' href='/r/{escape(token)}'>Overview</a>"
        "</div><p class=count>Keys: 1 FAIL · 2 PASS · 3 UNCLEAR · 4 N/A · &larr;/&rarr; navigate</p>"
        "</div></div></div>"
    )
    script = f"<script>window.__S={json.dumps(state)};{_CARD_JS}</script>"
    return _page(f"Card {pos + 1}", body, script)


_CARD_JS = r"""
const S = window.__S;
const $ = (id) => document.getElementById(id);
const rat = $('rationale'), note = $('note'), warn = $('warn'), saved = $('saved');
let verdict = S.verdict, flagged = S.flagged;
rat.value = S.rationale; note.value = S.note;
function paint(){
  document.querySelectorAll('.vbtn').forEach(b=>b.classList.toggle('on', b.dataset.v===verdict));
  $('flag').classList.toggle('on', flagged);
  const need = (verdict==='FAIL'||verdict==='UNCLEAR');
  $('ratreq').textContent = need ? '(required)' : '';
  warn.textContent = (need && !rat.value.trim()) ? 'Rationale required to complete this card.' : '';
}
async function save(){
  saved.textContent='Saving…';
  try{
    const r = await fetch(`/r/${S.token}/save`,{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({card_id:S.card_id,verdict,rationale:rat.value,note:note.value,flagged})});
    const d = await r.json();
    saved.textContent = d.complete ? 'Saved ✓' : 'Saved (incomplete)';
    if(typeof d.done==='number'){ $('count').textContent = d.done+' / '+S.total;
      $('bar').style.width = (100*d.done/S.total)+'%'; }
  }catch(e){ saved.textContent='Save failed — retry'; }
}
document.querySelectorAll('.vbtn').forEach(b=>b.addEventListener('click',()=>{
  verdict=b.dataset.v; paint(); save();
}));
$('flag').addEventListener('click',()=>{ flagged=!flagged; paint(); save(); });
let t; function debounced(){ clearTimeout(t); t=setTimeout(save,600); }
rat.addEventListener('input',()=>{paint();debounced();});
note.addEventListener('input',debounced);
rat.addEventListener('blur',save); note.addEventListener('blur',save);
document.addEventListener('keydown',(e)=>{
  if(e.target.tagName==='TEXTAREA') return;
  const map={'1':'FAIL','2':'PASS','3':'UNCLEAR','4':'NOT_APPLICABLE'};
  if(map[e.key]){ verdict=map[e.key]; paint(); save(); e.preventDefault(); }
  else if(e.key==='ArrowRight' && S.pos<S.total-1){ location.href=`/r/${S.token}/card/${S.pos+1}`; }
  else if(e.key==='ArrowLeft' && S.pos>0){ location.href=`/r/${S.token}/card/${S.pos-1}`; }
});
$('bar').style.width = (100*S.done/S.total)+'%';
paint();
"""


@app.post("/r/<token>/save")
def save(token: str) -> Response:
    entry = resolve_token(token)
    if entry.get("role") != "reviewer":
        abort(404)
    payload = request.get_json(silent=True) or {}
    card_id = str(payload.get("card_id", ""))
    if not any(card_id == c["card_id"] for c in load_batch()):
        abort(400)
    verdict = payload.get("verdict") or None
    if verdict is not None and verdict not in VERDICTS:
        abort(400)
    rationale = (payload.get("rationale") or "").strip()
    note = (payload.get("note") or "").strip()
    flagged = 1 if payload.get("flagged") else 0

    db = get_db()
    now = _now()
    db.execute(
        """
        INSERT INTO annotations (reviewer_id, card_id, verdict, rationale, note, flagged,
                                 created_at, updated_at)
        VALUES (?,?,?,?,?,?,?,?)
        ON CONFLICT(reviewer_id, card_id) DO UPDATE SET
            verdict=excluded.verdict, rationale=excluded.rationale, note=excluded.note,
            flagged=excluded.flagged, updated_at=excluded.updated_at
        """,
        (entry["id"], card_id, verdict, rationale, note, flagged, now, now),
    )
    db.commit()

    row = db.execute(
        "SELECT * FROM annotations WHERE reviewer_id=? AND card_id=?", (entry["id"], card_id)
    ).fetchone()
    answers = answers_for(entry["id"])
    done = sum(1 for c in load_batch() if is_complete(answers.get(c["card_id"])))
    return jsonify(ok=True, complete=is_complete(row), done=done)


# --------------------------------------------------------------------------- #
# Admin routes
# --------------------------------------------------------------------------- #
def require_admin(token: str) -> None:
    entry = resolve_token(token)
    if entry.get("role") != "admin":
        abort(404)


@app.get("/admin/<token>/progress")
def admin_progress(token: str) -> Response:
    require_admin(token)
    batch = load_batch()
    tokens = load_tokens()
    reviewers = [t for t in tokens.values() if t.get("role") == "reviewer"]
    rows = ""
    for rv in reviewers:
        answers = answers_for(rv["id"])
        answered = sum(1 for c in batch if answers.get(c["card_id"]))
        complete = sum(1 for c in batch if is_complete(answers.get(c["card_id"])))
        flagged = sum(1 for c in batch if answers.get(c["card_id"]) and answers[c["card_id"]]["flagged"])
        rows += (
            f"<tr><td>{escape(rv['id'])}</td><td>{escape(rv.get('slot',''))}</td>"
            f"<td>{complete} / {len(batch)}</td><td>{answered}</td><td>{flagged}</td></tr>"
        )
    body = (
        "<div class=topbar><h1>Review admin — progress</h1></div>"
        f"<p class=count>Batch: {len(batch)} cards · {len(reviewers)} reviewers</p>"
        "<table><thead><tr><th>reviewer</th><th>slot</th><th>complete</th>"
        "<th>answered</th><th>flagged</th></tr></thead><tbody>"
        f"{rows}</tbody></table>"
        f"<p class=row><a class='btn primary' href='/admin/{escape(token)}/export'>"
        "Download JSONL export</a></p>"
    )
    return _page("Review admin", body)


@app.get("/admin/<token>/export")
def admin_export(token: str) -> Response:
    require_admin(token)
    batch = load_batch()
    tokens = load_tokens()
    reviewers = [t for t in tokens.values() if t.get("role") == "reviewer"]
    by_reviewer = {rv["id"]: answers_for(rv["id"]) for rv in reviewers}

    lines: list[str] = []
    for card in batch:
        cue = card.get("cue") or {}
        record: dict[str, Any] = {
            "card_id": card["card_id"],
            "mode_id": card["check_id"],
            "scenario_id": card.get("scenario_id", ""),
            "cue_turn": cue.get("cue_turn"),
            "transcript_window": card["transcript_window"],
            "source_tags": card.get("source_tags", []),
        }
        has_answer = False
        for rv in reviewers:
            row = by_reviewer[rv["id"]].get(card["card_id"])
            if not row or not row["verdict"]:
                continue
            slot = rv.get("slot", "annotator_2")
            n = "1" if slot.endswith("1") else "2"
            record[f"annotator_{n}_id"] = rv["id"]
            record[f"annotator_{n}_verdict"] = row["verdict"]
            if (row["rationale"] or "").strip() or (row["note"] or "").strip():
                record[f"annotator_{n}_note"] = " ".join(
                    p for p in [(row["rationale"] or "").strip(), (row["note"] or "").strip()] if p
                )
            if row["flagged"]:
                record[f"annotator_{n}_flagged"] = True
            has_answer = True
        if has_answer:
            lines.append(json.dumps(record, ensure_ascii=False))

    payload = "\n".join(lines) + ("\n" if lines else "")
    resp = Response(payload, mimetype="application/x-ndjson")
    resp.headers["Content-Disposition"] = "attachment; filename=review_annotations.jsonl"
    return resp


if __name__ == "__main__":
    host = os.environ.get("REVIEW_HOST", "127.0.0.1")
    port = int(os.environ.get("REVIEW_PORT", "3090"))
    app.run(host=host, port=port, threaded=True)
