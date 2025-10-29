"""
Error resilience and recovery utilities for SupportBench.

Provides retry decorators, atomic file writes, and error handling patterns.
"""
from __future__ import annotations

import json
import logging
import time
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Dict, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


def retry_on_io_error(
    max_retries: int = 3,
    backoff_base: float = 1.0,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator to retry functions on IOError with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts (default: 3)
        backoff_base: Base delay in seconds for exponential backoff (default: 1.0)

    Returns:
        Decorated function that retries on IOError

    Example:
        @retry_on_io_error(max_retries=3, backoff_base=1.0)
        def save_data(path):
            with open(path, 'w') as f:
                f.write(data)
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except (IOError, OSError) as e:
                    last_exception = e

                    # Don't retry on last attempt
                    if attempt == max_retries:
                        logger.error(
                            f"Failed after {max_retries} retries: {func.__name__}"
                        )
                        raise

                    # Calculate exponential backoff delay
                    delay = backoff_base * (2**attempt)
                    logger.warning(
                        f"Attempt {attempt + 1}/{max_retries} failed for {func.__name__}: {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    time.sleep(delay)

            # Should never reach here, but satisfy type checker
            raise last_exception  # type: ignore

        return wrapper

    return decorator


def atomic_json_write(data: Dict[str, Any], target_path: Path | str) -> None:
    """
    Write JSON data atomically using temp file + rename pattern.

    Writes to a temporary file first, then renames to target path.
    This ensures the target file is never left in a partially-written state.

    Args:
        data: Dictionary to write as JSON
        target_path: Target file path

    Raises:
        OSError: If file operations fail (e.g., permission denied, disk full)
        ValueError: If data is not JSON-serializable
    """
    target_path = Path(target_path)

    # Ensure parent directory exists
    target_path.parent.mkdir(parents=True, exist_ok=True)

    # Write to temporary file in same directory
    temp_path = target_path.with_suffix(target_path.suffix + ".tmp")

    try:
        # Write to temp file
        with open(temp_path, "w") as f:
            json.dump(data, f, indent=2)

        # Atomic rename
        temp_path.replace(target_path)

        logger.debug(f"Atomically wrote {target_path}")

    except Exception as e:
        # Clean up temp file if it exists
        if temp_path.exists():
            try:
                temp_path.unlink()
            except Exception:
                pass  # Best effort cleanup

        logger.error(f"Failed to write {target_path}: {e}")
        raise


@retry_on_io_error(max_retries=3, backoff_base=1.0)
def save_state_with_retry(state_data: Dict[str, Any], state_path: Path | str) -> None:
    """
    Save state with retry logic and atomic writes.

    Combines retry decorator with atomic writes for maximum resilience.

    Args:
        state_data: State dictionary to save
        state_path: Path to save state file

    Raises:
        IOError: If saving fails after all retries
    """
    atomic_json_write(state_data, state_path)


def load_state(state_path: Path | str) -> Dict[str, Any]:
    """
    Load state from JSON file with validation.

    Args:
        state_path: Path to state file

    Returns:
        Loaded state dictionary

    Raises:
        FileNotFoundError: If state file doesn't exist
        ValueError: If state file is corrupted or invalid JSON
    """
    state_path = Path(state_path)

    if not state_path.exists():
        raise FileNotFoundError(
            f"Resume state file not found: {state_path}. "
            "Cannot resume from non-existent state."
        )

    try:
        with open(state_path) as f:
            state = json.load(f)

        # Validate required fields
        if not isinstance(state, dict):
            raise ValueError("State must be a dictionary")

        # Basic schema validation
        required_fields = ["status", "dimension_scores"]
        missing = [f for f in required_fields if f not in state]
        if missing:
            raise ValueError(f"State missing required fields: {missing}")

        logger.info(f"Loaded state from {state_path}")
        return state

    except json.JSONDecodeError as e:
        raise ValueError(
            f"Corrupted state file (invalid JSON): {state_path}. "
            f"Error: {e}. Cannot resume from corrupted state."
        )
    except Exception as e:
        raise ValueError(f"Failed to load state from {state_path}: {e}")


def validate_state(state: Dict[str, Any]) -> bool:
    """
    Validate state dictionary structure.

    Args:
        state: State dictionary to validate

    Returns:
        True if valid

    Raises:
        ValueError: If state is invalid
    """
    # Check status is valid
    valid_statuses = [
        "initialized",
        "running",
        "completed",
        "completed_with_errors",
        "error",
    ]
    if state.get("status") not in valid_statuses:
        raise ValueError(f"Invalid status: {state.get('status')}")

    # Check dimension_scores exists and is dict
    if not isinstance(state.get("dimension_scores"), dict):
        raise ValueError("dimension_scores must be a dictionary")

    # Validate each dimension score
    valid_dim_statuses = ["not_started", "completed", "error"]
    for dim, dim_data in state["dimension_scores"].items():
        if not isinstance(dim_data, dict):
            raise ValueError(f"Dimension {dim} data must be a dictionary")

        dim_status = dim_data.get("status")
        if dim_status not in valid_dim_statuses:
            raise ValueError(f"Invalid status for dimension {dim}: {dim_status}")

    return True


def create_error_result(error: Exception, dimension: str) -> Dict[str, Any]:
    """
    Create standardized error result for failed scorer.

    Args:
        error: Exception that was raised
        dimension: Dimension name

    Returns:
        Error result dictionary
    """
    return {
        "status": "error",
        "error": f"{type(error).__name__}: {str(error)}",
        "score": 0.0,  # Default score for errors
        "breakdown": {},
        "evidence": [],
    }


def determine_overall_status(dimension_scores: Dict[str, Any]) -> str:
    """
    Determine overall run status based on dimension statuses.

    Args:
        dimension_scores: Dictionary of dimension results

    Returns:
        Overall status: "completed", "completed_with_errors", or "error"
    """
    statuses = [dim.get("status") for dim in dimension_scores.values()]

    # Count different status types
    completed_count = statuses.count("completed")
    error_count = statuses.count("error")
    total_count = len(statuses)

    if error_count == total_count:
        # All scorers failed
        return "error"
    elif error_count > 0:
        # Some scorers failed
        return "completed_with_errors"
    else:
        # All scorers succeeded
        return "completed"


def format_error_summary(dimension_scores: Dict[str, Any]) -> str:
    """
    Format error summary for logging/display.

    Args:
        dimension_scores: Dictionary of dimension results

    Returns:
        Formatted error summary string
    """
    errors = []
    for dim, dim_data in dimension_scores.items():
        if dim_data.get("status") == "error":
            error_msg = dim_data.get("error", "Unknown error")
            errors.append(f"  - {dim}: {error_msg}")

    if not errors:
        return "No errors"

    return "Errors encountered:\n" + "\n".join(errors)
