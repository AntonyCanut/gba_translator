#!/bin/zsh
# Bisect the battle-start reset between build2 (good) and build4 (bad).
# State: /tmp/bisect_lo and /tmp/bisect_hi hold the candidate index range
# into /tmp/b24_regions.json. Patching rule: regions in [0, mid) get the
# GOOD (build2) content; the rest keep the BAD (build4) content. If the
# probe still resets, the culprit is in [mid, hi); otherwise in [lo, mid).
set -e
cd /Users/akc/Projects/Test/gba_translator
LO=0
HI=$(python3 -c "import json; print(len(json.load(open('/tmp/b24_regions.json'))))")
echo "bisecting $HI regions"
while [ $((HI - LO)) -gt 1 ]; do
  MID=$(( (LO + HI) / 2 ))
  python3 - "$LO" "$MID" <<'EOF'
import json, sys
lo, mid = int(sys.argv[1]), int(sys.argv[2])
good = open('/tmp/build2.gba','rb').read()
rom = bytearray(open('/tmp/final_keep.gba','rb').read())
regs = json.load(open('/tmp/b24_regions.json'))
# heal regions [lo, mid) with good content; outside stays bad
for a, b in regs[lo:mid]:
    rom[a:b] = good[a:b]
open('output/roms/GenedRom-fr.gba','wb').write(bytes(rom))
EOF
  OUT=$(npx tsx scripts/probe_drive.mts output/roms/GenedRom-fr.gba bsx "boot,load6,explorei360" 2>&1 | grep -E "explore@(359|364)\]" | tail -1)
  if echo "$OUT" | grep -q "map=0.0\|map=0.5"; then
    # still resets -> culprit NOT healed -> in [MID, HI)
    LO=$MID
    echo "round: healed [0..$MID) -> STILL RESETS; culprit in [$MID,$HI)"
  else
    HI=$MID
    echo "round: healed [0..$MID) -> fixed; culprit in [$LO,$MID)"
  fi
done
echo "CULPRIT REGION INDEX: $LO"
python3 -c "import json; r=json.load(open('/tmp/b24_regions.json')); print('region:', hex(r[$LO][0]), '-', hex(r[$LO][1]))"
