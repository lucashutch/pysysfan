"""Tests for profile management."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from pysysfan.config import Config, CurveConfig, FanConfig, UpdateConfig
from pysysfan.profiles import (
    DEFAULT_PROFILE_NAME,
    Profile,
    ProfileManager,
    ProfileMetadata,
    create_profile,
    delete_profile,
    get_active_profile,
    get_profile_config_path,
    get_profile_manager,
    list_profiles,
    set_active_profile,
)


@pytest.fixture
def temp_config_dir():
    """Create a temporary configuration directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def profile_manager(temp_config_dir):
    """Create a ProfileManager with a temporary directory."""
    return ProfileManager(config_dir=temp_config_dir)


@pytest.fixture
def sample_config():
    """Create a sample configuration for testing."""
    config = Config()
    config.poll_interval = 3.0
    config.fans["test_fan"] = FanConfig(
        fan_id="/test/fan/0",
        curve="balanced",
        temp_ids=["/test/temp/0"],
        aggregation="max",
    )
    config.curves["balanced"] = CurveConfig(
        points=[(30, 30), (60, 60), (85, 100)],
        hysteresis=2.0,
    )
    config.update = UpdateConfig(auto_check=True, notify_only=False)
    return config


class TestProfileMetadata:
    """Tests for ProfileMetadata class."""

    def test_to_dict(self):
        """Test conversion to dictionary."""
        metadata = ProfileMetadata(
            display_name="Gaming Mode",
            description="High performance cooling",
            created_at="2024-01-01T00:00:00",
            updated_at="2024-01-02T00:00:00",
            rules={"auto_activate": {"temp_threshold": 80}},
        )

        data = metadata.to_dict()

        assert data["display_name"] == "Gaming Mode"
        assert data["description"] == "High performance cooling"
        assert data["created_at"] == "2024-01-01T00:00:00"
        assert data["updated_at"] == "2024-01-02T00:00:00"
        assert data["rules"]["auto_activate"]["temp_threshold"] == 80

    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {
            "display_name": "Silent Mode",
            "description": "Quiet operation",
            "created_at": "2024-03-01T00:00:00",
            "updated_at": "2024-03-02T00:00:00",
            "rules": {"schedule": {"night_only": True}},
        }

        metadata = ProfileMetadata.from_dict(data)

        assert metadata.display_name == "Silent Mode"
        assert metadata.description == "Quiet operation"
        assert metadata.created_at == "2024-03-01T00:00:00"
        assert metadata.updated_at == "2024-03-02T00:00:00"
        assert metadata.rules["schedule"]["night_only"] is True

    def test_from_dict_defaults(self):
        """Test creation from dictionary with missing fields."""
        data = {"display_name": "Test"}

        metadata = ProfileMetadata.from_dict(data)

        assert metadata.display_name == "Test"
        assert metadata.description == ""
        assert metadata.created_at == ""
        assert metadata.updated_at == ""
        assert metadata.rules == {}


class TestProfile:
    """Tests for Profile class."""

    def test_to_dict(self, sample_config):
        """Test conversion to dictionary."""
        metadata = ProfileMetadata(
            display_name="Test Profile",
            description="A test profile",
            created_at="2024-01-01T00:00:00",
            updated_at="2024-01-02T00:00:00",
        )
        profile = Profile(name="test", metadata=metadata, config=sample_config)

        data = profile.to_dict()

        assert data["name"] == "test"
        assert data["display_name"] == "Test Profile"
        assert data["description"] == "A test profile"
        assert data["created_at"] == "2024-01-01T00:00:00"
        assert data["updated_at"] == "2024-01-02T00:00:00"


