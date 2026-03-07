"""Profile management for pysysfan.

This module provides functions to manage multiple configuration profiles,
allowing users to switch between different fan configurations (e.g., gaming,
silent, performance) without restarting the daemon.

Directory Structure:
    ~/.pysysfan/
    ├── config.yaml           # Default profile (active)
    ├── active_profile        # File containing name of active profile
    ├── api_token             # API authentication token
    └── profiles/
        ├── gaming.yaml
        ├── gaming.meta.yaml  # Metadata (display name, description, rules)
        ├── work.yaml
        └── work.meta.yaml
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from pysysfan.config import Config, DEFAULT_CONFIG_DIR

logger = logging.getLogger(__name__)

# Profile storage paths
PROFILES_DIR = DEFAULT_CONFIG_DIR / "profiles"
ACTIVE_PROFILE_FILE = DEFAULT_CONFIG_DIR / "active_profile"

DEFAULT_PROFILE_NAME = "default"


@dataclass
class ProfileMetadata:
    """Metadata for a profile.

    Attributes:
        display_name: Human-readable name for the profile
        description: Optional description of the profile
        created_at: Timestamp when profile was created
        updated_at: Timestamp when profile was last updated
        rules: Optional automation rules for profile activation
    """

    display_name: str
    description: str = ""
    created_at: str = ""
    updated_at: str = ""
    rules: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert metadata to dictionary."""
        return {
            "display_name": self.display_name,
            "description": self.description,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "rules": self.rules,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProfileMetadata:
        """Create metadata from dictionary."""
        return cls(
            display_name=data.get("display_name", ""),
            description=data.get("description", ""),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            rules=data.get("rules", {}),
        )


@dataclass
class Profile:
    """Represents a pysysfan configuration profile.

    Attributes:
        name: Unique identifier for the profile
        metadata: Profile metadata (display name, description, etc.)
        config: The fan configuration for this profile
    """

    name: str
    metadata: ProfileMetadata
    config: Config

    def to_dict(self) -> dict[str, Any]:
        """Convert profile to dictionary for API responses."""
        return {
            "name": self.name,
            "display_name": self.metadata.display_name,
            "description": self.metadata.description,
            "created_at": self.metadata.created_at,
            "updated_at": self.metadata.updated_at,
            "rules": self.metadata.rules,
        }


class ProfileManager:
    """Manages pysysfan configuration profiles.

    Provides methods to create, read, update, delete, and switch between
    different configuration profiles stored in ~/.pysysfan/profiles/.
    """

    def __init__(self, config_dir: Path | None = None) -> None:
        """Initialize the profile manager.

        Args:
            config_dir: Base configuration directory. Defaults to ~/.pysysfan
        """
        self.config_dir = config_dir or DEFAULT_CONFIG_DIR
        self.profiles_dir = self.config_dir / "profiles"
        self.active_profile_file = self.config_dir / "active_profile"
        self.default_config_path = self.config_dir / "config.yaml"

        # Ensure directories exist
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        """Create necessary directories if they don't exist."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.profiles_dir.mkdir(parents=True, exist_ok=True)

    def _get_profile_config_path(self, name: str) -> Path:
        """Get the config file path for a profile.

        Args:
            name: Profile name

        Returns:
            Path to the profile's config.yaml file
        """
        if name == DEFAULT_PROFILE_NAME:
            return self.default_config_path
        return self.profiles_dir / f"{name}.yaml"

    def _get_profile_meta_path(self, name: str) -> Path:
        """Get the metadata file path for a profile.

        Args:
            name: Profile name

        Returns:
            Path to the profile's .meta.yaml file
        """
        if name == DEFAULT_PROFILE_NAME:
            return self.config_dir / "default.meta.yaml"
        return self.profiles_dir / f"{name}.meta.yaml"

    def _sanitize_profile_name(self, name: str) -> str:
        """Sanitize a profile name for use as a filename.

        Args:
            name: Raw profile name

        Returns:
            Sanitized name safe for filesystem use
        """
        # Remove or replace unsafe characters
        sanitized = name.lower().strip()
        sanitized = "".join(c if c.isalnum() or c in "-_" else "_" for c in sanitized)
        # Remove consecutive underscores
        while "__" in sanitized:
            sanitized = sanitized.replace("__", "_")
        return sanitized

    def list_profiles(self) -> list[Profile]:
        """List all available profiles.

        Returns:
            List of Profile objects including default and custom profiles
        """
        profiles = []

        # Always include default profile
        if self.default_config_path.exists():
            try:
                profiles.append(self.get_profile(DEFAULT_PROFILE_NAME))
            except Exception as e:
                logger.warning(f"Failed to load default profile: {e}")

        # Scan profiles directory
        if self.profiles_dir.exists():
            for config_file in self.profiles_dir.glob("*.yaml"):
                # Skip metadata files
                if config_file.name.endswith(".meta.yaml"):
                    continue

                name = config_file.stem
                try:
                    profiles.append(self.get_profile(name))
                except Exception as e:
                    logger.warning(f"Failed to load profile '{name}': {e}")

        return profiles

    def get_active_profile(self) -> str:
        """Get the name of the currently active profile.

        Returns:
            Name of the active profile, or 'default' if not set
        """
        if self.active_profile_file.exists():
            try:
                return self.active_profile_file.read_text().strip()
            except Exception as e:
                logger.warning(f"Failed to read active profile: {e}")

        return DEFAULT_PROFILE_NAME

    def set_active_profile(self, name: str) -> None:
        """Set the active profile.

        Args:
            name: Profile name to activate

        Raises:
            FileNotFoundError: If the profile doesn't exist
            ValueError: If the profile name is invalid
        """
        if not name or not isinstance(name, str):
            raise ValueError("Profile name must be a non-empty string")

        # Verify profile exists
        config_path = self._get_profile_config_path(name)
        if not config_path.exists():
            raise FileNotFoundError(f"Profile '{name}' not found at {config_path}")

        # Write active profile file
        try:
            self.active_profile_file.write_text(name)
            logger.info(f"Switched to profile: {name}")
        except Exception as e:
            logger.error(f"Failed to set active profile: {e}")
            raise

    def get_profile(self, name: str) -> Profile:
        """Get a profile by name.

        Args:
            name: Profile name

        Returns:
            Profile object

        Raises:
            FileNotFoundError: If the profile doesn't exist
        """
        config_path = self._get_profile_config_path(name)
        if not config_path.exists():
            raise FileNotFoundError(f"Profile '{name}' not found")

        # Load config
        config = Config.load(config_path)

        # Load metadata if exists
        meta_path = self._get_profile_meta_path(name)
        if meta_path.exists():
            try:
                with open(meta_path, "r") as f:
                    meta_data = yaml.safe_load(f) or {}
                metadata = ProfileMetadata.from_dict(meta_data)
            except Exception as e:
                logger.warning(f"Failed to load metadata for '{name}': {e}")
                metadata = ProfileMetadata(display_name=name)
        else:
            metadata = ProfileMetadata(display_name=name)

        return Profile(name=name, metadata=metadata, config=config)

    def get_profile_config_path(self, name: str) -> Path:
        """Get the config file path for a profile.

        Args:
            name: Profile name

        Returns:
            Path to the profile's config file
        """
        return self._get_profile_config_path(name)

    def create_profile(
        self,
        name: str,
        display_name: str | None = None,
        description: str = "",
        copy_from: str | None = None,
        config: Config | None = None,
    ) -> Profile:
        """Create a new profile.

        Args:
            name: Unique profile name (will be sanitized)
            display_name: Human-readable name (defaults to name)
            description: Optional description
            copy_from: Name of existing profile to copy from
            config: Config object to use (overrides copy_from)

        Returns:
            The newly created Profile

        Raises:
            FileExistsError: If profile already exists
            FileNotFoundError: If copy_from profile doesn't exist
        """
        sanitized_name = self._sanitize_profile_name(name)
        if not sanitized_name:
            raise ValueError(f"Invalid profile name: {name}")

        config_path = self._get_profile_config_path(sanitized_name)
        if config_path.exists():
            raise FileExistsError(f"Profile '{sanitized_name}' already exists")

        # Determine source config
        if config is not None:
            source_config = config
        elif copy_from:
            source_profile = self.get_profile(copy_from)
            source_config = source_profile.config
        else:
            # Create from default
            source_config = Config()

        # Create metadata
        from datetime import datetime

        now = datetime.now().isoformat()
        metadata = ProfileMetadata(
            display_name=display_name or name,
            description=description,
            created_at=now,
            updated_at=now,
        )

        # Save config
        source_config.save(config_path)

        # Save metadata
        meta_path = self._get_profile_meta_path(sanitized_name)
        with open(meta_path, "w") as f:
            yaml.dump(metadata.to_dict(), f, sort_keys=False)

        logger.info(f"Created profile: {sanitized_name}")

        return Profile(name=sanitized_name, metadata=metadata, config=source_config)

    def update_profile(
        self,
        name: str,
        display_name: str | None = None,
        description: str | None = None,
        config: Config | None = None,
    ) -> Profile:
        """Update an existing profile.

        Args:
            name: Profile name to update
            display_name: New display name (optional)
            description: New description (optional)
            config: New config (optional)

        Returns:
            Updated Profile

        Raises:
            FileNotFoundError: If profile doesn't exist
        """
        profile = self.get_profile(name)

        # Update config if provided
        if config is not None:
            config_path = self._get_profile_config_path(name)
            config.save(config_path)
            profile.config = config

        # Update metadata
        meta_path = self._get_profile_meta_path(name)
        if display_name is not None:
            profile.metadata.display_name = display_name
        if description is not None:
            profile.metadata.description = description

        from datetime import datetime

        profile.metadata.updated_at = datetime.now().isoformat()

        with open(meta_path, "w") as f:
            yaml.dump(profile.metadata.to_dict(), f, sort_keys=False)

        logger.info(f"Updated profile: {name}")
        return profile

    def delete_profile(self, name: str) -> None:
        """Delete a profile.

        Args:
            name: Profile name to delete

        Raises:
            FileNotFoundError: If profile doesn't exist
            ValueError: If trying to delete the active profile
        """
        if name == DEFAULT_PROFILE_NAME:
            raise ValueError("Cannot delete the default profile")

        if name == self.get_active_profile():
            raise ValueError(
                f"Cannot delete active profile '{name}'. Switch to another profile first."
            )

        config_path = self._get_profile_config_path(name)
        meta_path = self._get_profile_meta_path(name)

        if not config_path.exists():
            raise FileNotFoundError(f"Profile '{name}' not found")

        # Delete files
        try:
            config_path.unlink()
            if meta_path.exists():
                meta_path.unlink()
            logger.info(f"Deleted profile: {name}")
        except Exception as e:
            logger.error(f"Failed to delete profile '{name}': {e}")
            raise

    def duplicate_profile(self, source_name: str, new_name: str) -> Profile:
        """Duplicate an existing profile.

        Args:
            source_name: Name of profile to copy
            new_name: Name for the new profile

        Returns:
            The newly created Profile
        """
        source_profile = self.get_profile(source_name)

        return self.create_profile(
            name=new_name,
            display_name=f"{source_profile.metadata.display_name} (Copy)",
            description=source_profile.metadata.description,
            config=source_profile.config,
        )

    def export_profile(self, name: str, export_path: Path) -> None:
        """Export a profile to a file.

        Args:
            name: Profile name to export
            export_path: Destination path for the exported profile
        """
        profile = self.get_profile(name)

        export_data = {
            "name": profile.name,
            "metadata": profile.metadata.to_dict(),
            "config": _config_to_dict(profile.config),
        }

        with open(export_path, "w") as f:
            yaml.dump(export_data, f, sort_keys=False)

        logger.info(f"Exported profile '{name}' to {export_path}")

    def import_profile(self, import_path: Path, new_name: str | None = None) -> Profile:
        """Import a profile from a file.

        Args:
            import_path: Path to the exported profile file
            new_name: Optional new name for the imported profile

        Returns:
            The imported Profile
        """
        with open(import_path, "r") as f:
            data = yaml.safe_load(f)

        name = new_name or data.get("name", "imported")
        metadata_data = data.get("metadata", {})
        config_data = data.get("config", {})

        # Parse config
        config = _config_from_dict(config_data)

        return self.create_profile(
            name=name,
            display_name=metadata_data.get("display_name", name),
            description=metadata_data.get("description", ""),
            config=config,
        )


def _config_to_dict(config: Config) -> dict[str, Any]:
    """Convert Config object to dictionary."""
    return {
        "general": {"poll_interval": config.poll_interval},
        "fans": {
            name: {
                "fan_id": fan.fan_id,
                "curve": fan.curve,
                "temp_ids": fan.temp_ids,
                "aggregation": fan.aggregation,
                "header_name": fan.header_name,
                "allow_fan_off": fan.allow_fan_off,
            }
            for name, fan in config.fans.items()
        },
        "curves": {
            # Convert tuples to lists for YAML serialization
            name: {
                "points": [list(p) for p in curve.points],
                "hysteresis": curve.hysteresis,
            }
            for name, curve in config.curves.items()
        },
        "update": {
            "auto_check": config.update.auto_check,
            "notify_only": config.update.notify_only,
        },
    }


def _config_from_dict(data: dict[str, Any]) -> Config:
    """Create Config object from dictionary."""
    from pysysfan.config import FanConfig, CurveConfig, UpdateConfig

    config = Config()

    # General settings
    config.poll_interval = data.get("general", {}).get("poll_interval", 2.0)

    # Fans
    for name, fan_data in data.get("fans", {}).items():
        config.fans[name] = FanConfig(
            fan_id=fan_data.get("fan_id", ""),
            curve=fan_data.get("curve", "balanced"),
            temp_ids=fan_data.get("temp_ids", []),
            aggregation=fan_data.get("aggregation", "max"),
            header_name=fan_data.get("header_name"),
            allow_fan_off=fan_data.get("allow_fan_off", True),
        )

    # Curves
    for name, curve_data in data.get("curves", {}).items():
        points = curve_data.get("points", [])
        config.curves[name] = CurveConfig(
            points=[(float(p[0]), float(p[1])) for p in points],
            hysteresis=curve_data.get("hysteresis", 2.0),
        )

    # Update settings
    update_data = data.get("update", {})
    config.update = UpdateConfig(
        auto_check=update_data.get("auto_check", True),
        notify_only=update_data.get("notify_only", True),
    )

    return config


# Convenience functions for direct use
def get_profile_manager(config_dir: Path | None = None) -> ProfileManager:
    """Get a ProfileManager instance.

    Args:
        config_dir: Optional configuration directory

    Returns:
        ProfileManager instance
    """
    return ProfileManager(config_dir)


def list_profiles(config_dir: Path | None = None) -> list[Profile]:
    """List all available profiles.

    Args:
        config_dir: Optional configuration directory

    Returns:
        List of Profile objects
    """
    return get_profile_manager(config_dir).list_profiles()


def get_active_profile(config_dir: Path | None = None) -> str:
    """Get the name of the currently active profile.

    Args:
        config_dir: Optional configuration directory

    Returns:
        Name of the active profile
    """
    return get_profile_manager(config_dir).get_active_profile()


def set_active_profile(name: str, config_dir: Path | None = None) -> None:
    """Set the active profile.

    Args:
        name: Profile name to activate
        config_dir: Optional configuration directory
    """
    get_profile_manager(config_dir).set_active_profile(name)


def create_profile(
    name: str,
    display_name: str | None = None,
    description: str = "",
    copy_from: str | None = None,
    config_dir: Path | None = None,
) -> Profile:
    """Create a new profile.

    Args:
        name: Unique profile name
        display_name: Human-readable name
        description: Optional description
        copy_from: Name of existing profile to copy from
        config_dir: Optional configuration directory

    Returns:
        The newly created Profile
    """
    return get_profile_manager(config_dir).create_profile(
        name=name,
        display_name=display_name,
        description=description,
        copy_from=copy_from,
    )


def delete_profile(name: str, config_dir: Path | None = None) -> None:
    """Delete a profile.

    Args:
        name: Profile name to delete
        config_dir: Optional configuration directory
    """
    get_profile_manager(config_dir).delete_profile(name)


def get_profile_config_path(name: str, config_dir: Path | None = None) -> Path:
    """Get the config file path for a profile.

    Args:
        name: Profile name
        config_dir: Optional configuration directory

    Returns:
        Path to the profile's config file
    """
    return get_profile_manager(config_dir).get_profile_config_path(name)
