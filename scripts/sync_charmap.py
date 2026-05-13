#!/usr/bin/env python3
"""
Synchronise the canonical Python charmap to the TypeScript copies.

Usage:
    python3 scripts/sync_charmap.py          # generate + verify
    python3 scripts/sync_charmap.py --check  # verify only (CI mode)
"""

from __future__ import annotations

import argparse
import os
import sys
import unicodedata
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.text.charmap_data import (  # noqa: E402
    BYTE_TO_CHAR,
    CHAR_TO_BYTE,
    CONTROL_CODES,
    POKEMON_NEWLINE,
    POKEMON_TERMINATOR,
)

EMULATOR_TS = ROOT / "emulator-web" / "src" / "charmap.ts"
E2E_TS = ROOT / "tests" / "e2e-playwright" / "helpers" / "charmap.ts"

FRENCH_ACCENTS = list("éèêëàâçùûüîïôœ")


def _hex(value: int) -> str:
    return f"0x{value:02x}"


def _escape_char(char: str) -> str:
    if char == "'":
        return "\"'\""
    if char == "\n":
        return "'\\n'"
    if char == "\\":
        return "'\\\\'"
    return f"'{char}'"


def _group_entries(byte_to_char: Dict[int, str]) -> List[Tuple[str, List[Tuple[int, str]]]]:
    groups: List[Tuple[str, List[Tuple[int, str]]]] = [
        ("", []),        # space
        ("Digits", []),
        ("Punctuation", []),
        ("Uppercase", []),
        ("Lowercase", []),
        ("Accented (CFRU/Unbound extended)", []),
        ("Newline", []),
    ]

    for byte_val, char in sorted(byte_to_char.items()):
        if char == '\n':
            groups[6][1].append((byte_val, char))
        elif char == ' ':
            groups[0][1].append((byte_val, char))
        elif char.isdigit():
            groups[1][1].append((byte_val, char))
        elif char.isalpha() and char.isupper() and unicodedata.category(char) == 'Lu' and ord(char) < 128:
            groups[3][1].append((byte_val, char))
        elif char.isalpha() and char.islower() and unicodedata.category(char) == 'Ll' and ord(char) < 128:
            groups[4][1].append((byte_val, char))
        elif char.isalpha():
            groups[5][1].append((byte_val, char))
        else:
            groups[2][1].append((byte_val, char))

    return [(label, entries) for label, entries in groups if entries]


def _render_byte_to_char_entries(byte_to_char: Dict[int, str]) -> str:
    lines: list[str] = []
    groups = _group_entries(byte_to_char)

    for label, entries in groups:
        if label:
            lines.append(f"  // {label}")

        items_per_line = 5 if len(entries) > 3 else len(entries)
        for i in range(0, len(entries), items_per_line):
            chunk = entries[i:i + items_per_line]
            parts = [f"[{_hex(b)}, {_escape_char(c)}]" for b, c in chunk]
            line = "  " + ", ".join(parts) + ","
            lines.append(line)

    return "\n".join(lines)


def _render_control_code_switch(control_codes: Dict[int, int]) -> str:
    cases: list[str] = []
    for leader, length in sorted(control_codes.items()):
        cases.append(f"    case {_hex(leader)}: return {length};")
    cases.append("    default: return 1;")
    return "\n".join(cases)


def _render_multi_byte_leaders(control_codes: Dict[int, int]) -> str:
    items = [_hex(leader) for leader in sorted(control_codes.keys())]
    return ", ".join(items)


def generate_emulator_ts(byte_to_char: Dict[int, str], control_codes: Dict[int, int]) -> str:
    entries = _render_byte_to_char_entries(byte_to_char)
    leaders = _render_multi_byte_leaders(control_codes)
    switch_body = _render_control_code_switch(control_codes)

    return f"""\
export const POKEMON_TERMINATOR = {_hex(POKEMON_TERMINATOR)};
export const POKEMON_NEWLINE = {_hex(POKEMON_NEWLINE)};

const BYTE_TO_CHAR: Map<number, string> = new Map([
{entries}
]);

const MULTI_BYTE_LEADERS = new Set([{leaders}]);

function controlCodeLength(leader: number): number {{
  switch (leader) {{
{switch_body}
  }}
}}

export function decodePokemonText(
  data: Uint8Array,
  preserveUnknown = false,
): string {{
  const result: string[] = [];
  let i = 0;
  while (i < data.length) {{
    const byte = data[i];
    if (byte === POKEMON_TERMINATOR) break;

    if (MULTI_BYTE_LEADERS.has(byte)) {{
      const skip = controlCodeLength(byte);
      i += skip;
      continue;
    }}

    const char = BYTE_TO_CHAR.get(byte);
    if (char !== undefined) {{
      result.push(char);
    }} else if (preserveUnknown) {{
      result.push(`<0x${{byte.toString(16).toUpperCase().padStart(2, '0')}}>`);
    }} else {{
      result.push('?');
    }}
    i++;
  }}
  return result.join('');
}}

export function encodePokemonText(text: string): Uint8Array {{
  const CHAR_TO_BYTE = new Map<string, number>();
  for (const [byte, char] of BYTE_TO_CHAR) {{
    if (!CHAR_TO_BYTE.has(char)) {{
      CHAR_TO_BYTE.set(char, byte);
    }}
  }}

  const bytes: number[] = [];
  for (const char of text) {{
    const byte = CHAR_TO_BYTE.get(char);
    if (byte !== undefined) {{
      bytes.push(byte);
    }} else {{
      bytes.push(0xac); // '?' fallback
    }}
  }}
  bytes.push(POKEMON_TERMINATOR);
  return new Uint8Array(bytes);
}}
"""


