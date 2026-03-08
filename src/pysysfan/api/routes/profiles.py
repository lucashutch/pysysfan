"""Profile management routes for the daemon API."""

from __future__ import annotations

from types import ModuleType
from typing import Any, Callable

from fastapi import Depends, FastAPI, HTTPException, status


def register_profile_routes(
    app: FastAPI,
    *,
    daemon: Any,
    auth_dependency: Callable[..., Any],
    server_module: ModuleType,
) -> None:
    """Register profile-management routes."""

    @app.get("/api/profiles")
    async def list_profiles(token: str = Depends(auth_dependency)) -> dict[str, Any]:
        """List all available profiles with metadata."""
        try:
            profile_manager = server_module.ProfileManager()
            profiles = profile_manager.list_profiles()
            active = profile_manager.get_active_profile()
            return {
                "profiles": [profile.to_dict() for profile in profiles],
                "active": active,
                "count": len(profiles),
            }
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to list profiles: {exc}",
            )

    @app.get("/api/profiles/active")
    async def get_active_profile(
        token: str = Depends(auth_dependency),
    ) -> dict[str, Any]:
        """Get the name of the currently active profile."""
        try:
            return {"active": server_module.ProfileManager().get_active_profile()}
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to get active profile: {exc}",
            )

    @app.post("/api/profiles/{name}/activate")
    async def activate_profile(
        name: str, token: str = Depends(auth_dependency)
    ) -> dict[str, Any]:
        """Switch to a different profile and reload the daemon config."""
        try:
            profile_manager = server_module.ProfileManager()
            if not profile_manager.get_profile_config_path(name).exists():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Profile '{name}' not found",
                )

            profile_manager.set_active_profile(name)
            new_config_path = profile_manager.get_profile_config_path(name)
            daemon.config_path = new_config_path

            if not daemon.reload_config():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to reload configuration for new profile",
                )

            return {
                "success": True,
                "message": f"Switched to profile: {name}",
                "profile": name,
                "config_path": str(new_config_path),
            }
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to activate profile: {exc}",
            )

    @app.post("/api/profiles/{name}")
    async def create_profile(
        name: str, profile_data: dict, token: str = Depends(auth_dependency)
    ) -> dict[str, Any]:
        """Create a new profile."""
        try:
            profile_manager = server_module.ProfileManager()
            if profile_manager.get_profile_config_path(name).exists():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Profile '{name}' already exists",
                )

            profile = profile_manager.create_profile(
                name=name,
                display_name=profile_data.get("display_name"),
                description=profile_data.get("description", ""),
                copy_from=profile_data.get("copy_from"),
            )
            return {"success": True, "profile": profile.to_dict()}
        except HTTPException:
            raise
        except FileExistsError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
        except FileNotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create profile: {exc}",
            )

    @app.delete("/api/profiles/{name}")
    async def delete_profile(
        name: str, token: str = Depends(auth_dependency)
    ) -> dict[str, Any]:
        """Delete a profile."""
        try:
            profile_manager = server_module.ProfileManager()
            if name == "default":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot delete the default profile",
                )
            if name == profile_manager.get_active_profile():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot delete the active profile. Switch to another profile first.",
                )

            profile_manager.delete_profile(name)
            return {
                "success": True,
                "message": f"Profile '{name}' deleted",
                "deleted": name,
            }
        except HTTPException:
            raise
        except FileNotFoundError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Profile '{name}' not found",
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to delete profile: {exc}",
            )

    @app.get("/api/profiles/{name}/config")
    async def get_profile_config(
        name: str, token: str = Depends(auth_dependency)
    ) -> dict[str, Any]:
        """Get a profile's configuration."""
        try:
            profile = server_module.ProfileManager().get_profile(name)
            return server_module.config_to_dict(profile.config)
        except FileNotFoundError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Profile '{name}' not found",
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to get profile config: {exc}",
            )

    @app.put("/api/profiles/{name}/config")
    async def update_profile_config(
        name: str, config_data: dict, token: str = Depends(auth_dependency)
    ) -> dict[str, Any]:
        """Update a profile's configuration."""
        try:
            profile_manager = server_module.ProfileManager()
            if not profile_manager.get_profile_config_path(name).exists():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Profile '{name}' not found",
                )

            profile = profile_manager.get_profile(name)
            config = server_module._build_config_from_payload(
                config_data,
                existing_config=profile.config,
            )
            profile_manager.update_profile(name, config=config)

            is_active = name == profile_manager.get_active_profile()
            if is_active:
                daemon.config_path = profile_manager.get_profile_config_path(name)
                daemon.reload_config()

            return {
                "success": True,
                "profile": name,
                "is_active": is_active,
                "reloaded": is_active,
            }
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to update profile config: {exc}",
            )
