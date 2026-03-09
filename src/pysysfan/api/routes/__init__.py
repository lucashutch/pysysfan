"""Route registration helpers for the FastAPI daemon surface."""

from pysysfan.api.routes.alerts import register_alert_routes
from pysysfan.api.routes.config import register_config_routes
from pysysfan.api.routes.core import register_core_routes
from pysysfan.api.routes.profiles import register_profile_routes
from pysysfan.api.routes.service import register_service_routes

__all__ = [
    "register_alert_routes",
    "register_config_routes",
    "register_core_routes",
    "register_profile_routes",
    "register_service_routes",
]
