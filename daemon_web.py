"""FastAPI web dashboard for daemon monitoring and control."""

import logging
from pathlib import Path
from typing import Dict, Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from src.daemon.state import DaemonState

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

    return app
