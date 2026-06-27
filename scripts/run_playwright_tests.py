#!/usr/bin/env python3
"""Orchestrate Playwright E2E tests with report generation and ticket creation.

1. Start the emulator-web server
2. Run Playwright tests (npx playwright test)
3. Wait for completion
4. Read generated reports
5. Display console summary
6. Return exit code (0 = all pass, 1 = failures)
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EMULATOR_WEB_DIR = PROJECT_ROOT / "emulator-web"
REPORTS_DIR = PROJECT_ROOT / "test-results" / "reports"
TICKETS_DIR = PROJECT_ROOT / "tickets"

SEVERITY_COLORS = {
    "critical": "\033[91m",
    "major": "\033[93m",
    "minor": "\033[90m",
}
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[92m"
RED = "\033[91m"


def start_emulator_server(
    port: int = 3000,
    rom_path: str = "",
) -> subprocess.Popen | None:
    if not EMULATOR_WEB_DIR.exists():
        print("[orchestrator] emulator-web/ not found, skipping server")
        return None

    env = {**os.environ, "PORT": str(port)}
    if rom_path:
        env["ROM_PATH"] = rom_path

    node_modules = EMULATOR_WEB_DIR / "node_modules"
    if not node_modules.exists():
        print("[orchestrator] Installing emulator-web dependencies...")
        subprocess.run(
            ["npm", "install"],
            cwd=str(EMULATOR_WEB_DIR),
            check=True,
            capture_output=True,
        )

    print(f"[orchestrator] Starting emulator server on port {port}...")
    proc = subprocess.Popen(
        ["npx", "tsx", "src/server.ts"],
        cwd=str(EMULATOR_WEB_DIR),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    time.sleep(2)
    if proc.poll() is not None:
        print("[orchestrator] Server failed to start")
        return None

    print(f"[orchestrator] Server started (PID: {proc.pid})")
    return proc


def stop_server(proc: subprocess.Popen | None) -> None:
    if proc is None:
        return
    try:
        proc.send_signal(signal.SIGTERM)
        proc.wait(timeout=5)
    except (subprocess.TimeoutExpired, OSError):
        proc.kill()
    print("[orchestrator] Server stopped")


def run_playwright_tests(extra_args: list[str] | None = None) -> int:
    cmd = ["npx", "playwright", "test"]
    if extra_args:
        cmd.extend(extra_args)

    print(f"\n[orchestrator] Running: {' '.join(cmd)}")
    print("=" * 60)

    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT))

    print("=" * 60)
    return result.returncode


def find_latest_report() -> Path | None:
    if not REPORTS_DIR.exists():
        return None
    json_reports = sorted(REPORTS_DIR.glob("report-*.json"), reverse=True)
    return json_reports[0] if json_reports else None


def display_summary(report_path: Path | None) -> int:
    if report_path is None:
        print("\n[orchestrator] No report found.")
        return 1

    with open(report_path, encoding="utf-8") as f:
        report = json.load(f)

    total = report.get("totalTests", 0)
    passed = report.get("passed", 0)
    failed = report.get("failed", 0)
    skipped = report.get("skipped", 0)
    errors = report.get("errors", [])
    duration = report.get("duration", 0)

    print(f"\n{'='*60}")
    print(f"{BOLD}  PLAYWRIGHT TEST SUMMARY{RESET}")
    print(f"{'='*60}")
    print(f"  ROM: {report.get('rom', '?')}")
    print(f"  Duration: {duration / 1000:.1f}s")
    print()

    pass_color = GREEN if failed == 0 else RED
    print(f"  Total:   {total}")
    print(f"  {GREEN}Passed: {passed}{RESET}")
    if failed > 0:
        print(f"  {RED}Failed: {failed}{RESET}")
    if skipped > 0:
        print(f"  Skipped: {skipped}")

    rate = (passed / total * 100) if total > 0 else 0
    print(f"\n  {pass_color}Success rate: {rate:.1f}%{RESET}")

    if errors:
        print(f"\n{'─'*60}")
        print(f"  ERREURS ({len(errors)}):")
        print(f"{'─'*60}")

        for err in errors:
            sev = err.get("severity", "?")
            color = SEVERITY_COLORS.get(sev, "")
            cat = err.get("category", "?")
            msg = err.get("message", "")[:80]
            print(f"  {color}{err['id']} [{sev}] {cat}{RESET}: {msg}")

    ticket_files = list(TICKETS_DIR.glob("auto-*.yaml")) if TICKETS_DIR.exists() else []
    open_tickets = 0
    for tf in ticket_files:
        content = tf.read_text(encoding="utf-8")
        if "status: open" in content or 'status: "open"' in content:
            open_tickets += 1

    if ticket_files:
        print(f"\n{'─'*60}")
        print(f"  TICKETS: {len(ticket_files)} total, {open_tickets} open")
        print(f"{'─'*60}")

    print(f"\n{'='*60}")

    md_reports = sorted(REPORTS_DIR.glob("report-*.md"), reverse=True) if REPORTS_DIR.exists() else []
    if md_reports:
        print(f"  Detailed report: {md_reports[0]}")

    print(f"  JSON report: {report_path}")
    print(f"{'='*60}\n")

    return 0 if failed == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Orchestrate GBA Translator Playwright tests"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=3000,
        help="Emulator server port (default: 3000)",
    )
    parser.add_argument("--rom", default="", help="Path to the ROM")
    parser.add_argument(
        "--no-server",
        action="store_true",
        help="Do not start the server (already running)",
    )
    parser.add_argument(
        "playwright_args",
        nargs="*",
        help="Extra arguments for Playwright",
    )

    args = parser.parse_args()

    server_proc = None
    try:
        if not args.no_server:
            server_proc = start_emulator_server(args.port, args.rom)

        exit_code = run_playwright_tests(args.playwright_args or None)

        report_path = find_latest_report()
        summary_code = display_summary(report_path)

        return exit_code if exit_code != 0 else summary_code

    except KeyboardInterrupt:
        print("\n[orchestrator] Interrupted by user")
        return 130
    finally:
        stop_server(server_proc)


if __name__ == "__main__":
    sys.exit(main())
