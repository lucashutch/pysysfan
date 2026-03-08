"""FastAPI application factory for daemon management."""

from __future__ import annotations

import logging
import sys

import requests  # noqa: F401
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from pysysfan.api.middleware import verify_token
from pysysfan.api.routes import (
    register_alert_routes,
    register_config_routes,
    register_core_routes,
    register_profile_routes,
    register_service_routes,
)
from pysysfan.api.serializers import (  # noqa: F401
    _build_config_from_payload,
    _build_curve_config,
    _build_fan_config,
    _sensors_payload,
    config_to_dict,
)
from pysysfan.api.service_control import (  # noqa: F401
    build_local_api_base_url,
    find_daemon_process,
    get_recent_logs,
    stop_daemon_graceful,
)
from pysysfan.api.state import StateManager
from pysysfan.platforms import windows_service  # noqa: F401
from pysysfan.profiles import ProfileManager  # noqa: F401

logger = logging.getLogger(__name__)


def create_app(daemon, state: StateManager) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        daemon: The FanDaemon instance to expose via API.
        state: The StateManager for daemon state access.

    Returns:
        Configured FastAPI application.
    """
    app = FastAPI(
        title="PySysFan API",
        version="1.0.0",
        docs_url=None,  # Disable Swagger UI in production
        redoc_url=None,
    )

    # CORS for local development
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost", "http://localhost:*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.state.daemon = daemon
    app.state.state_manager = state

    server_module = sys.modules[__name__]
    register_core_routes(
        app,
        daemon=daemon,
        state=state,
        auth_dependency=verify_token,
        server_module=server_module,
    )
    register_config_routes(
        app,
        daemon=daemon,
        auth_dependency=verify_token,
        server_module=server_module,
    )
    register_service_routes(
        app,
        daemon=daemon,
        auth_dependency=verify_token,
        server_module=server_module,
    )
    register_profile_routes(
        app,
        daemon=daemon,
        auth_dependency=verify_token,
        server_module=server_module,
    )
    register_alert_routes(
        app,
        daemon=daemon,
        auth_dependency=verify_token,
    )

    return app