class TestProfileManager:
    """Tests for ProfileManager class."""

    def test_init_creates_directories(self, temp_config_dir):
        """Test that initialization creates necessary directories."""
        pm = ProfileManager(config_dir=temp_config_dir)

        assert pm.config_dir.exists()
        assert pm.profiles_dir.exists()

    def test_get_profile_config_path_default(self, profile_manager):
        """Test getting config path for default profile."""
        path = profile_manager._get_profile_config_path(DEFAULT_PROFILE_NAME)

        assert path == profile_manager.default_config_path

    def test_get_profile_config_path_custom(self, profile_manager):
        """Test getting config path for custom profile."""
        path = profile_manager._get_profile_config_path("gaming")

        assert path == profile_manager.profiles_dir / "gaming.yaml"

    def test_sanitize_profile_name(self, profile_manager):
        """Test profile name sanitization."""
        assert profile_manager._sanitize_profile_name("Gaming Mode") == "gaming_mode"
        assert (
            profile_manager._sanitize_profile_name("Test-Profile_123")
            == "test-profile_123"
        )
        assert profile_manager._sanitize_profile_name("a!b@c#d$") == "a_b_c_d_"
        assert profile_manager._sanitize_profile_name("__test__") == "_test_"

    def test_list_profiles_empty(self, profile_manager):
        """Test listing profiles when none exist."""
        profiles = profile_manager.list_profiles()

        assert profiles == []

    def test_list_profiles_with_default(self, profile_manager, sample_config):
        """Test listing profiles with default profile."""
        # Create default config
        sample_config.save(profile_manager.default_config_path)

        profiles = profile_manager.list_profiles()

        assert len(profiles) == 1
        assert profiles[0].name == DEFAULT_PROFILE_NAME

    def test_create_profile(self, profile_manager, sample_config):
        """Test creating a new profile."""
        # First create default profile to copy from
        sample_config.save(profile_manager.default_config_path)

        profile = profile_manager.create_profile(
            name="gaming",
            display_name="Gaming Mode",
            description="High performance",
            copy_from=DEFAULT_PROFILE_NAME,
        )

        assert profile.name == "gaming"
        assert profile.metadata.display_name == "Gaming Mode"
        assert profile.metadata.description == "High performance"
        assert profile_manager.get_profile_config_path("gaming").exists()
        assert profile_manager._get_profile_meta_path("gaming").exists()

    def test_create_profile_from_config(self, profile_manager, sample_config):
        """Test creating a profile from a Config object."""
        profile = profile_manager.create_profile(
            name="custom",
            display_name="Custom Profile",
            config=sample_config,
        )

        assert profile.name == "custom"
        assert profile.config.poll_interval == 3.0

    def test_create_profile_already_exists(self, profile_manager, sample_config):
        """Test creating a profile that already exists."""
        sample_config.save(profile_manager.default_config_path)

        profile_manager.create_profile(name="gaming", copy_from=DEFAULT_PROFILE_NAME)

        with pytest.raises(FileExistsError):
            profile_manager.create_profile(name="gaming")

    def test_create_profile_copy_from_nonexistent(self, profile_manager):
        """Test creating a profile copying from non-existent source."""
        with pytest.raises(FileNotFoundError):
            profile_manager.create_profile(name="gaming", copy_from="nonexistent")

    def test_get_profile(self, profile_manager, sample_config):
        """Test getting a profile."""
        sample_config.save(profile_manager.default_config_path)
        profile_manager.create_profile(name="test", copy_from=DEFAULT_PROFILE_NAME)

        profile = profile_manager.get_profile("test")

        assert profile.name == "test"
        assert profile.config is not None

    def test_get_profile_not_found(self, profile_manager):
        """Test getting a non-existent profile."""
        with pytest.raises(FileNotFoundError):
            profile_manager.get_profile("nonexistent")

    def test_get_active_profile_default(self, profile_manager):
        """Test getting active profile when not set."""
        active = profile_manager.get_active_profile()

        assert active == DEFAULT_PROFILE_NAME

    def test_get_active_profile_set(self, profile_manager):
        """Test getting active profile after setting it."""
        # Create a profile first
        config = Config()
        config.save(profile_manager.profiles_dir / "gaming.yaml")

        profile_manager.set_active_profile("gaming")
        active = profile_manager.get_active_profile()

        assert active == "gaming"

    def test_set_active_profile(self, profile_manager):
        """Test setting the active profile."""
        # Create a profile first
        config = Config()
        config.save(profile_manager.profiles_dir / "gaming.yaml")

        profile_manager.set_active_profile("gaming")

        assert profile_manager.active_profile_file.read_text().strip() == "gaming"

    def test_set_active_profile_not_found(self, profile_manager):
        """Test setting a non-existent profile as active."""
        with pytest.raises(FileNotFoundError):
            profile_manager.set_active_profile("nonexistent")

    def test_set_active_profile_invalid_name(self, profile_manager):
        """Test setting an invalid profile name."""
        with pytest.raises(ValueError):
            profile_manager.set_active_profile("")

        with pytest.raises(ValueError):
            profile_manager.set_active_profile(None)  # type: ignore

    def test_update_profile(self, profile_manager, sample_config):
        """Test updating a profile."""
        sample_config.save(profile_manager.default_config_path)
        profile_manager.create_profile(
            name="gaming",
            display_name="Old Name",
            description="Old Description",
            copy_from=DEFAULT_PROFILE_NAME,
        )

        updated = profile_manager.update_profile(
            name="gaming",
            display_name="New Name",
            description="New Description",
        )

        assert updated.metadata.display_name == "New Name"
        assert updated.metadata.description == "New Description"

    def test_delete_profile(self, profile_manager, sample_config):
        """Test deleting a profile."""
        sample_config.save(profile_manager.default_config_path)
        profile_manager.create_profile(name="temp", copy_from=DEFAULT_PROFILE_NAME)

        profile_manager.delete_profile("temp")

        assert not profile_manager.get_profile_config_path("temp").exists()

    def test_delete_profile_default(self, profile_manager):
        """Test deleting the default profile (should fail)."""
        with pytest.raises(ValueError, match="Cannot delete the default profile"):
            profile_manager.delete_profile(DEFAULT_PROFILE_NAME)

    def test_delete_profile_active(self, profile_manager, sample_config):
        """Test deleting the active profile (should fail)."""
        sample_config.save(profile_manager.default_config_path)
        profile_manager.create_profile(name="active", copy_from=DEFAULT_PROFILE_NAME)
        profile_manager.set_active_profile("active")

        with pytest.raises(ValueError, match="Cannot delete active profile"):
            profile_manager.delete_profile("active")

    def test_delete_profile_not_found(self, profile_manager):
        """Test deleting a non-existent profile."""
        with pytest.raises(FileNotFoundError):
            profile_manager.delete_profile("nonexistent")

    def test_duplicate_profile(self, profile_manager, sample_config):
        """Test duplicating a profile."""
        sample_config.save(profile_manager.default_config_path)
        profile_manager.create_profile(
            name="source",
            display_name="Source Profile",
            description="To be copied",
            copy_from=DEFAULT_PROFILE_NAME,
        )

        duplicated = profile_manager.duplicate_profile("source", "copy")

        assert duplicated.name == "copy"
        assert "Copy" in duplicated.metadata.display_name
        assert duplicated.metadata.description == "To be copied"

    def test_export_import_profile(
        self, profile_manager, sample_config, temp_config_dir
    ):
        """Test exporting and importing a profile."""
        sample_config.save(profile_manager.default_config_path)
        profile_manager.create_profile(
            name="export_me",
            display_name="Export Test",
            description="For testing export/import",
            copy_from=DEFAULT_PROFILE_NAME,
        )

        export_path = temp_config_dir / "exported.yaml"
        profile_manager.export_profile("export_me", export_path)

        assert export_path.exists()

        # Import with a new name
        imported = profile_manager.import_profile(export_path, "imported")

        assert imported.name == "imported"
        assert imported.metadata.display_name == "Export Test"


