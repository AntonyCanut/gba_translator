# Assisted translation guide (for contributors/automation)

- Quickstart
  - `make extract` — dump original text, split into 250-line chunks, copy into `fr_chunks/` if empty.
  - `make build-fr` — combine `fr_chunks/*` into `combined_fr.txt` then inject into `totranslate_fr.gba` using free-space relocation (falls back to append).
  - Use `.venv/bin/python3` if present; otherwise use system `python3`.
  - Sensitive offsets stay in place (low ROM areas); long strings are relocated to free space starting after `0x220000`.
  - Keep gibberish/binary lines untouched; check `fr_chunks/doutes.txt` before editing.

- Never change offsets or line order in `fr_chunks/*`.
- Preserve control codes (`\n`, `\p`, `\l`, `{...}`) and wrap at 36 characters max per displayed segment.
- Do not trim whitespace unless the resulting length is identical.
- Terminology: “move” → “capacité”, TM → “CT”, Gym → “Arène”, Gym Leader → “Champion d’Arène”.
- Translate city and Pokémon names to their official French forms.
- Translate move names to the official French in-game names (e.g., Thunderbolt → Tonnerre).
- Leave unreadable/binary strings and already-correct lines unchanged.
- Keep `\p` and `\l` at the same positions when possible.
- Before working, review/update `fr_chunks/doutes.txt` for any unresolved doubts.
- Each chunk file must contain exactly 250 lines (except the very last chunk if shorter).
