"""Shared subprocess utilities for platform helpers."""

from __future__ import annotations

import os
import subprocess


def hidden_process_kwargs() -> dict[str, object]:
    """Return subprocess kwargs that suppress console windows on Windows."""
    if os.name != "nt":
        return {}

    kwargs: dict[str, object] = {
        "creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0),
    }
    startupinfo_factory = getattr(subprocess, "STARTUPINFO", None)
    if startupinfo_factory is not None:
        startupinfo = startupinfo_factory()
        startupinfo.dwFlags |= getattr(subprocess, "STARTF_USESHOWWINDOW", 0)
        startupinfo.wShowWindow = getattr(subprocess, "SW_HIDE", 0)
        kwargs["startupinfo"] = startupinfo
    return kwargs
