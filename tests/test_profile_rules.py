"""Tests for profile rules and rule engine."""

from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from pysysfan.profile_rules import (
    ProfileRule,
    ProfileRuleEngine,
    evaluate_process_rule,
    evaluate_time_rule,
    get_rule_engine,
)


@pytest.fixture
def temp_rules_file():
    """Create a temporary rules file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir) / "rules.yaml"


class TestProfileRule:
    """Tests for ProfileRule dataclass."""

    def test_to_dict(self):
        """Test conversion to dictionary."""
        rule = ProfileRule(
            id="test123",
            rule_type="time",
            profile_name="silent",
            enabled=True,
            start_hour=22,
            end_hour=6,
            days=[0, 1, 2, 3, 4, 5, 6],
        )

        data = rule.to_dict()

        assert data["id"] == "test123"
        assert data["rule_type"] == "time"
        assert data["profile_name"] == "silent"
        assert data["enabled"] is True
        assert data["start_hour"] == 22
        assert data["end_hour"] == 6
        assert data["days"] == [0, 1, 2, 3, 4, 5, 6]

    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {
            "id": "abc123",
            "rule_type": "process",
            "profile_name": "gaming",
            "enabled": False,
            "process_names": ["game.exe", "steam.exe"],
        }

        rule = ProfileRule.from_dict(data)

        assert rule.id == "abc123"
        assert rule.rule_type == "process"
        assert rule.profile_name == "gaming"
        assert rule.enabled is False
        assert rule.process_names == ["game.exe", "steam.exe"]

    def test_from_dict_defaults(self):
        """Test creation from dictionary with missing fields."""
        data = {"rule_type": "manual", "profile_name": "default"}

        rule = ProfileRule.from_dict(data)

        assert rule.rule_type == "manual"
        assert rule.profile_name == "default"
        assert rule.enabled is True
        assert rule.id is not None


class TestEvaluateTimeRule:
    """Tests for time rule evaluation."""

    def test_same_day_range_matches(self):
        """Test same-day time range matching."""
        rule = ProfileRule(
            rule_type="time",
            profile_name="silent",
            start_hour=9,
            end_hour=17,
        )

        with patch("pysysfan.profile_rules.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2024, 1, 1, 12, 0, 0)
            mock_dt.now.return_value = datetime(2024, 1, 1, 12, 0, 0)

            result = evaluate_time_rule(rule)
            assert result is True

    def test_same_day_range_not_matches(self):
        """Test same-day time range not matching."""
        rule = ProfileRule(
            rule_type="time",
            profile_name="silent",
            start_hour=9,
            end_hour=17,
        )

        with patch("pysysfan.profile_rules.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2024, 1, 1, 8, 0, 0)

            result = evaluate_time_rule(rule)
            assert result is False

    def test_overnight_range_matches(self):
        """Test overnight time range matching."""
        rule = ProfileRule(
            rule_type="time",
            profile_name="silent",
            start_hour=22,
            end_hour=6,
        )

        with patch("pysysfan.profile_rules.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2024, 1, 1, 23, 0, 0)

            result = evaluate_time_rule(rule)
            assert result is True

    def test_overnight_range_matches_early_morning(self):
        """Test overnight range matching in early morning."""
        rule = ProfileRule(
            rule_type="time",
            profile_name="silent",
            start_hour=22,
            end_hour=6,
        )

        with patch("pysysfan.profile_rules.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2024, 1, 1, 3, 0, 0)

            result = evaluate_time_rule(rule)
            assert result is True

    def test_day_filter(self):
        """Test day-of-week filtering."""
        rule = ProfileRule(
            rule_type="time",
            profile_name="silent",
            start_hour=0,
            end_hour=23,
            days=[0, 1, 2, 3, 4],  # Monday-Friday
        )

        with patch("pysysfan.profile_rules.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2024, 1, 1, 12, 0, 0)  # Monday

            result = evaluate_time_rule(rule)
            assert result is True

    def test_day_filter_not_matching(self):
        """Test day-of-week filtering not matching."""
        rule = ProfileRule(
            rule_type="time",
            profile_name="silent",
            start_hour=0,
            end_hour=23,
            days=[1, 2, 3, 4, 5],  # Tuesday-Saturday
        )

        with patch("pysysfan.profile_rules.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2024, 1, 7, 12, 0, 0)  # Sunday

            result = evaluate_time_rule(rule)
            assert result is False


class TestEvaluateProcessRule:
    """Tests for process rule evaluation."""

    def test_process_running(self):
        """Test detection of running process."""
        rule = ProfileRule(
            rule_type="process",
            profile_name="gaming",
            process_names=["python.exe"],
        )

        import psutil

        with patch("psutil.process_iter") as mock_process_iter:
            mock_proc = {"name": "python.exe"}
            mock_process_iter.return_value = [
                type("MockProc", (), {"info": mock_proc})()
            ]

            result = evaluate_process_rule(rule)
            assert result is True

    def test_process_not_running(self):
        """Test when process is not running."""
        rule = ProfileRule(
            rule_type="process",
            profile_name="gaming",
            process_names=["game.exe"],
        )

        with patch("psutil.process_iter") as mock_process_iter:
            mock_proc = {"name": "other.exe"}
            mock_process_iter.return_value = [
                type("MockProc", (), {"info": mock_proc})()
            ]

            result = evaluate_process_rule(rule)
            assert result is False

    def test_no_process_names(self):
        """Test with empty process names list."""
        rule = ProfileRule(
            rule_type="process",
            profile_name="gaming",
            process_names=None,
        )

        result = evaluate_process_rule(rule)
        assert result is False


class TestProfileRuleEngine:
    """Tests for ProfileRuleEngine class."""

    def test_init_creates_engine(self, temp_rules_file):
        """Test engine initialization."""
        engine = ProfileRuleEngine(rules_file=temp_rules_file)

        assert engine.rules_file == temp_rules_file
        assert engine.rules == []

    def test_load_rules_empty_file(self, temp_rules_file):
        """Test loading rules from empty file."""
        engine = ProfileRuleEngine(rules_file=temp_rules_file)

        assert engine.rules == []

    def test_add_rule(self, temp_rules_file):
        """Test adding a rule."""
        engine = ProfileRuleEngine(rules_file=temp_rules_file)

        rule = ProfileRule(
            rule_type="time",
            profile_name="silent",
            start_hour=22,
            end_hour=6,
        )
        engine.add_rule(rule)

        assert len(engine.rules) == 1
        assert engine.rules[0].profile_name == "silent"

    def test_remove_rule(self, temp_rules_file):
        """Test removing a rule."""
        engine = ProfileRuleEngine(rules_file=temp_rules_file)

        rule = ProfileRule(
            id="test-id",
            rule_type="time",
            profile_name="silent",
        )
        engine.add_rule(rule)

        result = engine.remove_rule("test-id")

        assert result is True
        assert len(engine.rules) == 0

    def test_remove_rule_not_found(self, temp_rules_file):
        """Test removing non-existent rule."""
        engine = ProfileRuleEngine(rules_file=temp_rules_file)

        result = engine.remove_rule("nonexistent")

        assert result is False

    def test_update_rule(self, temp_rules_file):
        """Test updating a rule."""
        engine = ProfileRuleEngine(rules_file=temp_rules_file)

        rule = ProfileRule(
            id="test-id",
            rule_type="time",
            profile_name="silent",
            enabled=True,
        )
        engine.add_rule(rule)

        result = engine.update_rule("test-id", enabled=False, profile_name="gaming")

        assert result is True
        assert engine.rules[0].enabled is False
        assert engine.rules[0].profile_name == "gaming"

    def test_get_rule(self, temp_rules_file):
        """Test getting a rule by ID."""
        engine = ProfileRuleEngine(rules_file=temp_rules_file)

        rule = ProfileRule(
            id="test-id",
            rule_type="time",
            profile_name="silent",
        )
        engine.add_rule(rule)

        retrieved = engine.get_rule("test-id")

        assert retrieved is not None
        assert retrieved.id == "test-id"

    def test_evaluate_no_rules(self, temp_rules_file):
        """Test evaluation with no rules."""
        engine = ProfileRuleEngine(rules_file=temp_rules_file)

        result = engine.evaluate(force=True)

        assert result is None

    def test_evaluate_disabled_rule(self, temp_rules_file):
        """Test that disabled rules are skipped."""
        engine = ProfileRuleEngine(rules_file=temp_rules_file)

        rule = ProfileRule(
            id="test-id",
            rule_type="time",
            profile_name="silent",
            enabled=False,
            start_hour=0,
            end_hour=23,
            days=[0, 1, 2, 3, 4, 5, 6],
        )
        engine.add_rule(rule)

        with patch("pysysfan.profile_rules.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2024, 1, 1, 12, 0, 0)

            result = engine.evaluate(force=True)

        assert result is None


class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""

    def test_get_rule_engine(self):
        """Test get_rule_engine function."""
        engine = get_rule_engine()

        assert isinstance(engine, ProfileRuleEngine)
