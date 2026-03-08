"""Alert-rule and alert-history routes for the daemon API."""

from __future__ import annotations

from typing import Any, Callable

from fastapi import Depends, FastAPI, HTTPException, status


def register_alert_routes(
    app: FastAPI,
    *,
    daemon: Any,
    auth_dependency: Callable[..., Any],
) -> None:
    """Register alert management routes."""

    @app.get("/api/alerts/rules")
    async def list_alert_rules(
        token: str = Depends(auth_dependency),
    ) -> dict[str, Any]:
        """List all alert rules."""
        rules = daemon.notification_manager.get_rules()
        return {"rules": rules, "count": len(rules)}

    @app.post("/api/alerts/rules")
    async def create_alert_rule(
        rule_data: dict, token: str = Depends(auth_dependency)
    ) -> dict[str, Any]:
        """Create a new alert rule."""
        from pysysfan.notifications import AlertRule

        try:
            rule = AlertRule(
                sensor_id=rule_data.get("sensor_id", ""),
                alert_type=rule_data.get("alert_type", "high_temp"),
                threshold=rule_data.get("threshold", 80.0),
                enabled=rule_data.get("enabled", True),
                cooldown_seconds=rule_data.get("cooldown_seconds", 60.0),
            )
            daemon.notification_manager.add_rule(rule)
            return {
                "success": True,
                "rule": daemon.notification_manager.get_rules()[-1],
            }
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create alert rule: {exc}",
            )

    @app.put("/api/alerts/rules/{rule_id}")
    async def update_alert_rule(
        rule_id: str,
        rule_data: dict,
        token: str = Depends(auth_dependency),
    ) -> dict[str, Any]:
        """Update an existing alert rule."""
        try:
            success = daemon.notification_manager.update_rule(
                rule_id=rule_id,
                alert_type=rule_data.get("alert_type"),
                threshold=rule_data.get("threshold"),
                enabled=rule_data.get("enabled"),
                cooldown_seconds=rule_data.get("cooldown_seconds"),
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
            )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Alert rule '{rule_id}' not found",
            )
        return {"success": True, "rule_id": rule_id}

    @app.delete("/api/alerts/rules/{rule_id}")
    async def delete_alert_rule(
        rule_id: str, token: str = Depends(auth_dependency)
    ) -> dict[str, Any]:
        """Delete an alert rule."""
        success = daemon.notification_manager.remove_rule(rule_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Alert rule '{rule_id}' not found",
            )
        return {"success": True, "deleted": rule_id}

    @app.get("/api/alerts/history")
    async def get_alert_history(
        limit: int = 50,
        token: str = Depends(auth_dependency),
    ) -> dict[str, Any]:
        """Get alert history."""
        history = daemon.notification_manager.get_history(limit=limit)
        return {"alerts": history, "count": len(history)}

    @app.delete("/api/alerts/history")
    async def clear_alert_history(
        token: str = Depends(auth_dependency),
    ) -> dict[str, bool]:
        """Clear alert history."""
        daemon.notification_manager.clear_history()
        return {"success": True}
