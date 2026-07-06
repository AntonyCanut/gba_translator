"""Locate the LZ77-compressed 'SELECT Move' hint graphic in the ROM.
Strategy: the menu code (0xa0b000-0xa0c400) references graphics via pointers to
LZ77 blocks (header byte 0x10). Decompress each candidate and check whether the
decompressed tiles contain the VRAM 'Move' tile bitmaps (tiles 0x0c..0x0e)."""
import struct

en = open('input/roms/englishrom.gba', 'rb').read()
vram = open('output/proofs/startmenu-vram/vram-bg.bin', 'rb').read()
char_base = 2 * 0x4000
# target tile bitmaps loaded in VRAM (the hint bar static tiles)
targets = {t: vram[char_base + t*32: char_base + t*32 + 32] for t in range(8, 15)}


def lz77_decompress(data, off):
    if data[off] != 0x10:
        return None
    size = data[off+1] | (data[off+2] << 8) | (data[off+3] << 16)
    out = bytearray()
    p = off + 4
    try:
        while len(out) < size:
            flags = data[p]; p += 1
            for b in range(8):
                if len(out) >= size:
                    break
                if flags & (0x80 >> b):
                    info = (data[p] << 8) | data[p+1]; p += 2
                    length = (info >> 12) + 3
                    disp = (info & 0xfff) + 1
                    for _ in range(length):
                        out.append(out[len(out)-disp])
                else:
                    out.append(data[p]); p += 1
    except IndexError:
        return None
    return bytes(out), p


def collect_ptrs(lo, hi):
    ptrs = []
    for a in range(lo, hi, 4):
        v = struct.unpack('<I', en[a:a+4])[0]
        if 0x08000000 <= v < 0x0a000000:
            o = v - 0x08000000
            if o < len(en) and en[o] == 0x10:
                ptrs.append((a, o))
    return ptrs


cands = collect_ptrs(0xa0b000, 0xa0c400)
print(f'LZ77 pointer candidates in menu code: {[(hex(a),hex(o)) for a,o in cands]}')

# Also brute over a wider code window and the graphics banks
for lo, hi, tag in [(0xa08000, 0xa10000, 'menu-wide')]:
    for a in range(lo, hi, 4):
        v = struct.unpack('<I', en[a:a+4])[0]
        if 0x08000000 <= v < 0x0a000000:
            o = v - 0x08000000
            if o < len(en)-4 and en[o] == 0x10:
                cands.append((a, o))

seen = set()
for a, o in cands:
    if o in seen:
        continue
    seen.add(o)
    res = lz77_decompress(en, o)
    if not res:
        continue
    dec, end = res
    # check if any target tile bitmap is present
    for t, raw in targets.items():
        if raw != b'\x00'*32 and raw in dec:
            idx = dec.index(raw)
            print(f'MATCH tile 0x{t:02x} in LZ77@0x{o:x} (ptr@0x{a:x}) declen={len(dec)} at dec-off {idx} (tile {idx//32})')
