"""One development family per run. Inspect owns generation and logs; no automatic scores."""

import hashlib
import json
import subprocess
import tomllib
from pathlib import Path

from inspect_ai import Task, task
from inspect_ai.dataset import Sample
from inspect_ai.model import (
    ChatMessageUser,
    GenerateConfig,
    ModelCost,
    ModelInfo,
    get_model_info,
    set_model_info,
)
from inspect_ai.solver import Generate, Solver, TaskState, solver

ROOT = Path(__file__).resolve().parent
CASES = ROOT / "cases"
PROJECT = ROOT / "pyproject.toml"
VERSION = tomllib.loads(PROJECT.read_text())["project"]["version"]

# OpenRouter list prices in USD per million tokens, read from /api/v1/models on 2026-10-30.
# Refresh them before a paid run. Each value is (input, output, input_cache_read).
# Llama lists no cache price, so its cache-read entry repeats the input price.
OPENROUTER_PRICES: dict[str, tuple[float, float, float]] = {
    "openrouter/anthropic/claude-haiku-5.5": (0.10, 0.50, 0.01),
    "openrouter/openai/gpt-5.6-luna-pro": (0.20, 1.20, 0.02),
    "openrouter/openai/gpt-5.6-luna": (0.20, 1.20, 0.02),
    "openrouter/google/gemini-3.1-flash-lite": (0.25, 1.50, 0.025),
    "openrouter/deepseek/deepseek-v4.1-flash": (0.045, 0.50, 0.006),
    "openrouter/meta-llama/llama-3.3-70b-instruct": (0.10, 0.32, 0.10),
}


def register_prices() -> None:
    """Give Inspect each price so it records `total_cost` and `cost_limit` binds."""
    for name, (input_price, output_price, cache_read_price) in OPENROUTER_PRICES.items():
        cost = ModelCost(
            input=input_price,
            output=output_price,
            input_cache_write=input_price,
            input_cache_read=cache_read_price,
        )
        info = get_model_info(name) or ModelInfo()
        set_model_info(name, info.model_copy(update={"cost": cost}))


register_prices()


def case_path(family: str) -> Path:
    """The directory listing under cases/ is the family list."""
    path = CASES / str(family) / "case.json"
    if not isinstance(family, str) or Path(family).name != family or not path.is_file():
        known = sorted(p.parent.name for p in CASES.glob("*/case.json"))
        raise ValueError(f"Unknown family {family!r}; known families: {known}")
    return path


def revision(paths: list[Path]) -> dict:
    """Uncommitted files among those a run depends on; None outside a repository, as in Harbor.

    The commit itself is Inspect's native `log.eval.revision`.
    """
    git = ["git", "-C", str(ROOT)]
    try:
        status = subprocess.run([*git, "status", "--porcelain", "--", *map(str, paths)],
                                capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return {"uncommitted": None}
    return {"uncommitted": sorted(line[3:] for line in status.splitlines())}


def load_case(family: str) -> dict:
    case = json.loads(case_path(family).read_text())
    if case["id"] != family:
        raise ValueError(f"Case id {case['id']!r} differs from directory {family!r}")
    return case


def opening(case: dict, variant: dict) -> str:
    """Fill the one placeholder with the variant's one varying fact."""
    [field] = set(variant) - {"id"}
    if case["opening"].count("{" + field + "}") != 1:
        raise ValueError(f"Opening must hold exactly one {{{field}}} placeholder")
    return case["opening"].replace("{" + field + "}", variant[field])


def samples(family: str = "backup_care") -> list[Sample]:
    case = load_case(family)
    return [
        Sample(
            id=f"{case['id']}/{variant['id']}",
            input=opening(case, variant),
            metadata={"followups": case["followups"]},
        )
        for variant in case["variants"]
    ]


@solver
def conversation() -> Solver:
    async def solve(state: TaskState, generate: Generate) -> TaskState:
        # Only deliver a continuation after the actual preceding model response.
        # Metadata is never inserted wholesale into the target's messages.
        state.metadata["completed_turns"] = 0
        for index in range(len(state.metadata["followups"]) + 1):
            if state.completed:
                break
            if index:
                state.messages.append(
                    ChatMessageUser(content=state.metadata["followups"][index - 1])
                )
            state = await generate(state)
            if state.output.stop_reason in {"max_tokens", "model_length"}:
                raise RuntimeError(f"Incomplete response at user turn {index + 1}")
            # A reply is judgeable evidence only once complete. The log keeps truncated text.
            state.metadata["completed_turns"] = index + 1
        return state

    return solve


@task
def conversation_family(family: str = "backup_care") -> Task:
    return Task(
        dataset=samples(family),
        solver=conversation(),
        scorer=None,
        config=GenerateConfig(max_tokens=2048),
        metadata={
            "use": "development",
            "family": family,
            "benchmark_version": VERSION,
            "project_sha256": hashlib.sha256(PROJECT.read_bytes()).hexdigest(),
            "case_sha256": hashlib.sha256(case_path(family).read_bytes()).hexdigest(),
            "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "measurement": "unscored; review criteria are separate from generation",
            **revision([case_path(family), PROJECT, Path(__file__)]),
        },
    )
