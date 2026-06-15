#!/usr/bin/env python3
"""Review dialogue page breaks for fluidity (mid-sentence screen clears).

A ``<0xFB>`` page code *pauses and clears the whole message window* before
the next text. When it lands in the middle of a sentence, the continuation
appears on a brand-new screen instead of flowing on the next line:

    Ce Pokémon m'a fait        <-- screen 1
    -- press A, screen clears --
    mal !                      <-- screen 2

A line break (or, past two lines, a scroll) would read far more fluidly.
``src.core.dialogue_linewrap.demote_midsentence_pages`` softens exactly
those page breaks to scrolls at build time (both codes are one byte, so the
ROM length never changes), and ``rewrap`` then re-flows the words across
them. Page breaks that fall on a real sentence boundary, before a
capitalised new sentence/label (signs, location names), or that end on a
runtime buffer are kept — their pacing is deliberate.

This script does NOT modify the ROM or the data: the fix is applied
automatically by the build pipeline (``19_build_translated_rom_generic`` and
``apply_inline_overrides_fr``) through ``rewrap``. It audits the translation
set, predicts every page break the build will now soften, and prints a
before/after preview so the dialogue pass can be reviewed at a glance.

Usage:
    python3 scripts/fix_dialogue_page_breaks.py            # latest build JSON
    python3 scripts/fix_dialogue_page_breaks.py --json <translation_ready.json>
    python3 scripts/fix_dialogue_page_breaks.py --limit 40 # more examples
    python3 scripts/fix_dialogue_page_breaks.py --all      # list every case
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.dialogue_linewrap import (  # noqa: E402
    _LOWER_CONT,
    _SENTENCE_END,
    _TRAILING_BUFFER_RE,
)

# Build-time control codes come in two textual forms in the translation
# set: decoded hex tokens (``<0xNN>``) and named placeholders that the
# builder converts just before wrapping (``{COLOR}``, ``{STR_VAR_1}``…).
# For the sentence-boundary test, both are control bytes to skip over.
_CONTROL_TOKEN = re.compile(r'<0x[0-9A-Fa-f]{2}>|\{[^}]*\}')
_TRAILING_CLOSERS = re.compile(
    r'(?:<0x[0-9A-Fa-f]{2}>|\{[^}]*\}|[\s»"”\'’)\]])+$'
)
_LEADING_CODES = re.compile(r'^(?:<0x[0-9A-Fa-f]{2}>|\{[^}]*\}|\s)+')
_PAGE = '<0xFB>'


def _ends_sentence(page: str) -> bool:
    stripped = page.rstrip()
    if _TRAILING_BUFFER_RE.search(stripped):
        return True
    core = _TRAILING_CLOSERS.sub('', stripped)
    return not core or core[-1] in _SENTENCE_END


def _continues_lower(page: str) -> bool:
    visible = _LEADING_CODES.sub('', page)
    return bool(visible) and visible[0] in _LOWER_CONT


def _is_midsentence_page(before: str, after: str) -> bool:
    """Predict whether the build will soften the page break between them."""
    return not _ends_sentence(before) and _continues_lower(after)


def _latest_translation_json() -> Optional[Path]:
    folder = Path(__file__).resolve().parents[1] / 'output' / 'translation'
    candidates = sorted(folder.glob('*_translation_ready.json'))
    return candidates[-1] if candidates else None


def _preview(text: str) -> str:
    """Render control tokens compactly for a readable terminal preview."""
    return _CONTROL_TOKEN.sub('·', text).replace('\n', ' / ')


def _scan(translations: List[dict]) -> Tuple[int, int, int, List[dict]]:
    dialogues = pages = midsentence = 0
    hits: List[dict] = []
    for item in translations:
        if item.get('category') != 'dialogue' or item.get('encoding') != 'pokemon':
            continue
        text = item.get('translation') or ''
        if _PAGE not in text:
            continue
        dialogues += 1
        parts = text.split(_PAGE)
        for before, after in zip(parts, parts[1:]):
            pages += 1
            if _is_midsentence_page(before, after):
                midsentence += 1
                hits.append({
                    'offset': item.get('offset'),
                    'before': before,
                    'after': after,
                })
    return dialogues, pages, midsentence, hits


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        '--json', type=Path, default=None,
        help='translation_ready.json (default: newest in output/translation/)',
    )
    parser.add_argument(
        '--limit', type=int, default=20,
        help='number of before/after examples to print (default: 20)',
    )
    parser.add_argument(
        '--all', action='store_true',
        help='print every mid-sentence page break, not just --limit',
    )
    args = parser.parse_args()

    path = args.json or _latest_translation_json()
    if not path or not path.exists():
        print('No translation_ready.json found in output/translation/.',
              file=sys.stderr)
        return 1

    data = json.loads(path.read_text(encoding='utf-8'))
    translations = data.get('translations', data if isinstance(data, list) else [])

    dialogues, pages, midsentence, hits = _scan(translations)

    print(f'Source : {path}')
    print(f'Dialogues with page breaks : {dialogues}')
    print(f'Page breaks (<0xFB>)        : {pages}')
    print(f'Mid-sentence screen clears  : {midsentence} '
          f'({midsentence / pages * 100:.1f}% of pages)'
          if pages else 'Mid-sentence screen clears  : 0')
    print(f'  -> softened to a scroll at build time by rewrap()\n')

    shown = hits if args.all else hits[: args.limit]
    for hit in shown:
        off = hit['offset']
        off_hex = f'0x{off:X}' if isinstance(off, int) else off
        print(f'[{off_hex}]')
        print(f'   before clear : …{_preview(hit["before"])[-48:]}')
        print(f'   new screen   : {_preview(hit["after"])[:48]}…')
    if not args.all and len(hits) > len(shown):
        print(f'\n… and {len(hits) - len(shown)} more (use --all to list them).')

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
