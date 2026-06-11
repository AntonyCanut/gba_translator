#!/usr/bin/env python3
"""Resolve translation tokens that can never come from the English queue.

* ``{LV}`` is the printable "Lv." ligature glyph ``<0x34>`` — a glyph, not
  a control sequence, so the positional queue never holds it. Under the
  old FA/FB-queue bug it silently swallowed a break (page-clear mid-
  sentence in the badge speeches); now it would stay literal. Replace it
  with the glyph everywhere (31 occurrences).
* Entries whose ``{COLOR}X`` markers outnumber the English colour
  sequences keep the surplus markers literal ("?COLOR?É" on screen).
  The marker letter is the decoded colour argument byte (É=0x06,
  Ë=0x08, Ç=0x04, Á=0x02…), so each marker is rewritten as the explicit
  ``<0xFC><0x01><0xNN>`` code.

Every JSON entry is then re-resolved through the builder's placeholder
logic; the script fails if any ``{token}`` would still print literally.
"""

from __future__ import annotations

import csv
import importlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.text_codec import TextDecoder, TextEncoder

builder_module = importlib.import_module(
    'src.translators.19_build_translated_rom_generic'
)
Builder = builder_module.TranslatedROMBuilder

ROOT = Path(__file__).resolve().parents[1]
COMBINED = ROOT / 'combined_fr.txt'
CSV_PATH = ROOT / 'output/translation/2026-01-15_trilingual_translation.csv'
JSON_PATH = ROOT / 'output/translation/2026-06-11_translation_ready.json'
EN_ROM = ROOT / 'input/roms/englishrom.gba'

COLOR_MARKER_RE = re.compile(r'\{COLOR\}(.)')

# The marker letter is the FRLG international charmap glyph at the colour
# argument byte (0x01='À' … 0x08='Ë'), a convention verified against the
# entries whose markers DID resolve positionally: {COLOR}É ↔ FC 01 06
# (Rock Smash), {COLOR}Á ↔ FC 01 02 (ADM), {COLOR}Ë ↔ FC 01 08.
MARKER_TO_COLOR_ARG = {
    'À': 0x01, 'Á': 0x02, 'Â': 0x03, 'Ç': 0x04,
    'È': 0x05, 'É': 0x06, 'Ê': 0x07, 'Ë': 0x08,
}


def explicit_colors(text: str) -> str:
    def repl(match: re.Match) -> str:
        byte = MARKER_TO_COLOR_ARG.get(match.group(1))
        if byte is None:
            return match.group(0)
        return f'<0xFC><0x01><0x{byte:02X}>'

    return COLOR_MARKER_RE.sub(repl, text)


# Entries needing a full rewrite: wrong buffer order or stray tokens the
# queue can never satisfy ({EVIL_TEAM} next to the plural-s buffer FD08).
SPECIAL_REWRITES = {
    0x1F93EF6: (
        "Tu n'as pas triomphé\n<0xFC><0x01><0x06><0xFD><0x02>"
        '<0xFC><0x01><0x04> fois dans les installations<0xFA>de combat.<0xFB>'
        'Il te faudra <0xFC><0x01><0x06><0xFD><0x04><0xFC><0x01><0x04> '
        "victoire<0xFD><0x08> de plus\npour que l'ethos du combat<0xFA>"
        'fusionne avec ton âme.'
    ),
}


def main() -> int:
    en = EN_ROM.read_bytes()

    def en_text_raw(offset: int):
        end = offset
        while en[end] != 0xFF:
            end += 1
        raw = bytes(en[offset:end])
        return TextDecoder.decode_pokemon(raw, preserve_unknown=True), raw.hex()

    data = json.loads(JSON_PATH.read_text(encoding='utf-8'))
    changed: dict[int, str] = {}
    unresolved = []
    for item in data['translations']:
        translation = item.get('translation') or ''
        if not translation:
            continue
        offset = item['offset']
        new = SPECIAL_REWRITES.get(offset, translation).replace('{LV}', '<0x34>')
        if '{' in new:
            text, raw = en_text_raw(offset)
            resolved = Builder._apply_control_placeholders(new, text, raw)
            if '{COLOR}' in resolved:
                new = explicit_colors(new)
                resolved = Builder._apply_control_placeholders(new, text, raw)
            leftover = re.findall(r'\{[^}]*\}', resolved)
            if leftover:
                unresolved.append((offset, leftover, new[:90]))
        if new != translation:
            item['translation'] = new
            changed[offset] = new
    print(f'JSON translations rewritten: {len(changed)}')
    for offset, leftover, head in unresolved:
        print(f'  STILL UNRESOLVED 0x{offset:06X}: {leftover} {head!r}')
    if unresolved:
        return 1
    JSON_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8'
    )

    # mirror into CSV
    with CSV_PATH.open(newline='', encoding='utf-8-sig') as handle:
        rows = list(csv.reader(handle))
    header, body = rows[0], rows[1:]
    touched = 0
    for row in body:
        offset = int(row[0], 16)
        if offset in changed:
            row[8] = changed[offset]
            touched += 1
    with CSV_PATH.open('w', newline='', encoding='utf-8-sig') as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(body)
    print(f'CSV rows updated: {touched}')

    # mirror into combined (same text, \n / \l / \p escapes)
    def to_combined(text: str) -> str:
        return (
            text.replace('<0xFA>', r'\l')
                .replace('<0xFB>', r'\p')
                .replace('\n', r'\n')
        )

    line_re = re.compile(r'^0x([0-9A-Fa-f]+):')
    out_lines = []
    touched = 0
    for line in COMBINED.read_text(encoding='utf-8').splitlines():
        match = line_re.match(line)
        if match:
            offset = int(match.group(1), 16)
            if offset in changed:
                line = f'0x{offset:X}: {to_combined(changed[offset])}'
                touched += 1
        out_lines.append(line)
    COMBINED.write_text('\n'.join(out_lines) + '\n', encoding='utf-8')
    print(f'combined lines updated: {touched}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