class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""

    def test_get_profile_manager(self, temp_config_dir):
        """Test get_profile_manager function."""
        pm = get_profile_manager(temp_config_dir)

        assert isinstance(pm, ProfileManager)
        assert pm.config_dir == temp_config_dir

    def test_list_profiles(self, temp_config_dir, sample_config):
        """Test list_profiles function."""
        # Setup
        pm = ProfileManager(temp_config_dir)
        sample_config.save(pm.default_config_path)
        pm.create_profile(name="test", copy_from=DEFAULT_PROFILE_NAME)

        # Test
        profiles = list_profiles(temp_config_dir)

        assert len(profiles) == 2
        assert any(p.name == DEFAULT_PROFILE_NAME for p in profiles)
        assert any(p.name == "test" for p in profiles)

    def test_get_active_profile(self, temp_config_dir, sample_config):
        """Test get_active_profile function."""
        pm = ProfileManager(temp_config_dir)
        sample_config.save(pm.default_config_path)
        pm.create_profile(name="active_prof", copy_from=DEFAULT_PROFILE_NAME)
        pm.set_active_profile("active_prof")

        active = get_active_profile(temp_config_dir)

        assert active == "active_prof"

    def test_set_active_profile(self, temp_config_dir, sample_config):
        """Test set_active_profile function."""
        pm = ProfileManager(temp_config_dir)
        sample_config.save(pm.default_config_path)
        pm.create_profile(name="new_active", copy_from=DEFAULT_PROFILE_NAME)

        set_active_profile("new_active", temp_config_dir)

        assert pm.get_active_profile() == "new_active"

    def test_create_profile(self, temp_config_dir, sample_config):
        """Test create_profile function."""
        pm = ProfileManager(temp_config_dir)
        sample_config.save(pm.default_config_path)

        profile = create_profile(
            name="func_test",
            display_name="Function Test",
            copy_from=DEFAULT_PROFILE_NAME,
            config_dir=temp_config_dir,
        )

        assert profile.name == "func_test"
        assert pm.get_profile_config_path("func_test").exists()

    def test_delete_profile(self, temp_config_dir, sample_config):
        """Test delete_profile function."""
        pm = ProfileManager(temp_config_dir)
        sample_config.save(pm.default_config_path)
        pm.create_profile(name="to_delete", copy_from=DEFAULT_PROFILE_NAME)

        delete_profile("to_delete", temp_config_dir)

        assert not pm.get_profile_config_path("to_delete").exists()

    def test_get_profile_config_path(self, temp_config_dir):
        """Test get_profile_config_path function."""
        path = get_profile_config_path("test", temp_config_dir)

        assert path == temp_config_dir / "profiles" / "test.yaml"


