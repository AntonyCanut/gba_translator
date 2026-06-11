#!/usr/bin/env python3
"""One-shot data fix: live English strings + control-code corruption (T-58).

Fixes, across the three layers (combined_fr.txt, trilingual CSV,
translation_ready JSON):

* 0xA4CAF1  move-panel "+" indicator — the recorded translation was the
  bogus token text "{FC01}{FC03}" which rendered "?FC03?" next to the
  arrow; restore the byte-exact English string (nothing to translate).
* 0x1F2DBA3 "<X>! Use <Y>!" scripted battle command (Terhal/Bélier) —
  never extracted into any layer; budget 13 bytes, no room for
  "Utilise", so "X ! Y !" (the pattern already used by Floette).
* 0x3FD3B1/0x3FD3E4 "<class> <name> sent out <mon>!" — the combined/CSV
  rows recorded the ENGLISH text as the translation; now "envoie".
* 0x7F246C/0x7F24BF Floette scripted-battle copies embedded in battle
  scripts (sub-offset pointers) — translated like their 0x7F2419 sibling.
* 0x3FE791  battle Yes/No — "Oui/Non" fits the slot exactly.
* 0x7760E3  "Sandslash: Slash!" cry — species name localised.
* 0x1F8D540 "que <il/elle>" → "qu'<il/elle>" elision (pronoun buffer).
* 0x3FB2B6  trailing break drifted <0xFB>→<0xFA>; restored.
* 0x3FCA49  ability-blocks-move battle string — tokens were stored in
  French word order but replacement is positional; rephrased to follow
  the ROM buffer order (name, ability, attacker, move).
* 0x755647→0x75565A and 0x75C7FF→0x75C811 re-anchors: the old entries
  swallowed script bytecode/struct bytes decoded as text; rewrap then
  collapsed the "spaces" (raw 0x00/0xFE bytes), shifting a trainerbattle
  script by two bytes. The entries now start at the real text, which a
  script pointer targets directly.
"""

from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.rom_reader import ROMReader
from src.core.padding_detector import PaddingDetector
from src.core.text_codec import TextDecoder, TextEncoder

ROOT = Path(__file__).resolve().parents[1]
COMBINED = ROOT / 'combined_fr.txt'
CSV_PATH = ROOT / 'output/translation/2026-01-15_trilingual_translation.csv'
JSON_PATH = ROOT / 'output/translation/2026-06-11_translation_ready.json'
EN_ROM = ROOT / 'input/roms/englishrom.gba'

# offset -> (translation in JSON form, category) ; None translation keeps EN
FIXES: dict[int, tuple[str, str]] = {
    0xA4CAF1: ('<0xFC><0x01><0x07><0xFC><0x03><0x06>+', 'description'),
    0x1F2DBA3: ('<0xFD><0x02> ! <0xFD><0x03> !', 'dialogue'),
    0x3FD3B1: (
        '<0xFD><0x1C> <0xFD><0x1D> envoie\n<0xFD><0x06> !<0xFC><0x08><0x3C>',
        'dialogue',
    ),
    0x3FD3E4: ('<0xFD><0x1C> <0xFD><0x1D> envoie\n<0xFD><0x00> !', 'dialogue'),
    0x7F246C: (
        '<0xFC><0x01><0x08>Floette ! Blizzard Floral !', 'dialogue',
    ),
    0x7F24BF: (
        '<0xFC><0x01><0x08>Floette ! Blizzard Floral !', 'dialogue',
    ),
    0x3FE791: (
        '<0xFC><0x05><0x05><0xFC><0x04><0x0D><0x0E><0x0F>Oui\nNon',
        'description',
    ),
    0x7760E3: ('Sablaireau: <0xFC><0x01><0x06>Slash !', 'dialogue'),
    0x1F8D540: (
        'Félicitations pour ta série de\nvictoires, challenger !<0xFB>'
        "Le <0xFD><0x02> a fait savoir\nqu'<0xFD><0x03> est impressionné "
        'par toi.<0xFB><0xFD><0x04> voit ton talent, et\n<0xFD><0x03> veut '
        'te défier !<0xFB>Es-tu prêt à affronter le\n<0xFD><0x02> ?',
        'dialogue',
    ),
    0x3FB2B6: ("<0xFD><0x00> tente d'apprendre\n<0xFD><0x01>.<0xFB>", 'dialogue'),
    0x3FCA49: (
        "<0xFD><0x10>, avec <0xFD><0x19>,\nempêche <0xFD><0x13><0xFA>"
        "d'utiliser <0xFD><0x00> !",
        'dialogue',
    ),
    0x75565A: (
        'Que font les gens quand ils\ndoivent aller aux toilettes ?<0xFB>'
        "Et si ça mord pendant que j'y\nsuis ? Je ne peux pas y aller...",
        'dialogue',
    ),
    0x75C811: (
        'Tu as entendu, <0xFD><0x01> ?<0xFB>On dirait que des Pokémon sont\n'
        'piégés dans cette cage là-bas !<0xFB>Allons voir ça.',
        'dialogue',
    ),
}

