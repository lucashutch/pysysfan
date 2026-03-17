"""Helpers for persisting rolling daemon history to disk.

The daemon appends compact NDJSON samples so the desktop UI can read recent
history even when it starts after the daemon has been running for a while.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from pysysfan.config import DEFAULT_CONFIG_DIR

DEFAULT_HISTORY_PATH = DEFAULT_CONFIG_DIR / "daemon_history.ndjson"
DEFAULT_HISTORY_MAX_AGE_SECONDS = 15 * 60.0
# Skip appending once the file grows beyond this limit to prevent unbounded
# growth between compaction runs (compaction fires every ~60 s in the daemon).
# At a 0.1 s poll interval the file accumulates ~50 KB/min, so 5 MB gives
# ample headroom while preventing runaway growth.
HISTORY_MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB


@dataclass(slots=True)
class HistorySample:
    """Serializable point-in-time history sample."""

    timestamp: float
    temperatures: dict[str, float] = field(default_factory=dict)
    fan_rpm: dict[str, float] = field(default_factory=dict)
    fan_targets: dict[str, float] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> HistorySample:
        """Build a history sample from a decoded JSON payload."""
        return cls(
            timestamp=float(payload["timestamp"]),
            temperatures={
                str(key): float(value)
                for key, value in payload.get("temperatures", {}).items()
            },
            fan_rpm={
                str(key): float(value)
                for key, value in payload.get("fan_rpm", {}).items()
            },
            fan_targets={
                str(key): float(value)
                for key, value in payload.get("fan_targets", {}).items()
            },
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert the sample to a JSON-serializable dictionary."""
        return asdict(self)


def append_history_sample(
    sample: HistorySample,
    path: Path = DEFAULT_HISTORY_PATH,
) -> None:
    """Append a single NDJSON history sample to disk.

    Skips the write when the file has already exceeded ``HISTORY_MAX_FILE_SIZE``
    to prevent unbounded growth between periodic compaction runs.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size >= HISTORY_MAX_FILE_SIZE:
        return
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(sample.to_dict(), sort_keys=True))
        handle.write("\n")


def read_history(
    path: Path = DEFAULT_HISTORY_PATH,
    *,
    max_age_seconds: float = DEFAULT_HISTORY_MAX_AGE_SECONDS,
    now: float | None = None,
) -> list[HistorySample]:
    """Read recent history samples from an NDJSON history file.

    Corrupt or partially-written lines are ignored so the UI can safely read
    while the daemon is writing.
    """
    if not path.exists():
        return []

    current_time = time.time() if now is None else now
    cutoff = None if max_age_seconds < 0 else current_time - max_age_seconds
    samples: list[HistorySample] = []

    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    sample = HistorySample.from_dict(json.loads(stripped))
                except (ValueError, TypeError, KeyError):
                    continue
                if cutoff is not None and sample.timestamp < cutoff:
                    continue
                samples.append(sample)
    except OSError:
        return []

    return samples


def compact_history(
    path: Path = DEFAULT_HISTORY_PATH,
    *,
    max_age_seconds: float = DEFAULT_HISTORY_MAX_AGE_SECONDS,
    now: float | None = None,
) -> None:
    """Rewrite the NDJSON history file so it only keeps recent samples."""
    samples = read_history(path, max_age_seconds=max_age_seconds, now=now)
    if not samples:
        try:
            path.unlink()
        except FileNotFoundError:
            return
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.stem}-",
        suffix=".tmp",
        delete=False,
        newline="\n",
    ) as handle:
        for sample in samples:
            handle.write(json.dumps(sample.to_dict(), sort_keys=True))
            handle.write("\n")
        temp_path = Path(handle.name)

    os.replace(temp_path, path)


__all__ = [
    "DEFAULT_HISTORY_MAX_AGE_SECONDS",
    "DEFAULT_HISTORY_PATH",
    "HISTORY_MAX_FILE_SIZE",
    "HistorySample",
    "append_history_sample",
    "compact_history",
    "read_history",
]
