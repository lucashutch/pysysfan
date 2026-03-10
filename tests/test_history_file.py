"""Tests for daemon-owned NDJSON history storage."""

from __future__ import annotations

from pysysfan.history_file import (
    HistorySample,
    append_history_sample,
    compact_history,
    read_history,
)


def test_read_history_ignores_stale_and_malformed_lines(tmp_path) -> None:
    history_path = tmp_path / "daemon_history.ndjson"
    history_path.write_text(
        "\n".join(
            [
                '{"timestamp": 50, "temperatures": {"/cpu/temp/0": 40.0}}',
                "not-json",
                '{"timestamp": 100, "temperatures": {"/cpu/temp/0": 55.0}, "fan_rpm": {"/mb/control/0": 1200.0}}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    samples = read_history(history_path, max_age_seconds=30.0, now=120.0)

    assert len(samples) == 1
    assert samples[0].timestamp == 100.0
    assert samples[0].fan_rpm == {"/mb/control/0": 1200.0}


def test_compact_history_keeps_recent_samples(tmp_path) -> None:
    history_path = tmp_path / "daemon_history.ndjson"
    append_history_sample(
        HistorySample(timestamp=10.0, temperatures={"/cpu/temp/0": 35.0}),
        history_path,
    )
    append_history_sample(
        HistorySample(timestamp=100.0, temperatures={"/cpu/temp/0": 55.0}),
        history_path,
    )
    append_history_sample(
        HistorySample(timestamp=110.0, fan_targets={"/mb/control/0": 60.0}),
        history_path,
    )

    compact_history(history_path, max_age_seconds=20.0, now=120.0)

    samples = read_history(history_path, max_age_seconds=-1, now=120.0)
    assert [sample.timestamp for sample in samples] == [100.0, 110.0]