def generate_e2e_ts(byte_to_char: Dict[int, str], control_codes: Dict[int, int]) -> str:
    entries = _render_byte_to_char_entries(byte_to_char)
    leaders = _render_multi_byte_leaders(control_codes)
    switch_body = _render_control_code_switch(control_codes)

    return f"""\
export const POKEMON_TERMINATOR = {_hex(POKEMON_TERMINATOR)};
export const POKEMON_NEWLINE = {_hex(POKEMON_NEWLINE)};

const BYTE_TO_CHAR: Map<number, string> = new Map([
{entries}
]);

const CHAR_TO_BYTE: Map<string, number> = new Map();
for (const [byte, char] of BYTE_TO_CHAR) {{
  if (!CHAR_TO_BYTE.has(char)) {{
    CHAR_TO_BYTE.set(char, byte);
  }}
}}

const MULTI_BYTE_LEADERS = new Set([{leaders}]);

function controlCodeLength(leader: number): number {{
  switch (leader) {{
{switch_body}
  }}
}}

export function decodePokemonText(data: Uint8Array): string {{
  const result: string[] = [];
  let i = 0;
  while (i < data.length) {{
    const byte = data[i];
    if (byte === POKEMON_TERMINATOR) break;

    if (MULTI_BYTE_LEADERS.has(byte)) {{
      i += controlCodeLength(byte);
      continue;
    }}

    const char = BYTE_TO_CHAR.get(byte);
    if (char !== undefined) {{
      result.push(char);
    }} else {{
      result.push('?');
    }}
    i++;
  }}
  return result.join('');
}}

export function encodePokemonText(text: string): Uint8Array {{
  const bytes: number[] = [];
  for (const char of text) {{
    const byte = CHAR_TO_BYTE.get(char);
    if (byte !== undefined) {{
      bytes.push(byte);
    }} else {{
      bytes.push(0xac); // '?' fallback
    }}
  }}
  bytes.push(POKEMON_TERMINATOR);
  return new Uint8Array(bytes);
}}

export function hexToBytes(hex: string): Uint8Array {{
  const bytes = new Uint8Array(hex.length / 2);
  for (let i = 0; i < hex.length; i += 2) {{
    bytes[i / 2] = parseInt(hex.substring(i, i + 2), 16);
  }}
  return bytes;
}}
"""


def count_french_accents(char_to_byte: Dict[str, int]) -> Tuple[List[str], List[str]]:
    present = [a for a in FRENCH_ACCENTS if a in char_to_byte]
    missing = [a for a in FRENCH_ACCENTS if a not in char_to_byte]
    return present, missing


def sync(check_only: bool = False) -> bool:
    targets = [
        (EMULATOR_TS, generate_emulator_ts),
        (E2E_TS, generate_e2e_ts),
    ]

    present_accents, missing_accents = count_french_accents(CHAR_TO_BYTE)

    print("=" * 60)
    print("sync_charmap.py — Python → TypeScript charmap synchronisation")
    print("=" * 60)
    print()
    print(f"  CHAR_TO_BYTE entries : {len(CHAR_TO_BYTE)}")
    print(f"  BYTE_TO_CHAR entries : {len(BYTE_TO_CHAR)}")
    print(f"  Control codes        : {len(CONTROL_CODES)} ({', '.join(_hex(k) for k in sorted(CONTROL_CODES))})")
    print(f"  Terminator           : {_hex(POKEMON_TERMINATOR)}")
    print(f"  Newline              : {_hex(POKEMON_NEWLINE)}")
    print(f"  FR accents present   : {len(present_accents)}/{len(FRENCH_ACCENTS)} ({' '.join(present_accents)})")
    if missing_accents:
        print(f"  FR accents MISSING   : {' '.join(missing_accents)}")
    print()

    all_ok = True

    for path, generator in targets:
        generated = generator(BYTE_TO_CHAR, CONTROL_CODES)
        rel = path.relative_to(ROOT)

        if not path.parent.exists():
            if check_only:
                print(f"  FAIL  {rel} — parent directory missing")
                all_ok = False
                continue
            path.parent.mkdir(parents=True, exist_ok=True)

        if path.exists():
            existing = path.read_text(encoding="utf-8")
            if existing == generated:
                print(f"  OK    {rel} — already in sync")
                continue
            else:
                if check_only:
                    print(f"  DRIFT {rel} — file differs from generated")
                    all_ok = False
                    continue
                print(f"  WRITE {rel} — updated")
        else:
            if check_only:
                print(f"  MISS  {rel} — file does not exist")
                all_ok = False
                continue
            print(f"  WRITE {rel} — created")

        path.write_text(generated, encoding="utf-8")

    print()
    if all_ok:
        print("All files in sync.")
    elif check_only:
        print("DRIFT DETECTED — run `python3 scripts/sync_charmap.py` to fix.")
    else:
        print("Files synchronised.")

    return all_ok


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync Python charmap → TypeScript")
    parser.add_argument("--check", action="store_true", help="Check only, do not write")
    args = parser.parse_args()

    ok = sync(check_only=args.check)
    if not ok and args.check:
        sys.exit(1)


if __name__ == "__main__":
    main()
