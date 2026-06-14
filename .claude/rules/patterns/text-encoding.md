# Encodage de texte GBA (Gen III / CFRU)

Le projet manipule l'encodage texte **propriétaire Gen III** de Pokémon FireRed/Unbound,
pas de l'ASCII. La source de vérité est `src/core/text_codec.py`.

## Tables & constantes (extraites du code réel)

```python
GBA_ROM_BASE      = 0x08000000   # base des pointeurs 32-bit
POKEMON_TERMINATOR = 0xFF        # fin de chaîne
POKEMON_NEWLINE    = 0xFE        # saut de ligne
ASCII_TERMINATOR   = 0x00
POKEMON_TABLE: Dict[str, int]    # caractère -> codepoint (ex. ' ':0x00, '0':0xA1, 'À':0x01, 'Ç':0x04)
ASCII_TABLE,  SPANISH_ALIASES, ENCODE_ALIASES
CONTROL_CODE_ENCODE / CONTROL_CODE_DECODE
```

## Règles d'or

- **Terminateur** : `0xFF` clôt toute chaîne ; `0xFE` est un saut de ligne interne.
- **Control codes multi-octets** : `FC`, `FD`, `F8`, `F9`, `F7` sont suivis d'octets
  d'argument (2–3 octets au total). Ne jamais les décoder caractère par caractère ;
  passer par `CONTROL_CODE_DECODE`.
- **Pointeurs** : 32-bit little-endian, valeur ROM = `offset + 0x08000000`. Valider
  qu'un pointeur retombe dans la ROM avant de l'écrire.
- **Caractères accentués FR/ES** : mappés sur les codepoints Gen III via `POKEMON_TABLE`
  (`é è ê ë à â ç ù û ü î ï ô œ` …). Vérifie qu'un glyphe existe dans la police cible
  avant de l'injecter (certaines polices, ex. l'intro, n'ont pas `ê/ç/ù`).
- **Longueur** : compter en **octets encodés**, pas en caractères (un control code ≠ 1
  octet). Utiliser `get_encoded_length()`.

## Synchronisation Python ↔ TypeScript

La charmap est dupliquée côté émulateur web (TypeScript). Après toute modification de
`text_codec.py`, lance `make sync-charmap` et vérifie avec `make sync-charmap-check`
(la CI a un job `charmap-sync` qui échoue si les deux divergent).

## Pièges connus (pipeline de tokens)

- Remplacement **positionnel** des placeholders : conserver l'ordre des tokens bruts,
  ne pas réordonner (`{fille}`, `{LV}` = `0x34`, `{COLOR}X` → `FC 01 NN`).
- `FA`/`FB` sont hors file de tokens.
- Toujours vérifier que l'anglais « vivant » est bien atteint par pointeur avant de
  conclure qu'une chaîne est traduite.
