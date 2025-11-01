"""Command-line interface for daemon control."""

import argparse
import sys
from typing import Optional

import requests


class DaemonCLI:
    """CLI for controlling the RAG daemon."""

    def __init__(self, base_url: str = "http://localhost:8001") -> None:
        """Initialize CLI.

        Args:
            base_url: Base URL for daemon API
        """
        self.base_url = base_url

    def status(self) -> None:
        """Display daemon status."""
        try:
            response = requests.get(f"{self.base_url}/api/status")
            response.raise_for_status()
            data = response.json()

            print(f"Scheduler State: {data['scheduler_state']}")
            print(f"Interval: {data['interval']} minutes")
            print(f"Run Mode: {data['run_mode']}")

            if data.get("last_run"):
                last_run = data["last_run"]
                print(f"\nLast Run:")
                print(f"  Time: {last_run['timestamp']}")
                print(f"  Success: {last_run['success']}")
                print(f"  Processed: {last_run.get('processed_docs', 0)}")
                print(f"  Skipped: {last_run.get('skipped_docs', 0)}")
                if last_run.get("error"):
                    print(f"  Error: {last_run['error']}")

        except requests.RequestException as e:
            print(f"Error: Cannot connect to daemon. Is it running? ({e})", file=sys.stderr)
            sys.exit(1)

    def trigger(self) -> None:
        """Trigger manual ingestion."""
        try:
            response = requests.post(f"{self.base_url}/api/trigger")
            response.raise_for_status()
            print("Ingestion triggered successfully")
        except requests.RequestException as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

    def pause(self) -> None:
        """Pause scheduler."""
        try:
            response = requests.post(f"{self.base_url}/api/pause")
            response.raise_for_status()
            print("Scheduler paused")
        except requests.RequestException as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

    def resume(self) -> None:
        """Resume scheduler."""
        try:
            response = requests.post(f"{self.base_url}/api/resume")
            response.raise_for_status()
            print("Scheduler resumed")
        except requests.RequestException as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

    def config(self, interval: Optional[int] = None, run_mode: Optional[str] = None,
               max_results: Optional[int] = None) -> None:
        """Update configuration.

        Args:
            interval: New interval in minutes
            run_mode: New run mode
            max_results: New max_results limit
        """
        payload = {}
        if interval is not None:
            payload["interval"] = interval
        if run_mode is not None:
            payload["run_mode"] = run_mode
        if max_results is not None:
            payload["max_results"] = max_results

        if not payload:
            print("No configuration changes specified", file=sys.stderr)
            sys.exit(1)

        try:
            response = requests.post(f"{self.base_url}/api/config", json=payload)
            response.raise_for_status()
            print("Configuration updated")
        except requests.RequestException as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

    def history(self, limit: int = 20) -> None:
        """Display run history.

        Args:
            limit: Number of recent runs to show
        """
        try:
            response = requests.get(f"{self.base_url}/api/history?limit={limit}")
            response.raise_for_status()
            data = response.json()

            history = data.get("history", [])
            if not history:
                print("No run history available")
                return

            print(f"Last {len(history)} runs:\n")
            for run in history:
                status = "✓" if run["success"] else "✗"
                print(f"{status} {run['timestamp']}: {run.get('processed_docs', 0)} processed, "
                      f"{run.get('skipped_docs', 0)} skipped ({run.get('duration', 0):.2f}s)")
                if run.get("error"):
                    print(f"  Error: {run['error']}")

        except requests.RequestException as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

    def logs(self, tail: int = 100) -> None:
        """Display recent log lines.

        Args:
            tail: Number of lines to show
        """
        try:
            response = requests.get(f"{self.base_url}/api/logs?lines={tail}")
            response.raise_for_status()
            data = response.json()

            logs = data.get("logs", [])
            if not logs:
                print("No logs available")
                return

            for line in logs:
                print(line.rstrip())

        except requests.RequestException as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description="Personal RAG Daemon CLI")
    parser.add_argument(
        "--url",
        default="http://localhost:8001",
        help="Daemon API URL (default: http://localhost:8001)"
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Status command
    subparsers.add_parser("status", help="Show daemon status")

    # Trigger command
    subparsers.add_parser("trigger", help="Trigger manual ingestion")

    # Pause command
    subparsers.add_parser("pause", help="Pause scheduler")

    # Resume command
    subparsers.add_parser("resume", help="Resume scheduler")

    # Config command
    config_parser = subparsers.add_parser("config", help="Update configuration")
    config_parser.add_argument("--interval", type=int, choices=[10, 30, 60],
                               help="Interval in minutes")
    config_parser.add_argument("--mode", choices=["awake-only", "plugged-in-only"],
                               help="Run mode")
    config_parser.add_argument("--max-results", type=int,
                               help="Maximum documents to fetch")

    # History command
    history_parser = subparsers.add_parser("history", help="Show run history")
    history_parser.add_argument("--limit", type=int, default=20,
                                help="Number of runs to show (default: 20)")

    # Logs command
    logs_parser = subparsers.add_parser("logs", help="Show recent logs")
    logs_parser.add_argument("--tail", type=int, default=100,
                             help="Number of lines to show (default: 100)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    cli = DaemonCLI(base_url=args.url)

    if args.command == "status":
        cli.status()
    elif args.command == "trigger":
        cli.trigger()
    elif args.command == "pause":
        cli.pause()
    elif args.command == "resume":
        cli.resume()
    elif args.command == "config":
        cli.config(
            interval=args.interval,
            run_mode=args.mode,
            max_results=getattr(args, 'max_results', None)
        )
    elif args.command == "history":
        cli.history(limit=args.limit)
    elif args.command == "logs":
        cli.logs(tail=args.tail)


if __name__ == "__main__":
    main()