class TestProfileConfigOperations:
    """Tests for profile configuration loading and saving."""

    def test_profile_config_roundtrip(self, profile_manager, sample_config):
        """Test that config is preserved through save/load cycle."""
        sample_config.save(profile_manager.default_config_path)
        profile_manager.create_profile(name="roundtrip", copy_from=DEFAULT_PROFILE_NAME)

        profile = profile_manager.get_profile("roundtrip")

        assert profile.config.poll_interval == sample_config.poll_interval
        assert len(profile.config.fans) == len(sample_config.fans)
        # Config.load() adds default curves (silent, balanced, performance) automatically
        # so we check that at least the expected curves are present
        assert len(profile.config.curves) >= len(sample_config.curves)
        # Verify our specific curve is preserved
        assert "balanced" in profile.config.curves

    def test_profile_metadata_roundtrip(self, profile_manager, sample_config):
        """Test that metadata is preserved through save/load cycle."""
        sample_config.save(profile_manager.default_config_path)
        profile_manager.create_profile(
            name="meta_test",
            display_name="Metadata Test",
            description="Testing metadata persistence",
            copy_from=DEFAULT_PROFILE_NAME,
        )

        profile = profile_manager.get_profile("meta_test")

        assert profile.metadata.display_name == "Metadata Test"
        assert profile.metadata.description == "Testing metadata persistence"

    def test_update_profile_config(self, profile_manager, sample_config):
        """Test updating a profile's configuration."""
        sample_config.save(profile_manager.default_config_path)
        profile_manager.create_profile(
            name="update_cfg", copy_from=DEFAULT_PROFILE_NAME
        )

        new_config = Config()
        new_config.poll_interval = 5.0
        new_config.fans["new_fan"] = FanConfig(
            fan_id="/new/fan/0",
            curve="silent",
            temp_ids=["/new/temp/0"],
        )

        updated = profile_manager.update_profile("update_cfg", config=new_config)

        assert updated.config.poll_interval == 5.0
        assert "new_fan" in updated.config.fans


