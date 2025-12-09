# Assisted translation guide (for contributors/automation)

- Quickstart
  - `make extract` — dump original text, split into 250-line chunks, copy into `fr_chunks/` if empty.
  - `make build-fr` — combine `fr_chunks/*` into `combined_fr.txt` then inject into `totranslate_fr.gba` using free-space relocation (falls back to append).
  - Use `.venv/bin/python3` if present; otherwise use system `python3`.
  - Sensitive offsets stay in place (low ROM areas); long strings are relocated to free space starting after `0x220000`.
  - Keep gibberish/binary lines untouched; check `fr_chunks/doutes.txt` before editing.

- Always compare against the matching file in `origin_chuncks/` (same filename as the chunk you edit).
- Never change offsets or line order in `fr_chunks/*`; each chunk must have exactly 250 lines (except the final chunk if shorter).
- Keep any non-English or special characters (e.g., kana such as ね) exactly as they appear in the origin and in the same positions.
- Preserve control codes (`\n`, `\p`, `\l`, `{...}`) from the origin. Keep the same order and count whenever possible, and rephrase so the visible text (ignoring `{COLOR}`/placeholders) between two codes stays ≤ 36 characters. If a line in the origin has no break and cannot fit after rephrasing, add the minimum `\n` needed—never stack breaks back to back.
- Do not trim whitespace unless the resulting length is identical.
- Terminology: “move” → “capacité”, TM → “CT”, Gym → “Arène”, Gym Leader → “Champion d’Arène”.
- Translate city and Pokémon names to their official French forms.
- Translate move names to the official French in-game names (e.g., Thunderbolt → Tonnerre).
- Leave unreadable/binary strings and already-correct lines unchanged.
- Keep `\p` and `\l` at the same positions when possible.
- Before working, review/update `fr_chunks/doutes.txt` for any unresolved doubts.
- Each chunk file must contain exactly 250 lines (except the very last chunk if shorter).
- Le nom des lieux est référencé dans le document `place_names_map.txt` sur lequel il faut se référer pour la traduction.

## Critical Rules for "Dangerous" Lines (Overflows without Pointers)
Some text lines in the ROM do not have explicit pointers and are part of contiguous blocks. These lines are extremely sensitive to length changes.
1.  **Strict Length Limit**: If a line does not have a pointer (check with `scripts/check_overflows_specific.py`), the translated text MUST NOT exceed the length of the original English text (including the terminator). But it's Okay for Pokemon names, or city name.
2.  **No Relocation**: These lines cannot be relocated to free space. If they overflow, the game will crash because it will continue reading from the old address.
3.  **Verification**: Always run `scripts/check_overflows_specific.py` after translating to identify any dangerous overflows. If found, shorten the translation to fit the original length.