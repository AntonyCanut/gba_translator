#!/usr/bin/env python3
"""Clean overused ellipsis characters in combined_fr.txt.

Context:
  - The game renders a special « … » (ellipsis) character that saves 2 bytes
    compared to three ASCII dots « ... ».
  - The « ... » are sometimes used excessively / placed arbitrarily
    (dot runs « … … … … », « ……… ……… ……… », duplicates « …… »)
    and do not serve the dialogue.

Policy (safe — only shortens strings, so no pointer overflow; never removes
an isolated ellipsis that serves the dialogue):
  T1  Three or more ASCII dots « ... » -> « … » (saves 2 bytes per occurrence).
  T2  Any RUN of 2 or more ellipses separated only by spaces
      (« …… », « … … », « ……… », « … … … … ») -> a single « … ».
      (Keeps a single pause/beat, removes dot spam.)
  T3  Space(s) between the preceding WORD and « … » when NO word is attached
      after the ellipsis (« Non … » -> « Non… », « vu … rien » -> « vu… rien »)
      -> attach the ellipsis to the preceding word.
      Preserved cases: a word attached AFTER (« vu …rien » = leading ellipsis ->
      the preceding space stays) and an opening punctuation / dialogue dash
      before the space (« « … », « — … ») whose space is typographic.

DOES NOT TOUCH:
  - an isolated ellipsis « … » (hesitation, open ending — serves the dialogue);
  - pause beats on separate pages « …\\p… » (intentional rhythm);
  - control codes ({...}, \\n \\p \\l) — none contain dots.

Surgical insertion: only lines containing ellipsis characters are modified;
everything else (offsets, formatting, LF line endings) is preserved byte for byte.
"""
import argparse
import re
import sys

# Run of ellipses (… or already-normalized ...) separated by spaces.
RUN = re.compile(r'…(?:[ \t]*…)+')
# 3 or more ASCII dots.
ASCII_DOTS = re.compile(r'\.{3,}')
# Characters that, just before the space, KEEP the space: opening punctuation,
# quotation marks, apostrophes, dialogue dashes (the space is typographic,
# not a "preceding word").
_KEEP_BEFORE = '«(""“‘\'’[{¿¡—–-…'
# T3: space(s) between a word and « … » when no word is attached after
# the ellipsis (negative lookahead `\w`). The pattern REQUIRES a real content
# character before the space (group 1) — so it never acts on leading format
# spaces or spaces after opening punctuation.
SPACE_BEFORE = re.compile(
    r'([^\s' + re.escape(_KEEP_BEFORE) + r'])[ \t]+…(?!\w)')


def clean_body(body: str) -> str:
    # T1: ASCII -> ellipsis character (saves 2 bytes per occurrence).
    body = ASCII_DOTS.sub('…', body)
    # T2: run of 2+ ellipses -> single one.
    body = RUN.sub('…', body)
    # T3: attach « … » to the preceding word if no word is attached after.
    body = SPACE_BEFORE.sub(r'\1…', body)
    return body


def transform_line(line: str) -> str:
    # Preserve the « 0xOFFSET: » prefix (no dots/ellipses there anyway).
    idx = line.find(':')
    if idx < 0:
        return clean_body(line)
    prefix, body = line[:idx + 1], line[idx + 1:]
    return prefix + clean_body(body)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('path', nargs='?', default="languages/fr/combined_fr.txt")
    ap.add_argument('--apply', action='store_true',
                    help='write modifications (otherwise dry-run + diff)')
    ap.add_argument('--max-show', type=int, default=0,
                    help='max number of modified entries to display (0 = all)')
    args = ap.parse_args()

    with open(args.path, encoding='utf-8') as fh:
        lines = fh.read().split('\n')

    changed = []
    for i, line in enumerate(lines):
        if '...' not in line and '…' not in line:
            continue
        new = transform_line(line)
        if new != line:
            changed.append((i, line, new))
            lines[i] = new

    print(f'Entries modified: {len(changed)}')
    shown = changed if args.max_show == 0 else changed[:args.max_show]
    for i, old, new in shown:
        off = old.split(':', 1)[0]
        print(f'\n--- {off} (line {i + 1})')
        print(f'  BEFORE: {old[:200]}')
        print(f'  AFTER:  {new[:200]}')

    if args.apply:
        with open(args.path, 'w', encoding='utf-8') as fh:
            fh.write('\n'.join(lines))
        print(f'\nWritten {args.path} ({len(changed)} entries cleaned).')
    else:
        print('\n[dry-run] Rerun with --apply to write.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
