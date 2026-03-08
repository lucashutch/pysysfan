"""Profile rule engine for automatic profile switching."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

import yaml

from pysysfan.config import DEFAULT_CONFIG_DIR

logger = logging.getLogger(__name__)

RULES_FILE = DEFAULT_CONFIG_DIR / "profile_rules.yaml"


@dataclass
class ProfileRule:
    """A rule for automatic profile switching.

    Attributes:
        id: Unique identifier for the rule
        rule_type: Type of rule ('time', 'process', 'manual')
        profile_name: Name of the profile to switch to when rule matches
        enabled: Whether the rule is currently active
        start_hour: Start hour for time-based rules (0-23)
        end_hour: End hour for time-based rules (0-23)
        days: Days for time-based rules (0=Monday, 6=Sunday)
        process_names: Process names to monitor for process-based rules
    """

    rule_type: Literal["time", "process", "manual"]
    profile_name: str
    enabled: bool = True
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    start_hour: int | None = None
    end_hour: int | None = None
    days: list[int] | None = None
    process_names: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert rule to dictionary."""
        return {
            "id": self.id,
            "rule_type": self.rule_type,
            "profile_name": self.profile_name,
            "enabled": self.enabled,
            "start_hour": self.start_hour,
            "end_hour": self.end_hour,
            "days": self.days,
            "process_names": self.process_names,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProfileRule:
        """Create rule from dictionary."""
        return cls(
            id=data.get("id", str(uuid.uuid4())[:8]),
            rule_type=data.get("rule_type", "manual"),
            profile_name=data.get("profile_name", ""),
            enabled=data.get("enabled", True),
            start_hour=data.get("start_hour"),
            end_hour=data.get("end_hour"),
            days=data.get("days"),
            process_names=data.get("process_names"),
        )


def evaluate_time_rule(rule: ProfileRule) -> bool:
    """Evaluate a time-based rule.

    Args:
        rule: The profile rule to evaluate

    Returns:
        True if the current time matches the rule, False otherwise
    """
    now = datetime.now()
    current_hour = now.hour
    current_day = now.weekday()

    if rule.days and current_day not in rule.days:
        return False

    if rule.start_hour is not None and rule.end_hour is not None:
        if rule.start_hour <= rule.end_hour:
            return rule.start_hour <= current_hour < rule.end_hour
        else:
            return current_hour >= rule.start_hour or current_hour < rule.end_hour

    return False


def evaluate_process_rule(rule: ProfileRule) -> bool:
    """Evaluate a process-based rule.

    Args:
        rule: The profile rule to evaluate

    Returns:
        True if any target process is running, False otherwise
    """
    if not rule.process_names:
        return False

    try:
        import psutil

        running_processes: set[str] = set()
        for proc in psutil.process_iter(["name"]):
            try:
                name = proc.info.get("name", "")
                if name:
                    running_processes.add(name.lower())
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        for target in rule.process_names:
            if target.lower() in running_processes:
                return True
    except ImportError:
        logger.warning("psutil not available, cannot evaluate process rules")

    return False


class ProfileRuleEngine:
    """Engine for evaluating profile switching rules.

    Loads rules from disk, evaluates them, and returns the profile
    that should be active based on current conditions.
    """

    def __init__(self, rules_file: Path | None = None):
        """Initialize the rule engine.

        Args:
            rules_file: Path to the rules YAML file. Defaults to ~/.pysysfan/profile_rules.yaml
        """
        self.rules_file = rules_file or RULES_FILE
        self._rules: list[ProfileRule] = []
        self._last_evaluation: float = 0.0
        self._last_result: str | None = None
        self.load_rules()

    def load_rules(self) -> None:
        """Load rules from the rules file."""
        if not self.rules_file.exists():
            self._rules = []
            return

        try:
            with open(self.rules_file, "r") as f:
                data = yaml.safe_load(f) or {}

            rules_data = data.get("rules", [])
            self._rules = [ProfileRule.from_dict(r) for r in rules_data]
            logger.debug(f"Loaded {len(self._rules)} profile rules")
        except Exception as e:
            logger.error(f"Failed to load profile rules: {e}")
            self._rules = []

    def save_rules(self) -> None:
        """Save rules to the rules file."""
        self.rules_file.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "rules": [rule.to_dict() for rule in self._rules],
        }

        try:
            with open(self.rules_file, "w") as f:
                yaml.dump(data, f, sort_keys=False)
            logger.debug(f"Saved {len(self._rules)} profile rules")
        except Exception as e:
            logger.error(f"Failed to save profile rules: {e}")
            raise

    @property
    def rules(self) -> list[ProfileRule]:
        """Get the list of rules."""
        return self._rules

    def add_rule(self, rule: ProfileRule) -> None:
        """Add a new rule.

        Args:
            rule: The rule to add
        """
        self._rules.append(rule)
        self.save_rules()

    def remove_rule(self, rule_id: str) -> bool:
        """Remove a rule by ID.

        Args:
            rule_id: The ID of the rule to remove

        Returns:
            True if rule was removed, False if not found
        """
        initial_len = len(self._rules)
        self._rules = [r for r in self._rules if r.id != rule_id]

        if len(self._rules) < initial_len:
            self.save_rules()
            return True
        return False

    def update_rule(self, rule_id: str, **kwargs) -> bool:
        """Update a rule by ID.

        Args:
            rule_id: The ID of the rule to update
            **kwargs: Fields to update

        Returns:
            True if rule was updated, False if not found
        """
        for rule in self._rules:
            if rule.id == rule_id:
                for key, value in kwargs.items():
                    if hasattr(rule, key):
                        setattr(rule, key, value)
                self.save_rules()
                return True
        return False

    def get_rule(self, rule_id: str) -> ProfileRule | None:
        """Get a rule by ID.

        Args:
            rule_id: The ID of the rule to get

        Returns:
            The rule if found, None otherwise
        """
        for rule in self._rules:
            if rule.id == rule_id:
                return rule
        return None

    def evaluate(self, force: bool = False) -> str | None:
        """Evaluate all rules and return the profile to switch to.

        Rules are evaluated in order, and the first matching rule's
        profile is returned. If no rules match, returns None.

        Args:
            force: Force re-evaluation even if recently evaluated

        Returns:
            Profile name to switch to, or None if no rules match
        """
        import time

        current_time = time.time()

        if not force and (current_time - self._last_evaluation) < 30:
            return self._last_result

        self._last_evaluation = current_time
        self._last_result = None

        for rule in self._rules:
            if not rule.enabled:
                continue

            matches = False

            if rule.rule_type == "time":
                matches = evaluate_time_rule(rule)
            elif rule.rule_type == "process":
                matches = evaluate_process_rule(rule)
            elif rule.rule_type == "manual":
                continue

            if matches:
                logger.debug(
                    f"Rule '{rule.id}' matched, switching to profile '{rule.profile_name}'"
                )
                self._last_result = rule.profile_name
                return rule.profile_name

        return None


def get_rule_engine() -> ProfileRuleEngine:
    """Get a ProfileRuleEngine instance.

    Returns:
        ProfileRuleEngine instance
    """
    return ProfileRuleEngine()