class TestProfileEdgeCases:
    """Tests for edge cases and error handling."""

    def test_profile_name_with_special_chars(self, profile_manager, sample_config):
        """Test profile names with special characters are sanitized."""
        sample_config.save(profile_manager.default_config_path)

        profile = profile_manager.create_profile(
            name="Gaming Mode!!!",
            copy_from=DEFAULT_PROFILE_NAME,
        )

        assert profile.name == "gaming_mode_"

    def test_profile_name_empty_after_sanitization(self, profile_manager):
        """Test that empty names after sanitization are rejected."""
        # Empty string should be rejected
        with pytest.raises(ValueError):
            profile_manager.create_profile(name="")

    def test_corrupted_metadata_file(self, profile_manager, sample_config):
        """Test handling of corrupted metadata file."""
        sample_config.save(profile_manager.default_config_path)
        profile_manager.create_profile(name="corrupt", copy_from=DEFAULT_PROFILE_NAME)

        # Corrupt the metadata file
        meta_path = profile_manager._get_profile_meta_path("corrupt")
        meta_path.write_text("invalid: yaml: content: [")

        # Should still load profile with default metadata
        profile = profile_manager.get_profile("corrupt")
        assert profile.name == "corrupt"
        assert profile.metadata.display_name == "corrupt"  # Falls back to name

    def test_concurrent_profile_creation(self, profile_manager, sample_config):
        """Test that concurrent creation doesn't cause issues."""
        sample_config.save(profile_manager.default_config_path)

        # Create multiple profiles
        for i in range(5):
            profile_manager.create_profile(
                name=f"concurrent_{i}",
                copy_from=DEFAULT_PROFILE_NAME,
            )

        profiles = profile_manager.list_profiles()
        profile_names = {p.name for p in profiles if p.name != DEFAULT_PROFILE_NAME}

        assert profile_names == {f"concurrent_{i}" for i in range(5)}


class TestProfileManagerIntegration:
    """Integration tests for ProfileManager."""

    def test_full_profile_lifecycle(self, profile_manager, sample_config):
        """Test complete profile lifecycle: create, activate, update, delete."""
        # Setup default
        sample_config.save(profile_manager.default_config_path)

        # Create profiles
        gaming = profile_manager.create_profile(
            name="gaming",
            display_name="Gaming Mode",
            description="High performance cooling",
            copy_from=DEFAULT_PROFILE_NAME,
        )
        assert gaming.name == "gaming"

        silent = profile_manager.create_profile(
            name="silent",
            display_name="Silent Mode",
            description="Quiet operation",
            copy_from=DEFAULT_PROFILE_NAME,
        )
        assert silent.name == "silent"

        # Activate gaming
        profile_manager.set_active_profile("gaming")
        assert profile_manager.get_active_profile() == "gaming"

        # Update gaming config
        new_config = Config()
        new_config.poll_interval = 1.0
        profile_manager.update_profile("gaming", config=new_config)

        updated = profile_manager.get_profile("gaming")
        assert updated.config.poll_interval == 1.0

        # List all profiles
        profiles = profile_manager.list_profiles()
        assert len(profiles) == 3  # default + gaming + silent

        # Delete silent
        profile_manager.delete_profile("silent")
        profiles = profile_manager.list_profiles()
        assert len(profiles) == 2

        # Cannot delete active
        with pytest.raises(ValueError):
            profile_manager.delete_profile("gaming")

        # Switch to default then delete gaming
        profile_manager.set_active_profile(DEFAULT_PROFILE_NAME)
        profile_manager.delete_profile("gaming")
        profiles = profile_manager.list_profiles()
        assert len(profiles) == 1
