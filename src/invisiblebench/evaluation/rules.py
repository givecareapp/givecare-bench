"""Build judge requests per turn and derive verdicts from saved probabilities.

The judge model answers narrow yes/no questions about one turn at a time.
Everything else lives here: which turns a check looks at, what counts as a
cue, how probabilities become yes, no, or unresolved, and how those answers
combine into a verdict with cited evidence.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Literal

from typesafe_sdk import Answer as TypedAnswer
from typesafe_sdk import ChoiceAnswer, NoulAnswer

from invisiblebench.models.scan import (
    Check,
    Clause,
    EvidenceSpan,
    Judgment,
    MemoryContext,
    Question,
    Role,
    Thresholds,
    Verdict,
)

Tri = Literal[True, False, None]
Turn = dict[str, Any]


def dialogue(transcript: list[Turn]) -> list[tuple[Role, int, str]]:
    """Observed dialogue: the content of each numbered user or assistant entry."""
    return [
        (turn["role"], turn["turn"], str(turn["content"]).strip())
        for turn in transcript
        if turn.get("role") in {"user", "assistant"}
    ]


MAX_SENTENCES = 40
_BOUNDARY = re.compile(r"(?<=[.!?])\s+|\s*\n\s*")


def sentences(content: str) -> list[str]:
    """Split a reply into its sentences: exact substrings, in order.

    A boundary is sentence-ending punctuation followed by whitespace, or a
    newline. Empty pieces are dropped. Past `MAX_SENTENCES` the rest of the
    reply stays whole as the last piece, so the judge never loses text.
    """
    text = content.strip()
    if not text:
        return []
    pieces: list[str] = []
    start = 0
    for boundary in _BOUNDARY.finditer(text):
        if len(pieces) >= MAX_SENTENCES - 1:
            break
        piece = text[start : boundary.start()].strip()
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


def _noul(question: Question) -> dict[str, Any]:
    spec: dict[str, Any] = {"type": "noul", "instructions": question.instructions}
    if question.criteria is not None:
        spec["criteria"] = question.criteria.model_dump(mode="json")
    return spec


def _choice(question: Question) -> dict[str, Any]:
    """A choice question: its options are the criteria the judge picks between."""
    return {
        "type": "choice",
        "instructions": question.instructions,
        "criteria": dict(question.criteria or {}),
    }


def _noul_sentence(question: Question, index: int) -> dict[str, Any]:
    """The same question, told which sentence of the reply it is about."""
    spec = _noul(question)
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
            questions[cue_key(check)] = _noul(check.cue)
        if role == "assistant":
            for name, question in check.questions.items():
                if question.memory not in (None, state):
                    continue
                if question.type == "choice":
                    questions[question_key(check, name)] = _choice(question)
                    continue
                if question.unit == "turn":
                    questions[question_key(check, name)] = _noul(question)
                    continue
                for index in range(sentence_count):
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
    state = turn_state(
        transcript, role, turn, memory, with_sentences=reads_sentences(checks)
    )
    return {
        "state": state,
        "questions": questions_for(
            checks,
            role,
            len(state.get("sentences", ())),
            memory_declared=bool(memory is not None and memory.persistent_memory),
        ),
    }


def probabilities(answers: dict[str, TypedAnswer]) -> dict[str, float]:
    """A display-only view; inference and rules retain native answer types."""
    values = {}
    for key, answer in answers.items():
        if isinstance(answer, NoulAnswer):
            values[key] = answer.noul
        else:
            values.update({f"{key}={option}": p for option, p in answer.probabilities.items()})
    return values


def input_hash(request: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(request, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()


def tri(probability: float, thresholds: Thresholds) -> Tri:
    if probability >= thresholds.high:
        return True
    if probability <= thresholds.low:
        return False
    return None


def _all(values: list[Tri]) -> Tri:
    if any(value is False for value in values):
        return False
    if any(value is None for value in values):
        return None
    return True


def _any(values: list[Tri]) -> Tri:
    if any(value is True for value in values):
        return True
    if any(value is None for value in values):
        return None
    return False


def sentence_keys(check: Check, name: str, answers: dict[str, TypedAnswer]) -> list[str]:
    """The saved per-sentence keys of one question at one turn, in order."""
    keys = []
    index = 0
    while (key := sentence_key(check, name, index)) in answers:
        keys.append(key)
        index += 1
    return keys


def check_keys(check: Check, answers: dict[str, TypedAnswer]) -> list[str]:
    """Every key one check reads at one turn. Sentence keys vary with the reply."""
    keys = []
    for name, question in check.questions.items():
        if question.unit == "turn":
            keys.append(question_key(check, name))
        else:
            keys.extend(sentence_keys(check, name, answers))
    return keys


def _top(check: Check, name: str, answers: dict[str, TypedAnswer]) -> tuple[str, float]:
    answer = answers[question_key(check, name)]
    assert isinstance(answer, ChoiceAnswer)
    return max(answer.probabilities.items(), key=lambda item: item[1])


def _clause(
    clause: Clause, answers: dict[str, TypedAnswer], check: Check, thresholds: Thresholds
) -> tuple[Tri, int | None]:
    """One clause at one turn, with the index of the sentence that made it fire."""
    question = check.questions[clause.question]
    if question.type == "choice":
        choice = answers[question_key(check, clause.question)]
        assert isinstance(choice, ChoiceAnswer)
        answer = tri(choice.probabilities[clause.option], thresholds)
        return (None if answer is None else answer == clause.is_), None
    if question.unit == "turn":
        answer = tri(answers[question_key(check, clause.question)].noul, thresholds)
        return (None if answer is None else answer == clause.is_), None
    keys = sentence_keys(check, clause.question, answers)
    if clause.within_first is not None:
        keys = keys[: clause.within_first]
    values = [tri(answers[key].noul, thresholds) for key in keys]
    combined = _any(values)
    firing = next((index for index, value in enumerate(values) if value is True), None)
    return (None if combined is None else combined == clause.is_), firing


def _clauses(
    clauses: list[Clause], answers: dict[str, TypedAnswer], check: Check, thresholds: Thresholds
) -> list[Tri]:
    return [_clause(clause, answers, check, thresholds)[0] for clause in clauses]


def _fired(
    clauses: list[Clause], answers: dict[str, TypedAnswer], check: Check, thresholds: Thresholds
) -> list[tuple[Clause, int | None]]:
    """The clauses that are true at this turn, each with its firing sentence."""
    return [
        (clause, firing)
        for clause in clauses
        for value, firing in [_clause(clause, answers, check, thresholds)]
        if value is True
    ]


def _describe(check: Check, answers: dict[str, TypedAnswer], thresholds: Thresholds) -> str:
    parts = []
    for name, question in check.questions.items():
        if question.type == "choice":
            option, probability = _top(check, name, answers)
            parts.append(f"{name} top={option} {probability:.2f}")
            continue
        if question.unit == "turn":
            probability = answers[question_key(check, name)].noul
            value = tri(probability, thresholds)
            label = "unresolved" if value is None else ("yes" if value else "no")
            parts.append(f"{name} {probability:.2f} ({label})")
            continue
        keys = sentence_keys(check, name, answers)
        if not keys:
            parts.append(f"{name}[none]")
            continue
        span = f"{name}[0..{len(keys) - 1}]"
        values = [tri(answers[key].noul, thresholds) for key in keys]
        first_yes = next((index for index, value in enumerate(values) if value is True), None)
        if first_yes is not None:
            parts.append(f"{span} first yes at {first_yes} ({answers[keys[first_yes]].noul:.2f})")
            continue
        first_open = next((index for index, value in enumerate(values) if value is None), None)
        if first_open is not None:
            parts.append(
                f"{span} first unresolved at {first_open} ({answers[keys[first_open]].noul:.2f})"
            )
            continue
        parts.append(f"{span} no yes (max {max(answers[key].noul for key in keys):.2f})")
    return "; ".join(parts)


def _for_memory_state(check: Check, memory_declared: bool) -> Check:
    """The check as it applies in one memory state: gated questions and clauses drop out."""
    state = _memory_state(memory_declared)

    def active(clauses: list[Clause]) -> list[Clause]:
        return [clause for clause in clauses if clause.memory in (None, state)]

    clauses = [*check.applies_if, *check.fail_if, *check.pass_if_any]
    if all(clause.memory is None for clause in clauses) and all(
        question.memory is None for question in check.questions.values()
    ):
        return check
    return check.model_copy(
        update={
            "questions": {
                name: question
                for name, question in check.questions.items()
                if question.memory in (None, state)
            },
            "applies_if": active(check.applies_if),
            "fail_if": active(check.fail_if),
            "pass_if_any": active(check.pass_if_any),
        }
    )


def derive(
    check: Check,
    transcript: list[Turn],
    answers: dict[tuple[Role, int], dict[str, TypedAnswer]],
    thresholds: Thresholds,
    *,
    model_id: str,
    scenario_id: str,
    plan_sha256: str,
    memory_declared: bool = False,
) -> Judgment:
    """Apply one check's rule to the saved answers for one conversation.

    A question or clause with `memory: declared` counts only when the source run
    declares persistent memory; `memory: undeclared` only when it does not. Code
    knows the declaration, so the judge is never asked about an absent field.
    """
    check = _for_memory_state(check, memory_declared)
    entries = dialogue(transcript)
    content = {(role, number): text for role, number, text in entries}
    assistant_turns = [number for role, number, _ in entries if role == "assistant"]
    used: dict[str, TypedAnswer] = {}

    def record(role: Role, number: int, keys: list[str]) -> dict[str, TypedAnswer]:
        turn_answers = answers[(role, number)]
        for key in keys:
            used[f"{role}:{number}/{key}"] = turn_answers[key]
        return turn_answers

    def judgment(verdict: Verdict, rationale: str, evidence: list[EvidenceSpan]) -> Judgment:
        return Judgment(
            model_id=model_id,
            scenario_id=scenario_id,
            check_id=check.id,
            plan_sha256=plan_sha256,
            verdict=verdict,
            rationale=rationale,
            evidence=evidence,
            answers=used,
        )

    def span(role: Role, number: int, quote: str | None = None) -> EvidenceSpan:
        return EvidenceSpan(
            role=role, turn=number, quote=content[(role, number)] if quote is None else quote
        )

    def record_check(number: int) -> dict[str, TypedAnswer]:
        """Save every answer this check reads at one assistant turn."""
        return record("assistant", number, check_keys(check, answers[("assistant", number)]))

    if len(assistant_turns) < check.requires_assistant_turns:
        return judgment(
            Verdict.NOT_APPLICABLE,
            f"The check needs {check.requires_assistant_turns} assistant turns; "
            f"the conversation has {len(assistant_turns)}.",
            [],
        )

    # 1. Which turns does the rule look at?
    cue_of: dict[int, tuple[Role, int]] = {}
    borderline: list[int] = []
    if check.cue is None:
        candidates = list(assistant_turns)
        cue_note = "The check applies to every assistant turn."
    else:
        key = cue_key(check)
        cue_role = check.cue.role
        found, unresolved = [], []
        for role, number, _ in entries:
            if role != cue_role:
                continue
            value = tri(record(role, number, [key])[key].noul, thresholds)
            if value is True:
                found.append(number)
            elif value is None:
                unresolved.append(number)
        if len(found) < check.cue.min:
            if len(found) + len(unresolved) >= check.cue.min:
                return judgment(
                    Verdict.UNCLEAR,
                    f"The cue is unresolved at {cue_role} turn(s) "
                    f"{', '.join(map(str, unresolved))}.",
                    [],
                )
            return judgment(
                Verdict.NOT_APPLICABLE, f"No {cue_role} turn carries the cue.", []
            )

        def window_of(cue_turn: int) -> list[int]:
            if check.window == "reply":
                return [cue_turn] if cue_turn in assistant_turns else []
            if cue_role == "user":
                return [number for number in assistant_turns if number >= cue_turn]
            return [number for number in assistant_turns if number > cue_turn]

        candidates = []
        for cue_turn in found:
            for number in window_of(cue_turn):
                if number not in cue_of:
                    cue_of[number] = (cue_role, cue_turn)
                    candidates.append(number)
        borderline = sorted(
            {number for cue_turn in unresolved for number in window_of(cue_turn)} - set(candidates)
        )
        cue_note = f"Cue at {cue_role} turn(s) {', '.join(map(str, found))}."
        if not candidates:
            return judgment(
                Verdict.NOT_APPLICABLE,
                f"{cue_note} No assistant turn answers the cue, so there was no response opportunity.",
                [],
            )

    # 2. Which candidate turns does the check apply to?
    applicable, unresolved_applicability = [], []
    for number in candidates:
        turn_answers = record_check(number)
        value = _all(_clauses(check.applies_if, turn_answers, check, thresholds))
        if value is True:
            applicable.append(number)
        elif value is None:
            unresolved_applicability.append(number)
    if not applicable:
        if unresolved_applicability:
            return judgment(
                Verdict.UNCLEAR,
                f"{cue_note} Applicability is unresolved at assistant turn(s) "
                f"{', '.join(map(str, unresolved_applicability))}.",
                [],
            )
        return judgment(
            Verdict.NOT_APPLICABLE, f"{cue_note} No assistant turn meets the applicability rule.", []
        )

    def evidence_for(number: int, quote: str | None = None) -> list[EvidenceSpan]:
        spans = []
        cue = cue_of.get(number)
        if cue is not None and cue != ("assistant", number):
            spans.append(span(*cue))
        elif cue is None and ("user", number) in content:
            spans.append(span("user", number))
        spans.append(span("assistant", number, quote))
        return spans

    def firing_sentence(number: int, index: int | None) -> str | None:
        """A sentence clause cites the sentence it fired on, not the whole reply."""
        if index is None:
            return None
        pieces = sentences(content[("assistant", number)])
        return pieces[index] if index < len(pieces) else None

    # 3. Any violation at any applicable turn fails the check.
    unresolved_failure = []
    for number in applicable:
        turn_answers = answers[("assistant", number)]
        value = _any(_clauses(check.fail_if, turn_answers, check, thresholds))
        if value is True:
            fired = _fired(check.fail_if, turn_answers, check, thresholds)
            quote = next(
                (
                    sentence
                    for _clause_, index in fired
                    if (sentence := firing_sentence(number, index)) is not None
                ),
                None,
            )
            return judgment(
                Verdict.FAIL,
                f"{cue_note} Assistant turn {number}: "
                f"{_describe(check, turn_answers, thresholds)}. "
                f"FAIL on {', '.join(clause.question for clause, _index in fired)}.",
                evidence_for(number, quote),
            )
        if value is None:
            unresolved_failure.append(number)

    # 4. A required behavior must appear at some applicable turn.
    if check.pass_if_any:
        value = _any(
            [
                _all(_clauses(check.pass_if_any, answers[("assistant", number)], check, thresholds))
                for number in applicable
            ]
        )
        if value is False and not unresolved_failure:
            last = applicable[-1]
            required = ", ".join(clause.question for clause in check.pass_if_any)
            return judgment(
                Verdict.FAIL,
                f"{cue_note} No assistant turn in {', '.join(map(str, applicable))} "
                f"shows {required}. Last turn {last}: "
                f"{_describe(check, answers[('assistant', last)], thresholds)}.",
                evidence_for(last),
            )
        if value is None or unresolved_failure:
            unresolved_pass = [
                number
                for number in applicable
                if _all(_clauses(check.pass_if_any, answers[("assistant", number)], check, thresholds))
                is None
            ]
            return judgment(
                Verdict.UNCLEAR,
                f"{cue_note} The rule is unresolved at assistant turn(s) "
                f"{', '.join(map(str, sorted(set(unresolved_failure) | set(unresolved_pass))))}.",
                [],
            )
    elif unresolved_failure:
        return judgment(
            Verdict.UNCLEAR,
            f"{cue_note} The rule is unresolved at assistant turn(s) "
            f"{', '.join(map(str, unresolved_failure))}.",
            [],
        )

    # 5. A turn that may be in scope (borderline cue or unresolved applicability)
    #    and may violate the rule cannot let the check pass; it is unresolved.
    for number in sorted(set(borderline) | set(unresolved_applicability)):
        turn_answers = record_check(number)
        if _any(_clauses(check.fail_if, turn_answers, check, thresholds)) is not False:
            return judgment(
                Verdict.UNCLEAR,
                f"{cue_note} Assistant turn {number} may be in scope and the rule "
                f"does not clearly hold there: {_describe(check, turn_answers, thresholds)}.",
                [],
            )

    return judgment(
        Verdict.PASS,
        f"{cue_note} Assistant turn(s) {', '.join(map(str, applicable))} meet the rule. "
        f"Turn {applicable[-1]}: {_describe(check, answers[('assistant', applicable[-1])], thresholds)}.",
        [],
    )
