#!/usr/bin/env python3
"""Resolve an auto-generated error ticket."""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

TICKETS_DIR = Path(__file__).resolve().parent.parent / "tickets"


def find_ticket(tickets_dir: Path, ticket_id: str) -> Path | None:
    if not tickets_dir.exists():
        return None

    normalized = ticket_id.lower().strip()

    for ticket_file in tickets_dir.glob("*.yaml"):
        if normalized in ticket_file.name.lower():
            return ticket_file

    for ticket_file in tickets_dir.glob("*.yaml"):
        content = ticket_file.read_text(encoding="utf-8")
        title_match = re.search(r"^title:\s*(.+)$", content, re.MULTILINE)
        if title_match and normalized in title_match.group(1).lower():
            return ticket_file

    return None


def resolve_ticket(ticket_path: Path, resolution: str = "") -> bool:
    content = ticket_path.read_text(encoding="utf-8")

    if "status: resolved" in content or 'status: "resolved"' in content:
        print(f"Ticket {ticket_path.name} is already resolved.")
        return False

    content = re.sub(
        r'^status:\s*.+$',
        'status: "resolved"',
        content,
        count=1,
        flags=re.MULTILINE,
    )

    resolved_at = datetime.now(timezone.utc).isoformat()
    content = content.rstrip("\n") + "\n"
    content += f'resolved_at: "{resolved_at}"\n'

    if resolution:
        content += f'resolution: "{resolution}"\n'

    ticket_path.write_text(content, encoding="utf-8")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Resolve an auto-generated ticket")
    parser.add_argument("ticket_id", help="ID or partial name of the ticket to resolve")
    parser.add_argument(
        "--dir",
        type=Path,
        default=TICKETS_DIR,
        help="Tickets directory (default: tickets/)",
    )
    parser.add_argument(
        "--resolution",
        "-r",
        default="",
        help="Resolution message",
    )

    args = parser.parse_args()

    ticket_path = find_ticket(args.dir, args.ticket_id)
    if not ticket_path:
        print(f"Ticket not found: {args.ticket_id}")
        sys.exit(1)

    print(f"Resolving ticket: {ticket_path.name}")

    if resolve_ticket(ticket_path, args.resolution):
        print(f"Ticket resolved successfully.")
    else:
        print(f"Ticket could not be resolved.")
        sys.exit(1)


if __name__ == "__main__":
    main()