# entries whose old anchor swallowed script/struct bytes — drop them
REMOVED = {0x755647, 0x75C7FF}


def en_string(rom: bytes, offset: int) -> bytes:
    end = offset
    while rom[end] != 0xFF:
        end += 1
    return bytes(rom[offset:end])


def to_combined(text: str) -> str:
    return (
        text.replace('<0xFA>', r'\l')
            .replace('<0xFB>', r'\p')
            .replace('\n', r'\n')
    )


def main() -> int:
    reader = ROMReader(str(EN_ROM))
    reader.load()
    en = reader.rom_data
    detector = PaddingDetector(reader)

    budgets: dict[int, tuple[int, int, str]] = {}
    for offset, (translation, _cat) in FIXES.items():
        raw = en_string(en, offset)
        encoded = TextEncoder.encode_pokemon(translation)
        length = len(encoded) - 1  # strip terminator
        padding = detector.detect_padding(offset, len(raw), extended_search=True)
        budget = len(raw) + padding
        ok = length <= budget
        original = TextDecoder.decode_pokemon(raw, preserve_unknown=True)
        budgets[offset] = (length, len(raw), original)
        print(f'0x{offset:06X}: {length:3d} / budget {budget:3d} '
              f'({"OK" if ok else "TOO LONG"})')
        if not ok:
            return 1

    # ---- JSON --------------------------------------------------------
    data = json.loads(JSON_PATH.read_text(encoding='utf-8'))
    items = data['translations']
    items = [it for it in items if it['offset'] not in REMOVED]
    by_off = {it['offset']: it for it in items}
    for offset, (translation, cat) in FIXES.items():
        length, orig_len, original = budgets[offset]
        entry = by_off.get(offset)
        if entry is None:
            entry = {
                'offset': offset,
                'original_text': original,
                'translation': translation,
                'length': length,
                'original_length': orig_len,
                'padding_used': length - orig_len,
                'encoding': 'pokemon',
                'category': cat,
                'notes': '',
                'too_long': False,
            }
            items.append(entry)
            by_off[offset] = entry
        else:
            entry['translation'] = translation
            entry['length'] = length
            entry['original_length'] = orig_len
            entry['padding_used'] = length - orig_len
            entry['too_long'] = False
    items.sort(key=lambda it: it['offset'])
    data['translations'] = items
    data['total_translations'] = len(items)
    JSON_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8'
    )
    print(f'JSON: {len(items)} entries')

    # ---- CSV ---------------------------------------------------------
    with CSV_PATH.open(newline='', encoding='utf-8-sig') as handle:
        rows = list(csv.reader(handle))
    header, body = rows[0], rows[1:]
    body = [r for r in body if int(r[0], 16) not in REMOVED]
    seen = set()
    for row in body:
        offset = int(row[0], 16)
        if offset in FIXES:
            row[8] = FIXES[offset][0]
            seen.add(offset)
    for offset, (translation, cat) in FIXES.items():
        if offset in seen:
            continue
        length, orig_len, original = budgets[offset]
        padding = detector.detect_padding(offset, orig_len, extended_search=True)
        body.append([
            f'0x{offset:08X}', original, original, str(orig_len),
            str(padding), str(orig_len + padding), 'pokemon', cat,
            translation, '',
        ])
    body.sort(key=lambda r: int(r[0], 16))
    with CSV_PATH.open('w', newline='', encoding='utf-8-sig') as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(body)
    print(f'CSV: {len(body)} rows')

    # ---- combined ----------------------------------------------------
    line_re = re.compile(r'^0x([0-9A-Fa-f]+):')
    out_lines = []
    handled = set()
    for line in COMBINED.read_text(encoding='utf-8').splitlines():
        match = line_re.match(line)
        if match:
            offset = int(match.group(1), 16)
            if offset in REMOVED:
                continue
            if offset in FIXES:
                line = f'0x{offset:X}: {to_combined(FIXES[offset][0])}'
                handled.add(offset)
        out_lines.append(line)
    for offset, (translation, _cat) in FIXES.items():
        if offset not in handled:
            out_lines.append(f'0x{offset:X}: {to_combined(translation)}')
    COMBINED.write_text('\n'.join(out_lines) + '\n', encoding='utf-8')
    print(f'combined: {len(out_lines)} lines')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
