"""Windows service management routes for the daemon API."""

from __future__ import annotations

import asyncio
from types import ModuleType
from typing import Any, Callable

from fastapi import Depends, FastAPI, HTTPException


def register_service_routes(
    app: FastAPI,
    *,
    daemon: Any,
    auth_dependency: Callable[..., Any],
    server_module: ModuleType,
) -> None:
    """Register Windows service-management routes."""

    @app.get("/api/service/status")
    async def get_service_status(
        token: str = Depends(auth_dependency),
    ) -> dict[str, Any]:
        """Get full service status model."""
        import datetime

        task_status = server_module.windows_service.get_task_status()
        task_details = server_module.windows_service.get_task_details()

        task_installed = task_status is not None
        task_enabled = (
            task_details.get("Status") != "Disabled" if task_details else False
        )

        task_last_run = None
        if task_details and "Last Run Time" in task_details:
            try:
                time_str = task_details["Last Run Time"]
                if time_str and time_str != "N/A":
                    task_last_run = datetime.datetime.strptime(
                        time_str,
                        "%m/%d/%Y %I:%M:%S %p",
                    )
            except (ValueError, TypeError):
                pass

        daemon_proc = server_module.find_daemon_process()
        daemon_running = daemon_proc is not None
        daemon_pid = daemon_proc.pid if daemon_proc else None

        daemon_healthy = False
        if daemon_running:
            try:
                api_base_url = server_module.build_local_api_base_url(
                    api_host=daemon._api_host,
                    api_port=daemon._api_port,
                )
                response = server_module.requests.get(
                    f"{api_base_url}/api/health",
                    timeout=2.0,
                )
                daemon_healthy = response.status_code == 200
            except Exception:
                pass

        return {
            "task_installed": task_installed,
            "task_enabled": task_enabled,
            "task_status": task_status,
            "task_last_run": task_last_run.isoformat() if task_last_run else None,
            "daemon_running": daemon_running,
            "daemon_pid": daemon_pid,
            "daemon_healthy": daemon_healthy,
        }

    @app.post("/api/service/install")
    async def install_service(
        config_path: str | None = None,
        token: str = Depends(auth_dependency),
    ) -> dict[str, Any]:
        """Install pysysfan as startup service with explicit config path."""
        try:
            server_module.windows_service.install_task(config_path=config_path)
            return {"success": True, "message": "Service installed"}
        except FileNotFoundError as exc:
            raise HTTPException(404, str(exc))
        except Exception as exc:
            raise HTTPException(500, str(exc))

    @app.post("/api/service/uninstall")
    async def uninstall_service(
        token: str = Depends(auth_dependency),
    ) -> dict[str, Any]:
        """Remove pysysfan startup service."""
        try:
            server_module.windows_service.uninstall_task()
            return {"success": True, "message": "Service uninstalled"}
        except FileNotFoundError:
            raise HTTPException(404, "Service not installed")
        except Exception as exc:
            raise HTTPException(500, str(exc))

    @app.post("/api/service/enable")
    async def enable_service(token: str = Depends(auth_dependency)) -> dict[str, Any]:
        """Enable the scheduled task."""
        try:
            server_module.windows_service.enable_task()
            return {"success": True, "message": "Service enabled"}
        except FileNotFoundError:
            raise HTTPException(404, "Service not installed")
        except Exception as exc:
            raise HTTPException(500, str(exc))

    @app.post("/api/service/disable")
    async def disable_service(token: str = Depends(auth_dependency)) -> dict[str, Any]:
        """Disable the scheduled task."""
        try:
            server_module.windows_service.disable_task()
            return {"success": True, "message": "Service disabled"}
        except FileNotFoundError:
            raise HTTPException(404, "Service not installed")
        except Exception as exc:
            raise HTTPException(500, str(exc))

    @app.post("/api/service/start")
    async def start_service(token: str = Depends(auth_dependency)) -> dict[str, Any]:
        """Start the daemon now."""
        if server_module.find_daemon_process():
            return {"success": True, "message": "Daemon already running"}

        try:
            server_module.windows_service.start_task()
            return {"success": True, "message": "Daemon started"}
        except FileNotFoundError:
            raise HTTPException(404, "Service not installed")
        except Exception as exc:
            raise HTTPException(500, str(exc))

    @app.post("/api/service/stop")
    async def stop_service(token: str = Depends(auth_dependency)) -> dict[str, Any]:
        """Stop the daemon with graceful fallback."""
        success, method = server_module.stop_daemon_graceful(
            api_host=daemon._api_host,
            api_port=daemon._api_port,
        )
        if not success:
            raise HTTPException(500, "Failed to stop daemon")
        return {
            "success": True,
            "message": f"Daemon stopped via {method.value}",
            "method": method.value,
        }

    @app.post("/api/service/restart")
    async def restart_service(token: str = Depends(auth_dependency)) -> dict[str, Any]:
        """Restart the daemon."""
        success, _method = server_module.stop_daemon_graceful(
            api_host=daemon._api_host,
            api_port=daemon._api_port,
        )
        if not success:
            raise HTTPException(500, "Failed to stop daemon")

        await asyncio.sleep(1.0)

        try:
            server_module.windows_service.start_task()
            return {"success": True, "message": "Daemon restarted"}
        except FileNotFoundError:
            raise HTTPException(404, "Service not installed")
        except Exception as exc:
            raise HTTPException(500, f"Failed to start daemon: {exc}")

    @app.get("/api/service/logs")
    async def get_service_logs(
        lines: int = 100,
        token: str = Depends(auth_dependency),
    ) -> dict[str, Any]:
        """Get recent daemon logs."""
        log_lines = server_module.get_recent_logs(lines)
        return {"logs": log_lines, "total_lines": len(log_lines)}

    @app.post("/api/service/shutdown")
    async def shutdown_service(
        token: str = Depends(auth_dependency),
    ) -> dict[str, bool]:
        """Shutdown the daemon gracefully via API."""
        if hasattr(daemon, "stop"):
            daemon.stop()
        return {"success": True}
