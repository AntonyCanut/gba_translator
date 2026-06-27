#!/usr/bin/env python3
"""List auto-generated error tickets from Playwright test runs."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

TICKETS_DIR = Path(__file__).resolve().parent.parent / "tickets"

SEVERITY_ORDER = {"critical": 0, "major": 1, "minor": 2}
STATUS_SYMBOLS = {"open": "[ ]", "in_progress": "[~]", "resolved": "[x]"}


def parse_yaml_field(content: str, field: str) -> str:
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith(f"{field}:"):
            value = stripped[len(field) + 1 :].strip()
            return value.strip('"').strip("'")
    return ""


def list_tickets(
    tickets_dir: Path,
    status_filter: str | None = None,
    category_filter: str | None = None,
    severity_filter: str | None = None,
) -> list[dict[str, str]]:
    if not tickets_dir.exists():
        return []

    tickets = []
    for ticket_file in sorted(tickets_dir.glob("*.yaml")):
        content = ticket_file.read_text(encoding="utf-8")
        ticket = {
            "file": ticket_file.name,
            "title": parse_yaml_field(content, "title"),
            "category": parse_yaml_field(content, "category"),
            "severity": parse_yaml_field(content, "severity"),
            "status": parse_yaml_field(content, "status"),
            "source_test": parse_yaml_field(content, "source_test"),
            "created": parse_yaml_field(content, "created"),
        }

        if status_filter and ticket["status"] != status_filter:
            continue
        if category_filter and ticket["category"] != category_filter.upper():
            continue
        if severity_filter and ticket["severity"] != severity_filter:
            continue

        tickets.append(ticket)

    tickets.sort(key=lambda t: SEVERITY_ORDER.get(t["severity"], 99))
    return tickets


def print_tickets(tickets: list[dict[str, str]]) -> None:
    if not tickets:
        print("No tickets found.")
        return

    print(f"\n{'='*80}")
    print(f"  Tickets ({len(tickets)} found)")
    print(f"{'='*80}\n")

    current_severity = ""
    for ticket in tickets:
        if ticket["severity"] != current_severity:
            current_severity = ticket["severity"]
            print(f"  --- {current_severity.upper()} ---\n")

        symbol = STATUS_SYMBOLS.get(ticket["status"], "[ ]")
        print(f"  {symbol} {ticket['file']}")
        print(f"      {ticket['title']}")
        print(f"      Category: {ticket['category']} | Severity: {ticket['severity']}")
        print(f"      Test: {ticket['source_test']}")
        print(f"      Created: {ticket['created']}")
        print()

    by_status = {}
    for t in tickets:
        by_status.setdefault(t["status"], []).append(t)

    print(f"{'='*80}")
    print(f"  Summary:")
    for status, group in sorted(by_status.items()):
        print(f"    {status}: {len(group)}")
    print(f"{'='*80}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="List auto-generated tickets")
    parser.add_argument(
        "--dir",
        type=Path,
        default=TICKETS_DIR,
        help="Tickets directory (default: tickets/)",
    )
    parser.add_argument(
        "--status",
        choices=["open", "in_progress", "resolved"],
        help="Filter by status",
    )
    parser.add_argument("--category", help="Filter by category (e.g. CRASH, WRONG_TEXT)")
    parser.add_argument(
        "--severity",
        choices=["critical", "major", "minor"],
        help="Filter by severity",
    )
    parser.add_argument("--json", action="store_true", help="JSON output")

    args = parser.parse_args()

    tickets = list_tickets(args.dir, args.status, args.category, args.severity)

    if args.json:
        import json

        print(json.dumps(tickets, indent=2, ensure_ascii=False))
    else:
        print_tickets(tickets)

    sys.exit(0 if not any(t["status"] == "open" and t["severity"] == "critical" for t in tickets) else 1)


if __name__ == "__main__":
    main()
