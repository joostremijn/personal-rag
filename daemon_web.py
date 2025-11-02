"""FastAPI web dashboard for daemon monitoring and control."""

import logging
from pathlib import Path
from typing import Dict, Any, Optional

from fastapi import FastAPI, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel

from src.daemon.state import DaemonState
from src.daemon.oauth import OAuthManager

logger = logging.getLogger(__name__)

# Global state (initialized by daemon)
_state: Optional[DaemonState] = None
_scheduler = None


def init_app(state: DaemonState, scheduler) -> FastAPI:
    """Initialize FastAPI app with state and scheduler.

    Args:
        state: Daemon state manager
        scheduler: Daemon scheduler

    Returns:
        FastAPI application
    """
    global _state, _scheduler
    _state = state
    _scheduler = scheduler

    # Initialize OAuth manager
    oauth_manager = OAuthManager()

    app = FastAPI(title="Personal RAG Daemon")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        """Serve dashboard UI."""
        html_path = Path(__file__).parent / "templates" / "dashboard.html"
        if html_path.exists():
            return html_path.read_text()
        return "<h1>Dashboard</h1><p>Template not found</p>"

    @app.get("/api/status")
    async def get_status() -> Dict[str, Any]:
        """Get current daemon status."""
        last_run = _state.get_last_run()

        return {
            "scheduler_state": _state.get_config("scheduler_state"),
            "interval": _state.get_config("interval"),
            "run_mode": _state.get_config("run_mode"),
            "max_results": _state.get_config("max_results"),
            "last_run": last_run,
        }

    @app.get("/api/history")
    async def get_history(limit: int = 50) -> Dict[str, Any]:
        """Get run history."""
        history = _state.get_history(limit=limit)
        return {"history": history}

    @app.get("/api/config")
    async def get_config() -> Dict[str, str]:
        """Get current configuration."""
        return {
            "interval": _state.get_config("interval"),
            "run_mode": _state.get_config("run_mode"),
            "max_results": _state.get_config("max_results"),
        }

    class ConfigUpdate(BaseModel):
        interval: Optional[int] = None
        run_mode: Optional[str] = None
        max_results: Optional[int] = None

    @app.post("/api/config")
    async def update_config(config: ConfigUpdate) -> Dict[str, str]:
        """Update configuration."""
        if config.interval is not None:
            if config.interval not in [10, 30, 60]:
                raise HTTPException(400, "Interval must be 10, 30, or 60")
            _state.set_config("interval", str(config.interval))
            _scheduler.update_interval(config.interval)

        if config.run_mode is not None:
            if config.run_mode not in ["awake-only", "plugged-in-only"]:
                raise HTTPException(400, "Invalid run_mode")
            _state.set_config("run_mode", config.run_mode)

        if config.max_results is not None:
            _state.set_config("max_results", str(config.max_results))

        return {"status": "updated"}

    @app.post("/api/trigger")
    async def trigger_ingestion() -> Dict[str, str]:
        """Trigger manual ingestion now."""
        _scheduler.trigger_now()
        return {"status": "triggered"}

    @app.post("/api/pause")
    async def pause_scheduler() -> Dict[str, str]:
        """Pause scheduler."""
        _scheduler.pause()
        return {"status": "paused"}

    @app.post("/api/resume")
    async def resume_scheduler() -> Dict[str, str]:
        """Resume scheduler."""
        _scheduler.resume()
        return {"status": "resumed"}

    @app.get("/api/logs")
    async def get_logs(lines: int = 100) -> Dict[str, Any]:
        """Get recent log lines."""
        log_path = Path("logs/daemon.log")
        if not log_path.exists():
            return {"logs": []}

        with open(log_path) as f:
            all_lines = f.readlines()
            recent_lines = all_lines[-lines:]
            return {"logs": recent_lines}

    @app.get("/api/oauth/status")
    async def oauth_status():
        """Get OAuth authentication status."""
        return oauth_manager.get_status()

    @app.get("/api/oauth/authorize")
    async def oauth_authorize():
        """Start OAuth flow."""
        try:
            auth_url = oauth_manager.get_authorization_url()
            # Return HTML page with instructions
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head><title>Google Drive Authorization</title></head>
            <body style="font-family: sans-serif; max-width: 600px; margin: 50px auto;">
                <h2>Authorize Google Drive Access</h2>
                <p>Click the button below to authorize Personal RAG to access your Google Drive:</p>
                <p><a href="{auth_url}" target="_blank" style="display: inline-block; background: #4285f4; color: white; padding: 12px 24px; text-decoration: none; border-radius: 4px;">Authorize Google Drive</a></p>
                <p style="margin-top: 30px; color: #666;">After authorizing, copy the code and paste it below:</p>
                <form action="/api/oauth/callback" method="post" style="margin-top: 20px;">
                    <input type="text" name="code" placeholder="Paste authorization code here" style="width: 100%; padding: 10px; font-size: 14px;" required>
                    <button type="submit" style="margin-top: 10px; background: #34a853; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer;">Complete Authorization</button>
                </form>
            </body>
            </html>
            """
            return HTMLResponse(content=html_content)
        except FileNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))

    @app.post("/api/oauth/callback")
    async def oauth_callback(code: str = Form(...)):
        """Handle OAuth callback."""
        result = oauth_manager.exchange_code(code)

        if result["success"]:
            # Redirect to dashboard with success message
            return RedirectResponse(url="/?oauth=success", status_code=303)
        else:
            raise HTTPException(status_code=400, detail=result.get("error"))

    @app.post("/api/oauth/disconnect")
    async def oauth_disconnect():
        """Disconnect Google Drive."""
        oauth_manager.disconnect()
        return {"success": True}

    @app.get("/api/sources")
    async def list_sources():
        """List all sources."""
        sources = _state.get_sources()
        return {"sources": sources}

    @app.post("/api/sources")
    async def create_source(source: Dict[str, Any]):
        """Create a new source."""
        try:
            source_id = _state.create_source(source)
            return {"success": True, "id": source_id}
        except Exception as e:
            logger.error(f"Failed to create source: {e}")
            raise HTTPException(status_code=400, detail=str(e))

    @app.get("/api/sources/{source_id}")
    async def get_source(source_id: int):
        """Get a single source."""
        source = _state.get_source(source_id)
        if source:
            return source
        raise HTTPException(status_code=404, detail="Source not found")

    @app.put("/api/sources/{source_id}")
    async def update_source(source_id: int, data: Dict[str, Any]):
        """Update a source."""
        try:
            _state.update_source(source_id, data)
            return {"success": True}
        except Exception as e:
            logger.error(f"Failed to update source: {e}")
            raise HTTPException(status_code=400, detail=str(e))

    @app.delete("/api/sources/{source_id}")
    async def delete_source(source_id: int):
        """Delete a source."""
        try:
            _state.delete_source(source_id)
            return {"success": True}
        except Exception as e:
            logger.error(f"Failed to delete source: {e}")
            raise HTTPException(status_code=400, detail=str(e))

    @app.post("/api/sources/{source_id}/toggle")
    async def toggle_source(source_id: int):
        """Toggle source enabled status."""
        source = _state.get_source(source_id)
        if not source:
            raise HTTPException(status_code=404, detail="Source not found")

        _state.update_source(source_id, {"enabled": not source["enabled"]})
        return {"success": True, "enabled": not source["enabled"]}

    return app
