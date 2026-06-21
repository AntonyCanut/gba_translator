#!/usr/bin/env python3
"""Verify the Black Emboar gang translation in the BUILT FR ROM bytes.

For each target offset we find the pointer(s) in the EN ROM (bytes = off+0x08000000),
read the SAME pointer location in the FR ROM (it now holds the relocated address),
follow it, decode the string, and assert:
  - 'Noir' present (translated)
  - 'Black' / 'Emboar' absent (no franglais)
  - for the gender entries: no <0xFD><0x03> / <0xFD><0x02> pronoun bytes
"""
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.core.text_codec import TextDecoder

EN = (ROOT / 'input/roms/englishrom.gba').read_bytes()
FR = (ROOT / 'output/roms/GenedRom-fr.gba').read_bytes()
BASE = 0x08000000


def read_string(rom, off, maxlen=600):
    end = rom.find(b'\xff', off, off + maxlen)
    if end == -1:
        end = off + maxlen
    return rom[off:end + 1]


def decode(b):
    return TextDecoder.decode_pokemon(b, preserve_unknown=True)


# representative live targets (offset, is_gender_entry)
TARGETS = [
    0x7E8841, 0x7E888D, 0x7E9D68, 0x7EA26A, 0x7E9F91, 0x7EA030, 0x7F9F05,
    0x7FBA42, 0x7FCB63, 0x7E91E6, 0x7F991F,
    0x1EDD048, 0x1EDD2A8, 0x1F18318, 0x1F945EC, 0x1F9D358, 0x1F9E489,
    0x1F9E4D5, 0x1F9E530, 0x1FA02F8, 0x1FA37CC, 0x1FA39D5,
    0x1F9DE57, 0x1F9DF34, 0x1F9E3FB, 0x1F9D8D9,
]
GENDER = {0x1F9DBD7, 0x1FA13F5}

fails = []
checked = 0
for off in TARGETS + list(GENDER):
    ptr_bytes = struct.pack('<I', off + BASE)
    # find ALL pointer locations in EN ROM (aligned tables AND script-embedded)
    locs = []
    i = EN.find(ptr_bytes)
    while i != -1:
        locs.append(i)
        i = EN.find(ptr_bytes, i + 1)
    if not locs:
        fails.append(f"0x{off:X}: no pointer in EN ROM")
        continue
    gender = off in GENDER
    # follow each pointer's FR value; accept the first that decodes to French text
    best = None
    for loc in locs:
        fr_target = struct.unpack('<I', FR[loc:loc + 4])[0]
        if not (BASE <= fr_target < BASE + len(FR)):
            continue
        raw = read_string(FR, fr_target - BASE)
        txt = decode(raw)
        problems = []
        if 'Noir' not in txt:
            problems.append('no Noir')
        # 'Black Ferrothorn' is the rival gang, intentionally left untranslated
        import re as _re
        residual = _re.sub(r'Black(\s|<0x[0-9A-Fa-f]{2}>)+Ferrothorns?', '', txt)
        if 'Black' in residual or 'Emboar' in residual:
            problems.append('residual Black/Emboar')
        if gender and (b'\xfd\x03' in raw or b'\xfd\x02' in raw):
            problems.append('GENDER BYTE FD02/FD03 present!')
        cand = (loc, fr_target, txt, raw, problems)
        if best is None or len(problems) < len(best[4]):
            best = cand
        if not problems:
            break
    if best is None:
        fails.append(f"0x{off:X}: FR pointer(s) out of range")
        continue
    loc, fr_target, txt, raw, problems = best
    checked += 1
    tag = 'GENDER ' if gender else ''
    status = 'OK' if not problems else 'FAIL:' + ','.join(problems)
    print(f"[{status}] {tag}0x{off:X} @ptr{loc:X}->{fr_target:08X}: {txt[:90]!r}")
    if problems:
        fails.append(f"0x{off:X}: {problems} :: {txt[:120]!r}")

print(f"\nChecked {checked} live strings.")
if fails:
    print(f"FAILURES ({len(fails)}):")
    for f in fails:
        print("  ", f)
    sys.exit(1)
print("ALL GREEN — every live gang string is French, no gender bytes.")
