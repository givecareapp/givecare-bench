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
Every response carries ``X-Robots-Tag: noindex`` except the public index
(``/``), a plain explainer + reviewer-application page with no review content.
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
    if request.path != "/":
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
/* GiveCare "Earthy Neon" system — tokens ported from
   gc-web/packages/theme/foundation.css (warm paper, orange pop, brand status
   colors). Type: Alegreya (serif voice), Gabarito (display/UI), JetBrains
   Mono (kickers, labels, data). */
:root{--bg:oklch(98% 0.016 74);--panel:oklch(97% 0.02 75);--line:oklch(84% 0.05 72);
--fg:oklch(25% 0.08 40);--mut:oklch(47% 0.075 50);--input:oklch(95% 0.025 75);
--primary:oklch(78% 0.22 55);--primary-fg:oklch(28% 0.08 42);--link:oklch(48% 0.14 46);
--fail:oklch(45% 0.16 28);--fail-bg:oklch(96% 0.02 30);
--pass:oklch(42% 0.10 145);--pass-bg:oklch(96% 0.02 145);
--unclear:oklch(48% 0.14 60);--unclear-bg:oklch(96% 0.02 75);
--na:oklch(50% 0.02 60);--na-bg:oklch(95% 0.01 60);
--user:oklch(63% 0.18 148);--user-bg:oklch(96% 0.02 148);
--asst:oklch(93.5% 0.003 286);--asst-fg:oklch(22.7% 0.004 286);
--cue-bg:oklch(95.5% 0.04 52);--cue-line:oklch(72% 0.16 50);
--serif:"Alegreya",Georgia,serif;--display:"Gabarito",system-ui,sans-serif;
--mono:"JetBrains Mono",ui-monospace,Menlo,monospace;
--sans:ui-sans-serif,system-ui,-apple-system,sans-serif}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.6 var(--serif)}
a{color:var(--link);text-decoration-thickness:1px;text-underline-offset:2px}
:focus-visible{outline:2px solid var(--primary);outline-offset:2px}
::selection{background:oklch(78% 0.22 55 / .28)}
.wrap{max-width:1180px;margin:0 auto;padding:18px}
.prose{max-width:740px;margin:0 auto}
.topbar{display:flex;align-items:center;gap:16px;position:sticky;top:0;z-index:5;
background:var(--bg);padding:10px 0;border-bottom:1px solid var(--line)}
.topbar h1{font-family:var(--serif);font-size:19px;margin:0;font-weight:800;
letter-spacing:-.01em}
.wordmark{height:26px;display:block}
.kicker{font-family:var(--mono);font-size:11px;font-weight:500;letter-spacing:.14em;
text-transform:uppercase;color:var(--mut);margin:18px 0 4px}
.kicker .dot{color:var(--primary);margin-right:.5em;letter-spacing:0}
h1.title{font-family:var(--serif);font-weight:800;font-size:clamp(1.8rem,4vw,2.5rem);
line-height:1.05;letter-spacing:-.015em;margin:.15em 0 .45em}
.progress{flex:1;height:8px;background:var(--input);border-radius:6px;overflow:hidden}
.progress>span{display:block;height:100%;background:var(--primary);width:0}
.count{font-family:var(--mono);color:var(--mut);font-size:12px;white-space:nowrap}
.grid{display:grid;grid-template-columns:1fr 360px;gap:20px;margin-top:16px}
@media(max-width:900px){.grid{grid-template-columns:1fr}}
.transcript{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:16px}
.bubble{border-radius:12px;padding:10px 14px;margin:10px 0;white-space:pre-wrap;
word-wrap:break-word;border:1px solid var(--line);font-family:var(--sans);
font-size:14.5px;line-height:1.55}
.bubble .role{font-family:var(--mono);font-size:10.5px;text-transform:uppercase;
letter-spacing:.08em;color:var(--mut);margin-bottom:4px}
.bubble.user{background:var(--user-bg);border-left:3px solid var(--user)}
.bubble.assistant{background:var(--asst);color:var(--asst-fg)}
.bubble.cue{border-color:var(--cue-line);box-shadow:0 0 0 1px var(--cue-line) inset;
background:var(--cue-bg)}
.side{position:sticky;top:70px;align-self:start;display:flex;flex-direction:column;gap:14px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:16px}
.card h3{font-family:var(--mono);margin:0 0 8px;font-size:11.5px;font-weight:500;
color:var(--mut);text-transform:uppercase;letter-spacing:.12em}
.rubric b{color:var(--fg)}
.rubric .rule{margin:8px 0;padding:8px 10px;border-radius:8px;background:var(--input);
border:1px solid var(--line)}
.rule.pass{border-left:3px solid var(--pass);background:var(--pass-bg)}
.rule.fail{border-left:3px solid var(--fail);background:var(--fail-bg)}
.tags span{display:inline-block;font-family:var(--mono);font-size:10.5px;
background:var(--input);border:1px solid var(--line);border-radius:20px;
padding:2px 9px;margin:2px 4px 2px 0;color:var(--mut)}
.verdicts{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.vbtn{padding:11px;border-radius:9px;border:1px solid var(--line);background:var(--bg);
color:var(--fg);font-family:var(--display);font-weight:600;cursor:pointer;font-size:14px}
.vbtn .k{color:var(--mut);font-weight:400;font-size:12px}
.vbtn[data-v=FAIL].on{background:var(--fail);border-color:var(--fail);color:#fff}
.vbtn[data-v=PASS].on{background:var(--pass);border-color:var(--pass);color:#fff}
.vbtn[data-v=UNCLEAR].on{background:var(--unclear);border-color:var(--unclear);color:#fff}
.vbtn[data-v=NOT_APPLICABLE].on{background:var(--na);border-color:var(--na);color:#fff}
textarea{width:100%;background:var(--bg);color:var(--fg);border:1px solid var(--line);
border-radius:8px;padding:9px;font:14px/1.5 var(--sans);resize:vertical;min-height:64px}
label{font-family:var(--mono);display:block;font-size:11px;letter-spacing:.06em;
text-transform:uppercase;color:var(--mut);margin:10px 0 4px}
.req{color:var(--fail)}
.row{display:flex;gap:8px;align-items:center;margin-top:12px;flex-wrap:wrap}
.btn{padding:9px 14px;border-radius:8px;border:1px solid var(--line);background:var(--bg);
color:var(--fg);cursor:pointer;text-decoration:none;font-family:var(--display);
font-weight:600;font-size:14px}
.btn.primary{background:var(--primary);border-color:var(--primary);color:var(--primary-fg)}
.btn.flag.on{background:var(--fail-bg);border-color:var(--fail);color:var(--fail)}
.saved{font-family:var(--mono);font-size:12px;color:var(--pass);min-height:16px}
.warn{font-family:var(--mono);font-size:12px;color:var(--unclear);min-height:16px}
.hb{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:8px 16px;
margin-top:16px}
.hb h2,.hb h3,.hb h4{color:var(--fg)}
.hb pre.code{background:var(--input);border:1px solid var(--line);border-radius:8px;
padding:10px;overflow:auto;font-family:var(--mono);font-size:12px;white-space:pre}
.hb .tablerow{font-family:var(--mono);font-size:12px;color:var(--mut);white-space:pre-wrap}
table{border-collapse:collapse;width:100%;font-size:14px}
td,th{border:1px solid var(--line);padding:6px 9px;text-align:left}
th{background:var(--input)}
"""


_FONTS = (
    "<link rel=preconnect href='https://fonts.googleapis.com'>"
    "<link rel=preconnect href='https://fonts.gstatic.com' crossorigin>"
    "<link rel=stylesheet href='https://fonts.googleapis.com/css2"
    "?family=Alegreya:ital,wght@0,400..800;1,400..800"
    "&family=Gabarito:wght@400..800"
    "&family=JetBrains+Mono:wght@400;500&display=swap'>"
)


def _page(title: str, body: str, script: str = "", public: bool = False) -> Response:
    robots = "" if public else "<meta name=robots content='noindex,nofollow'>"
    html = (
        "<!doctype html><html lang=en><head><meta charset=utf-8>"
        "<meta name=viewport content='width=device-width,initial-scale=1'>"
        f"{robots}{_FONTS}"
        "<link rel=icon href='https://givecareapp.com/favicon.ico'>"
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


_APPLY_EMAIL = "ali@givecareapp.com"
_APPLY_MAILTO = (
    f"mailto:{_APPLY_EMAIL}"
    "?subject=InvisibleBench%20reviewer%20application"
    "&body=A%20line%20or%20two%20about%20your%20background%20"
    "(caregiving%2C%20clinical%2C%20crisis%2C%20or%20research)%20"
    "and%20why%20you%27d%20like%20to%20review."
)


@app.get("/")
def index() -> Response:
    body = (
        "<div class=topbar>"
        "<a href='https://givecareapp.com' aria-label='GiveCare home'>"
        "<img class=wordmark src='https://givecareapp.com/gc-logo.png' alt='GiveCare'>"
        "</a><div class=count>InvisibleBench</div></div>"
        "<div class=prose>"
        "<div class=kicker><span class=dot>&#9679;</span>"
        "InvisibleBench &middot; Human review</div>"
        "<h1 class=title>Human judgment for an AI safety benchmark</h1>"
        "<p>The human-review surface for "
        "<a href='https://bench.givecareapp.com'>InvisibleBench</a>, an open "
        "AI-safety benchmark for caregiving conversations. Reviewers grade "
        "model transcripts against one safety check at a time &mdash; blind "
        "&mdash; and those labels become the gold data that decides whether "
        "the benchmark&rsquo;s automated judges can be trusted.</p>"
        "<div class=card><h3>How reviewing works</h3><ol>"
        "<li><b>Private link</b> &mdash; no account, nothing to install. "
        "Progress autosaves; stop and resume any time.</li>"
        "<li>Each card: <b>one conversation</b>, <b>one check&rsquo;s "
        "rubric</b>.</li>"
        "<li>Verdict: <b>PASS</b>, <b>FAIL</b>, <b>UNCLEAR</b>, or "
        "<b>N/A</b>. Short rationale required for FAIL and UNCLEAR.</li>"
        "<li><b>Blind</b>: no machine verdicts, no other reviewers&rsquo; "
        "labels.</li>"
        "<li>~20 cards per batch, about 30&ndash;45 minutes. Full handbook "
        "on your reviewer page.</li>"
        "</ol></div>"
        "<div class=card><h3>Content advisory</h3>"
        "<p>Transcripts are simulated caregiver conversations and include "
        "crisis content &mdash; suicidal ideation, elder abuse, severe "
        "strain. All personas are fictional. Step away whenever you need "
        "to.</p></div>"
        "<div class=card><h3>Become a reviewer</h3>"
        "<p>We want people with real judgment about care: family caregivers, "
        "social workers, crisis-line responders, clinicians, AI-safety "
        "researchers. Email "
        f"<a href='{_APPLY_MAILTO}'>{_APPLY_EMAIL}</a> with a line about "
        "your background.</p>"
        f"<div class=row><a class='btn primary' href='{_APPLY_MAILTO}'>"
        "Apply by email &rarr;</a></div></div>"
        "<p style='color:var(--mut);font-size:13px'>Open source: "
        "<a href='https://github.com/givecareapp/givecare-bench'>"
        "github.com/givecareapp/givecare-bench</a> &middot; method and "
        "findings at <a href='https://bench.givecareapp.com'>"
        "bench.givecareapp.com</a>. Reviewer pages are private and "
        "unindexed.</p>"
        "</div>"
    )
    return _page("InvisibleBench — human review", body, public=True)


@app.get("/r/<token>")
def landing(token: str) -> Response:
    entry = resolve_token(token)
    if entry.get("role") != "reviewer":
        abort(404)
    batch = load_batch()
    answers = answers_for(entry["id"])
    order = reviewer_order(entry, batch)

    # (position, reason, started) for every card that doesn't count as complete.
    incomplete: list[tuple[int, str, bool]] = []
    for pos, i in enumerate(order):
        row = answers.get(batch[i]["card_id"])
        if is_complete(row):
            continue
        if row is None or not row["verdict"]:
            incomplete.append((pos, "no verdict yet", row is not None))
        else:
            incomplete.append((pos, f"{row['verdict']} needs a rationale", True))
    done = len(order) - len(incomplete)
    resume = incomplete[0][0] if incomplete else 0

    header = (
        "<div class=topbar>"
        "<img class=wordmark src='https://givecareapp.com/gc-logo.png' alt='GiveCare'>"
        f"<h1>Gold-card review</h1>"
        f"<div class=count>{done} / {len(batch)} complete</div></div>"
    )

    if not incomplete:
        body = header + (
            "<div class=card style='margin-top:16px'><h3>All done</h3>"
            f"<p><b>All {len(batch)} cards are complete &mdash; thank you.</b> "
            "Your labels join the benchmark&rsquo;s human gold set; once both "
            "reviewers finish, answers are merged and agreement is measured. "
            "Nothing else is needed from you.</p>"
            "<div class=row>"
            f"<a class='btn' href='/r/{escape(token)}/card/0'>"
            "Look back over your answers</a></div></div>"
        )
        return _page("Gold-card review — complete", body)

    # Cards the reviewer touched but that don't count yet are the deceptive
    # ones — itemize those; untouched cards are just a count.
    started = [(p, r) for p, r, s in incomplete if s]
    remaining = ""
    if started:
        items = "".join(
            f"<li><a href='/r/{escape(token)}/card/{p}'>Card {p + 1}</a> "
            f"&mdash; {escape(r)}</li>"
            for p, r in started
        )
        untouched = len(incomplete) - len(started)
        remaining = (
            "<div class=card style='margin-top:16px'><h3>Still incomplete</h3>"
            f"<ul style='margin:6px 0'>{items}</ul>"
            + (
                f"<p class=count>&hellip;plus {untouched} not started.</p>"
                if untouched
                else ""
            )
            + "</div>"
        )

    body = header + (
        "<p>You are grading model transcripts against a single safety check each. "
        "Read the whole window, apply the <b>human rubric</b> in the side panel "
        "(not any machine label — there are none here), and record a verdict. "
        "A rationale is required for <b>FAIL</b> and <b>UNCLEAR</b>.</p>"
        "<div class=row>"
        f"<a class='btn primary' href='/r/{escape(token)}/card/{resume}'>"
        f"{'Resume' if done else 'Begin'} review &rarr;</a></div>"
        f"{remaining}"
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
    last = pos == len(order) - 1
    next_href = f"/r/{escape(token)}" if last else f"/r/{escape(token)}/card/{pos + 1}"

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
        f"<a class='btn primary' id=next href='{next_href}'>"
        f"{'Finish' if last else 'Next'} &rarr;</a>"
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
  else if(e.key==='ArrowRight'){ location.href = S.pos<S.total-1 ? `/r/${S.token}/card/${S.pos+1}` : `/r/${S.token}`; }
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


@app.get("/admin/<token>/progress.json")
def admin_progress_json(token: str) -> Response:
    """Machine-readable completion state — the predicate for goal-watch nudges."""
    require_admin(token)
    batch = load_batch()
    reviewers = [t for t in load_tokens().values() if t.get("role") == "reviewer"]
    out = []
    for rv in reviewers:
        answers = answers_for(rv["id"])
        out.append(
            {
                "id": rv["id"],
                "slot": rv.get("slot"),
                "total": len(batch),
                "complete": sum(
                    1 for c in batch if is_complete(answers.get(c["card_id"]))
                ),
                "answered": sum(1 for c in batch if answers.get(c["card_id"])),
                "flagged": sum(
                    1
                    for c in batch
                    if (r := answers.get(c["card_id"])) and r["flagged"]
                ),
                "last_updated": max(
                    (r["updated_at"] for r in answers.values()), default=None
                ),
            }
        )
    return jsonify(
        batch_cards=len(batch),
        reviewers=out,
        all_complete=bool(out) and all(r["complete"] == r["total"] for r in out),
    )


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
