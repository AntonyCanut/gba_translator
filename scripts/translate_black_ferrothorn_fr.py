#!/usr/bin/env python3
"""Translate the 'Black Ferrothorn' gang name to French.

Black Ferrothorn(s) -> Noirépine   (single-word coined name: noir + épine,
already established for the location it controls, "Black Ferrothorn Turf"
-> "Territoire Noirépine", see the v2 toponym pass / F-58/F-60).

Ferrothorn's official FR Pokemon name is "Noacier" -- not reused here because
the gang name is a distinct in-universe proper noun (the rival "Granbull
Terreur" gang and "Roitiflam Noir" gang are likewise not literal Pokemon
names with a postposed adjective glued on), and "Noacier Noir" would be a
redundant black-on-black ("noir" is already baked into "Noacier").

When the EN source splits the two words across a line/scroll/page break
(\\n, \\l, \\p) -- e.g. "Black\\pFerrothorn" -- the break is preserved and
relocated to immediately *before* the merged word, so the number of breaks
(and therefore the page/box count) in the string is unchanged:
"Black\\pFerrothorns" -> "\\pNoirépine".

Only the LAST occurrence of each offset is edited (combined_fr.txt last-wins).
0x1F71D6A was a stray half-translation ("Ferrothorn Noir", missing "Black")
and is folded into the same pattern.
"""
import re
import sys
from pathlib import Path

PATH = Path(__file__).resolve().parents[1] / "languages/fr/combined_fr.txt"
LINE_RE = re.compile(r'^\s*0x([0-9A-Fa-f]+)\s*:\s*(.*)$')

# "Black<break-or-space>Ferrothorn(s)?" -> "<break>Noirépine" / "Noirépine"
GANG_BREAK = re.compile(r'Black(\\[nlp])Ferrothorns?')
GANG_SPACE = re.compile(r'Black Ferrothorns?')
# Stray half-translation missing the "Black" word.
STRAY = re.compile(r'\bFerrothorn Noir\b')


def regex_translate(body: str) -> str:
    body = GANG_BREAK.sub(r'\1Noirépine', body)
    body = GANG_SPACE.sub('Noirépine', body)
    body = STRAY.sub('Noirépine', body)
    return body


def main(apply: bool) -> int:
    raw = PATH.read_text(encoding='utf-8')
    lines = raw.split('\n')

    last_occ = {}
    for i, l in enumerate(lines):
        m = LINE_RE.match(l)
        if m:
            last_occ[m.group(1).lower().lstrip('0')] = i

    changed = 0
    problems = []
    for i, l in enumerate(lines):
        m = LINE_RE.match(l)
        if not m:
            continue
        off = m.group(1).lower().lstrip('0')
        body = m.group(2)
        if last_occ[off] != i:
            continue  # only the last occurrence wins
        if not (re.search(r'Black(\\[nlp]| )Ferrothorns?', body) or STRAY.search(body)):
            continue
        before = len(re.findall(r'\{(?!COLOR\})[^}]+\}', body))
        new_body = regex_translate(body)
        after = len(re.findall(r'\{(?!COLOR\})[^}]+\}', new_body))
        if before != after:
            problems.append(f"0x{off}: brace count {before}->{after}")
        if new_body == body:
            continue
        residual = re.sub(r'Noirépine', '', new_body)
        if 'Ferrothorn' in residual or re.search(r'\bBlack\b', residual):
            problems.append(f"0x{off}: residual EN -> {residual[:80]}")
        prefix = l[:l.index(':') + 2]
        lines[i] = prefix + new_body
        changed += 1
        if not apply:
            print(f"--- 0x{off.upper()}")
            print(f"  - {body[:160]}")
            print(f"  + {new_body[:160]}")

    print(f"\n{'APPLIED' if apply else 'DRY-RUN'}: {changed} lines changed")
    if problems:
        print("PROBLEMS:")
        for p in problems:
            print("  ", p)
        return 2
    if apply:
        PATH.write_text('\n'.join(lines), encoding='utf-8')
    return 0


if __name__ == '__main__':
    sys.exit(main(apply='--apply' in sys.argv))
