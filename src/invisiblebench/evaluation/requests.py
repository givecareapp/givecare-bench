"""Bind transcript evidence to native Jev questions, batched once per turn.

This module owns request construction and identity. Verdicts belong in rules.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from invisiblebench.evaluation import crisis_continuity, tasks
from invisiblebench.models.scan import Check, MemoryContext, Question, Role

Turn = dict[str, Any]


def dialogue(transcript: list[Turn]) -> list[tuple[Role, int, str]]:
    """Observed dialogue: the content of each numbered user or assistant entry."""
    return [
        (turn["role"], turn["turn"], str(turn["content"]).strip())
        for turn in transcript
        if turn.get("role") in {"user", "assistant"}
    ]


MAX_SENTENCES = 40

_BOUNDARY = re.compile(r"(?P<end>[.!?]+[\"'”’)\]]*)\s+|\s*\n\s*")

_ABBREVIATIONS = frozenset(
    {"dr.", "mr.", "mrs.", "ms.", "mx.", "prof.", "st.", "mt.", "sr.", "jr.", "vs.", "e.g.", "i.e."}
)


def _ends_sentence(piece: str, end: str) -> bool:
    """Whether a period-ended piece is a whole sentence, not a title, initial, or list number."""
    if end != ".":
        return True
    word = piece.rsplit(None, 1)[-1]
    if word.lower() in _ABBREVIATIONS:
        return False
    if re.fullmatch(r"[A-Z]\.", word):
        return False
    return not re.fullmatch(r"\d+\.", piece)


def sentences(content: str) -> list[str]:
    """Split a reply into its sentences: exact substrings, in order.

    A boundary is sentence-ending punctuation, with any closing quotes or
    brackets, followed by whitespace; or a newline. A period after a title
    (Dr.), an initial (J.), a Latin abbreviation (e.g.), or a list number (1.)
    is not a boundary. Decimals and times have no space after the point, so
    they never split. Empty pieces are dropped. Past `MAX_SENTENCES` the rest
    of the reply stays whole as the last piece, so the judge never loses text.
    """
    text = content.strip()
    if not text:
        return []
    pieces: list[str] = []
    start = 0
    for boundary in _BOUNDARY.finditer(text):
        if len(pieces) >= MAX_SENTENCES - 1:
            break
        end = boundary.group("end")
        stop = boundary.end("end") if end else boundary.start()
        piece = text[start:stop].strip()
        if end and "\n" not in boundary.group() and not _ends_sentence(piece, end):
            continue
        if piece:
            pieces.append(piece)
        start = boundary.end()
    remainder = text[start:].strip()
    if remainder:
        pieces.append(remainder)
    return pieces


def cue_key(check: Check) -> str:
    return f"{check.id}/cue"


def question_key(check: Check, name: str) -> str:
    return f"{check.id}/{name}"


def sentence_key(check: Check, name: str, index: int) -> str:
    return f"{check.id}/{name}[{index}]"


def _noul_sentence(question: Question, index: int) -> dict[str, Any]:
    """The same question, told which sentence of the reply it is about."""
    spec = question.to_jev().model_dump(mode="json", exclude_none=True)
    pointer = f"`sentences[{index}]`"
    if isinstance(question.instructions, dict):
        spec["instructions"] = {**question.instructions, "inspect": pointer}
    else:
        spec["instructions"] = f"About {pointer}: {question.instructions}"
    return spec


def reads_sentences(checks: list[Check]) -> bool:
    return any(
        question.unit == "sentence" for check in checks for question in check.questions.values()
    )


def _memory_state(memory_declared: bool) -> str:
    return "declared" if memory_declared else "undeclared"


def questions_for(
    checks: list[Check],
    role: Role,
    sentence_count: int = 0,
    memory_declared: bool = False,
) -> dict[str, dict[str, Any]]:
    """Every question asked about a turn of `role`, keyed for the answer ledger.

    A sentence question becomes one question per sentence of this reply. All of
    them ride in the same request, so a turn still costs one judge call. A
    question with `memory` is asked only in that memory state.
    """
    state = _memory_state(memory_declared)
    questions: dict[str, dict[str, Any]] = {}
    for check in checks:
        if check.cue is not None and check.cue.role == role:
            questions[cue_key(check)] = check.cue.to_jev().model_dump(
                mode="json", exclude_none=True
            )
        if role == "assistant":
            for name, question in check.questions.items():
                if question.memory not in (None, state):
                    continue
                if question.unit == "turn":
                    questions[question_key(check, name)] = question.to_jev().model_dump(
                        mode="json", exclude_none=True
                    )
                    continue
                consumers = [
                    clause
                    for clause in (*check.applies_if, *check.fail_if, *check.pass_if_any)
                    if clause.question == name and clause.memory in (None, state)
                ]
                limit = (
                    sentence_count
                    if any(c.within_first is None for c in consumers)
                    else min(sentence_count, max((c.within_first for c in consumers), default=0))
                )
                for index in range(limit):
                    questions[sentence_key(check, name, index)] = _noul_sentence(question, index)
    return questions


def turn_state(
    transcript: list[Turn],
    role: Role,
    turn: int,
    memory: MemoryContext | None = None,
    *,
    with_sentences: bool = False,
) -> dict[str, Any]:
    """The evidence one request carries: this turn, its counterpart, and earlier dialogue."""
    entries = dialogue(transcript)
    content = {(entry_role, number): text for entry_role, number, text in entries}
    earlier = [entry for entry in entries if entry[1] < turn]
    state: dict[str, Any] = {}
    if role == "user":
        state["caregiver"] = content[("user", turn)]
    else:
        if ("user", turn) in content:
            state["caregiver"] = content[("user", turn)]
        state["assistant"] = content[("assistant", turn)]
        if with_sentences:
            state["sentences"] = sentences(state["assistant"])
    state["earlier_caregiver"] = [text for entry_role, _, text in earlier if entry_role == "user"]
    state["earlier_assistant"] = [
        text for entry_role, _, text in earlier if entry_role == "assistant"
    ]
    if role == "assistant" and memory is not None and memory.persistent_memory:
        state["memory_context"] = {
            "persistent_memory": True,
            "evidence": [
                event.model_dump(mode="json") for event in memory.evidence if event.turn <= turn
            ],
        }
    return state


def request_turns(transcript: list[Turn]) -> list[tuple[Role, int]]:
    return [(role, number) for role, number, _ in dialogue(transcript)]


def build_request(
    checks: list[Check],
    transcript: list[Turn],
    role: Role,
    turn: int,
    memory: MemoryContext | None = None,
) -> dict[str, Any]:
    clauses = [check for check in checks if check.rule == "clauses"]
    state = (
        turn_state(transcript, role, turn, memory, with_sentences=reads_sentences(clauses))
        if clauses
        else {}
    )
    questions = questions_for(
        clauses,
        role,
        len(state.get("sentences", ())),
        memory_declared=bool(memory is not None and memory.persistent_memory),
    )
    for check in checks:
        if check.rule == "crisis_continuity":
            context, battery = crisis_continuity.request(check, dialogue(transcript), role, turn)
            if battery:
                state.update(context)
                questions.update(battery)
        elif check.rule in {"task_completion", "source_support"}:
            context, battery = tasks.request(check, transcript, role, turn, sentences)
            state.update(context)
            questions.update(battery)
    return {"state": state, "questions": questions}


def input_hash(request: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(request, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()
