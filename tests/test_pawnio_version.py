import types
from unittest.mock import patch

import pytest


def _fake_winreg_module(data):
    """Build a minimal winreg replacement for our registry helper."""

    class _Key:
        def __init__(self, root, key_path, values=None, subkeys=None):
            self.root = root
            self.key_path = key_path
            self._values = values or {}
            self._subkeys = subkeys or []

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    def OpenKey(root, key_path):
        if "\\" in key_path and key_path.split("\\")[-1] in data.get(root, {}).get(
            "", {}
        ):
            raise NotImplementedError

        # Uninstall root keys list subkeys
        entry = data[root][key_path]
        subkey_names = list(entry.keys())
        return _Key(root, key_path, subkeys=subkey_names)

    def QueryInfoKey(key):
        return (len(key._subkeys), 0, 0)

    def EnumKey(key, index):
        return key._subkeys[index]

    def _split_subkey(root_key_path):
        # key_path for OpenKey(subkey) is like: base_path\\SubKey
        base, sub = root_key_path.rsplit("\\", 1)
        return base, sub

    def _get_subkey_obj(root, key_path):
        base, sub = _split_subkey(key_path)
        values = data[root][base][sub]
        return _Key(root, key_path, values=values)

    def OpenKey_with_sub(root, key_path):
        if key_path.count("\\") >= 3:
            base, sub = key_path.rsplit("\\", 1)
            if base in data.get(root, {}):
                return _get_subkey_obj(root, key_path)
        return OpenKey(root, key_path)

    # Provide two behaviors for OpenKey(): list key vs subkey key
    def _OpenKey(root, key_path):
        return OpenKey_with_sub(root, key_path)

    def QueryValueEx(subkey, value_name):
        if value_name in subkey._values:
            return subkey._values[value_name], None
        raise FileNotFoundError(value_name)

    fake = types.SimpleNamespace()
    fake.HKEY_LOCAL_MACHINE = object()
    fake.HKEY_CURRENT_USER = object()

    fake.OpenKey = _OpenKey
    fake.QueryInfoKey = QueryInfoKey
    fake.EnumKey = EnumKey
    fake.QueryValueEx = QueryValueEx
    return fake


@pytest.mark.parametrize(
    "registry_version, expected",
    [
        ("2.2.0.0", "v2.2.0.0"),
        ("v2.2.0.0", "v2.2.0.0"),
    ],
)
def test_get_installed_pawnio_version_reads_display_version(
    tmp_path, registry_version, expected
):
    import pysysfan.pawnio as pawnio

    marker = tmp_path / ".pawnio_version"
    marker.write_text("v0.0.0\n", encoding="utf-8")

    base_key = r"SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall"
    root = object()
    data = {
        root: {
            base_key: {
                "sub1": {
                    "DisplayName": "PawnIO",
                    "DisplayVersion": registry_version,
                }
            }
        }
    }

    fake_winreg = _fake_winreg_module(data)
    fake_winreg.HKEY_LOCAL_MACHINE = root
    fake_winreg.HKEY_CURRENT_USER = root

    with (
        patch.object(pawnio.sys, "platform", "win32"),
        patch.object(pawnio, "_PAWNIO_VERSION_MARKER_FILE", marker),
        patch.dict("sys.modules", {"winreg": fake_winreg}),
    ):
        assert pawnio.get_installed_pawnio_version() == expected


def test_get_installed_pawnio_version_falls_back_to_marker_on_missing_display_version(
    tmp_path,
):
    import pysysfan.pawnio as pawnio

    marker = tmp_path / ".pawnio_version"
    marker.write_text("v1.2.3\n", encoding="utf-8")

    base_key = r"SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall"
    root = object()
    data = {
        root: {
            base_key: {
                "sub1": {
                    "DisplayName": "PawnIO",
                    # no DisplayVersion
                }
            }
        }
    }

    fake_winreg = _fake_winreg_module(data)
    fake_winreg.HKEY_LOCAL_MACHINE = root
    fake_winreg.HKEY_CURRENT_USER = root

    with (
        patch.object(pawnio.sys, "platform", "win32"),
        patch.object(pawnio, "_PAWNIO_VERSION_MARKER_FILE", marker),
        patch.dict("sys.modules", {"winreg": fake_winreg}),
    ):
        assert pawnio.get_installed_pawnio_version() == "v1.2.3"


def test_get_installed_pawnio_version_non_windows_uses_marker(tmp_path):
    import pysysfan.pawnio as pawnio

    marker = tmp_path / ".pawnio_version"
    marker.write_text("v9.9.9\n", encoding="utf-8")

    with (
        patch.object(pawnio.sys, "platform", "linux"),
        patch.object(pawnio, "_PAWNIO_VERSION_MARKER_FILE", marker),
    ):
        assert pawnio.get_installed_pawnio_version() == "v9.9.9"
