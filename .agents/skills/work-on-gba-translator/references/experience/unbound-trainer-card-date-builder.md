---
name: unbound-trainer-card-date-builder
description: "Trainer Card \"Début de l'aventure\" date = inline ASM builder at 0x1ED8D76 (Month Day, Year), no text template"
metadata:
  node_type: memory
  type: project
  originSessionId: 4c6ba974-b547-4c70-976e-262a69db9d05
---

Trainer Card front shows **"Début de l'aventure : Janv.19, 2026"** = Month·Day, Year (US order), NOT French D/M/Y. Confirmed on emulator (START menu → RIGHT×3 = player-name/card icon → A). Labels Nom/Portefeuille/Temps/Début de l'aventure ARE translated (the English 0x1F81E44 table is a red herring, unused). No FDnn date template exists — the date is built inline in ASM.

**Builder: file 0x1ED8D76–0x1ED8DA2** (function pool 0x1ED8E8C). Reads month index from `[sp,#0x14]`, month-name pointer table at **0x081FE6BF8** (base, `table[idx*4]`, 12 entries → cells 0x1F81E9E stride 6; July relocated 0x8E69712). Day→buffer 0x02021CD0 (2-digit), Year→0x02021CF0 (4-digit) via ConvertIntToDecimalStringN (0x08008E78). Assembly = `StringCopy(0x02021D18,month); StringAppend(day); StringAppend(", "); StringAppend(year)` → "Janv.19, 2026". StringCopy=0x08008D84, StringAppend=0x08008DA4. Calls go via bx-veneers at 0x9ED920C (bx r3) … 0x9ED9214 (bx r7).

In-place reorder is BLOCKED by register pressure (r4=0,r5=year,r6=day,r7=dest all pinned; StringCopy/Append clobber r0-r3; no free callee-saved reg to spill month ptr). Fix = free-space trampoline builder that emits "DD Mon YYYY" + redirect the block. See [[unbound-datetime-code-patches]] (patch_time_format_fr.py handles save-screen/clock, NOT the card). mGBA bridge (emulator-web MgbaBridgeClient, npx tsx) works for savestate load + screenshot; ss2 is an overworld state.
