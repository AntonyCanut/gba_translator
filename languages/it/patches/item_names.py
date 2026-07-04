#!/usr/bin/env python3
"""Translate untranslated item NAME cells (Berries + general items) in the IT ROM.

Item names live as fixed-width cells inside the CFRU item table (``gItems``)
at 0x876074, stride 44: ``name[14]`` followed by the item data (id, price,
hold-effect, description pointer at +0x14…). These *inline* name cells are
**copied byte-for-byte from the source ROM** by the build pipeline — no
translation pass touches them (they are absent from translation_ready.json,
combined_fr.txt and the Spanish extraction). The Unbound source already ships
translated names for the medicine/general items *and* for the long names
stored as a ROM pointer (union: name[14] starting with an 0x08 MSB pointer →
"Bright Powder" → its translated form etc. are pipeline-translated). What
stayed English are the short *inline* cells: every Berry ("Aspear Berry" →
"Baccaperina"), plus a large set of general items — evolution stones,
valuables, held/battle items, type Gems, Silvally ROMs, Genesect Drives,
incenses, mails, fishing rods, fossils, HMs…

This script rewrites those inline cells in place, byte-exact, with their
official Italian (Italy) names. It is data-driven: each cell whose current
name exactly matches a source-string key in ALL_NAMES is rewritten with the
Italian value. That source string is English for almost every item, but the
standard Poké Ball line (Poké/Great/Ultra/Master/Safari/Net/Dive/Nest/Repeat/
Timer/Luxury/Premier/Dusk/Heal/Quick/Cherish Ball) is a special case: the
Unbound base ROM ships those inline cells PRE-LOCALISED TO FRENCH, so their
keys are the French source strings ("Hyper Ball", "Super Ball", …) mapped to
the Italian name (see the "Standard Poké Ball line" block in ITEM_NAMES).
Cells that already hold the Italian name are skipped (idempotent), pointer
cells never match a key, and item data after the 14-byte name field is never
touched.

Italian names are the official localised names, sourced from the PokéAPI
item-name data (which mirrors the in-game text dumps) and cross-checked
against Bulbapedia's "In other languages" tables for a sample of entries;
only names that fit the 13-glyph cell are included here. Unlike Berry names
in French/German (which follow a "translate the flavour root" pattern),
official Italian Berry names use a "Bacca" + blended-root pattern
("Cheri Berry" → "Baccaliegia", not "Bacca Cheri") — every entry below is the
real localised name, not a guessed "Bacca X" prefix.

Names whose official IT form exceeds 13 glyphs (e.g. "Exp. Share" →
"Condividi esp." at 14, "Soft Sand" → "Sabbia Soffice" at 14, "Room Service"
→ "Distorservizio" at 14, "Bug Gem"/"Bug Memory" → "Bijoucoleottero"/"ROM
Coleottero" — the Italian Bug-type name "Coleottero" runs long, "Bottle Cap"
→ "Tappo d'argento" at 15, "Eon Ticket" → "Biglietto Eone" at 14) are
intentionally excluded rather than guessed at with an invented abbreviation;
they are left as the source ships them. Two entries are Unbound-custom
in-house items with no official Nintendo localisation ("Muscle " → the
FR/DE scripts' own coinage pattern is mirrored here as "Muscolo+"; "Costume
Box" → "Guardaroba", "wardrobe").

Usage:
    python3 languages/it/patches/item_names.py --rom output/roms/GenedRom-it.gba
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from src.text.charmap_data import BYTE_TO_CHAR, CHAR_TO_BYTE
from src.core.text_codec import TextEncoder

# CFRU item table (gItems). Each entry is 44 bytes: name[14] then item data
# (id u16 at +14, price u16 at +16, …, description pointer at +0x14). Only the
# 14-byte name field is ever rewritten here.
ITEM_TABLE_BASE = 0x876074
ITEM_STRIDE = 44
NAME_FIELD = 14  # bytes available for the name (13 glyphs max + 0xFF terminator)
# Generous upper bound on the number of item entries to scan. The exact-name
# match guard below makes over-scanning harmless (no random cell equals a Berry
# name), so we simply cover the whole table.
SCAN_COUNT = 1100

# English item name -> official Italian (Italy) name.
# Every Berry name below is the real localised in-game name (verified via
# PokéAPI item-name data, cross-checked against Bulbapedia for a sample).
# NOTE: CFRU spells the Gen VI berry "Maranga Berry" as "Marang Berry"; the key
# below matches the in-ROM English string.
BERRY_NAMES = {
    'Cheri Berry': 'Baccaliegia',
    'Chesto Berry': 'Baccastagna',
    'Pecha Berry': 'Baccapesca',
    'Rawst Berry': 'Baccafrago',
    'Aspear Berry': 'Baccaperina',
    'Leppa Berry': 'Baccamela',
    'Oran Berry': 'Baccarancia',
    'Persim Berry': 'Baccaki',
    'Lum Berry': 'Baccaprugna',
    'Sitrus Berry': 'Baccacedro',
    'Figy Berry': 'Baccafico',
    'Wiki Berry': 'Baccakiwi',
    'Mago Berry': 'Baccamango',
    'Aguav Berry': 'Baccaguava',
    'Iapapa Berry': 'Baccapaia',
    'Razz Berry': 'Baccalampon',
    'Bluk Berry': 'Baccamora',
    'Nanab Berry': 'Baccabana',
    'Wepear Berry': 'Baccapera',
    'Pinap Berry': 'Baccananas',
    'Pomeg Berry': 'Baccagrana',
    'Kelpsy Berry': 'Baccalga',
    'Qualot Berry': 'Baccaloquat',
    'Hondew Berry': 'Baccamelon',
    'Grepa Berry': 'Baccauva',
    'Tamato Berry': 'Baccamodoro',
    'Cornn Berry': 'Baccavena',
    'Magost Berry': 'Baccagostan',
    'Rabuta Berry': 'Baccambutan',
    'Nomel Berry': 'Baccalemon',
    'Spelon Berry': 'Baccamelos',
    'Pamtre Berry': 'Baccapalma',
    'Watmel Berry': 'Baccacomero',
    'Durin Berry': 'Baccadurian',
    'Belue Berry': 'Baccartillo',
    'Occa Berry': 'Baccacao',
    'Passho Berry': 'Baccapasflo',
    'Wacan Berry': 'Baccaparmen',
    'Rindo Berry': 'Baccarindo',
    'Yache Berry': 'Baccamoya',
    'Chople Berry': 'Baccarosmel',
    'Kebia Berry': 'Baccakebia',
    'Shuca Berry': 'Baccanaca',
    'Coba Berry': 'Baccababa',
    'Payapa Berry': 'Baccapayapa',
    'Tanga Berry': 'Baccaitan',
    'Charti Berry': 'Baccaciofo',
    'Kasib Berry': 'Baccacitrus',
    'Haban Berry': 'Baccahaban',
    'Colbur Berry': 'Baccaxan',
    'Babiri Berry': 'Baccababiri',
    'Chilan Berry': 'Baccacinlan',
    'Liechi Berry': 'Baccalici',
    'Ganlon Berry': 'Baccalongan',
    'Salac Berry': 'Baccasalak',
    'Petaya Berry': 'Baccapitaya',
    'Apicot Berry': 'Baccacocca',
    'Lansat Berry': 'Baccalangsa',
    'Starf Berry': 'Baccambola',
    'Enigma Berry': 'Baccaenigma',
    'Micle Berry': 'Baccaracolo',
    'Custap Berry': 'Baccacrela',
    'Jaboca Berry': 'Baccajaba',
    'Rowap Berry': 'Baccaroam',
    'Kee Berry': 'Baccalighia',
    'Marang Berry': 'Baccapane',
    'Roseli Berry': 'Baccarcadè',
}

# English item name -> official Italian (Italy) name, for the non-Berry
# inline cells. Every value verified to fit the 13-glyph name cell (the apply
# pass re-validates fit before writing). Names whose official IT form is
# longer than 13 glyphs are intentionally excluded (see module docstring).
ITEM_NAMES = {
    # Evolution & special stones
    'Sun Stone': 'Pietrasolare',
    'Moon Stone': 'Pietralunare',
    'Fire Stone': 'Pietrafocaia',
    'Thunderstone': 'Pietratuono',
    'Water Stone': 'Pietraidrica',
    'Leaf Stone': 'Pietrafoglia',
    'Dusk Stone': 'Neropietra',
    'Dawn Stone': 'Pietralbore',
    'Shiny Stone': 'Pietrabrillo',
    'Oval Stone': 'Pietraovale',
    'Ice Stone': 'Pietragelo',
    'Everstone': 'Pietrastante',
    # Valuables
    'Pearl': 'Perla',
    'Big Pearl': 'Grande Perla',
    'Stardust': 'Polvostella',
    'Nugget': 'Pepita',
    'Big Nugget': 'Granpepita',
    'Heart Scale': 'Squama Cuore',
    'Rare Bone': 'Osso Raro',
    'TinyMushroom': 'Minifungo',
    'Big Mushroom': 'Grande Fungo',
    'Prism Scale': 'Squama Bella',
    'Dragon Scale': 'Squama Drago',
    'Relic Copper': 'Soldantico',
    'Relic Silver': 'Ducatantico',
    'Relic Gold': 'Doblonantico',
    'Relic Vase': 'Vasantico',
    'Relic Band': 'Bracciantico',
    'Relic Statue': 'Statuantica',
    # Evolution-trigger held items
    'Protector': 'Copertura',
    'Magmarizer': 'Magmatore',
    'Electirizer': 'Elettritore',
    'Razor Claw': 'Affilartigli',
    'Razor Fang': 'Affilodente',
    'Reaper Cloth': 'Terrorpanno',
    'Up-Grade': 'Upgrade',
    'Metal Coat': 'Metalcoperta',
    "King's Rock": 'Roccia di Re',
    'Dragon Fang': 'Dentedidrago',
    'Whip Dream': 'Dolcespuma',
    # General held / battle items
    'Choice Band': 'Bendascelta',
    'White Herb': 'Erbachiara',
    'Macho Brace': 'Crescicappa',
    # "Exp. Share" -> "Condividi esp." (14 glyphs) excluded — does not fit.
    'Quick Claw': 'Rapidartigli',
    'Soothe Bell': 'Calmanella',
    'Mental Herb': 'Mentalerba',
    'Amulet Coin': 'Monetamuleto',
    'Cleanse Tag': 'Velopuro',
    'Smoke Ball': 'Palla Fumo',
    'Focus Band': 'Bandana',
    'Scope Lens': 'Mirino',
    # "Soft Sand" -> "Sabbia Soffice" (14 glyphs) excluded — does not fit.
    'Miracle Seed': 'Miracolseme',
    'Black Belt': 'Cinturanera',
    'Magnet': 'Calamita',
    'Mystic Water': 'Acqua Magica',
    'Sharp Beak': 'Beccaffilato',
    'Poison Barb': 'Velenaculeo',
    'Spell Tag': 'Spettrotarga',
    'Charcoal': 'Carbonella',
    'Silk Scarf': 'Sciarpa Seta',
    'Shell Bell': 'Conchinella',
    'Sea Incense': 'Marearoma',
    'Lax Incense': 'Distraroma',
    'Lucky Punch': 'Fortunpugno',
    'Metal Powder': 'Metalpolvere',
    'Thick Club': 'Ossospesso',
    'Leek': 'Gambo',
    'Rocky Helmet': 'Bitorzolelmo',
    'Wide Lens': 'Grandelente',
    'Zoom Lens': 'Zoomlente',
    'Destiny Knot': 'Destincomune',
    'Smooth Rock': 'Roccialiscia',
    'Damp Rock': 'Rocciaumida',
    'Heat Rock': 'Rocciacalda',
    'Icy Rock': 'Rocciafredda',
    'Big Root': 'Granradice',
    'Light Clay': 'Creta Luce',
    'Big Malasada': 'Malasada maxi',
    'Iron Ball': 'Ferropalla',
    'Lagging Tail': 'Rallentocoda',
    'Sticky Barb': 'Vischiopunta',
    'Muscle Band': 'Muscolbanda',
    'Expert Belt': 'Abilcintura',
    'Power Herb': 'Vigorerba',
    'Float Stone': 'Pietralieve',
    'Grip Claw': 'Presartigli',
    'Eviolite': 'Evolcondensa',
    'Red Card': 'Cartelrosso',
    'Eject Button': 'Pulsantefuga',
    'Air Balloon': 'Palloncino',
    'Absorb Bulb': 'Bulbo',
    'Cell Battery': 'Ricaripila',
    'Snowball': 'Palla di neve',
    'Metronome': 'Plessimetro',
    'Quick Powder': 'Velopolvere',
    'Shed Shell': 'Disfoguscio',
    'Binding Band': 'Legafascia',
    'Ring Target': 'Facilsaglio',
    'Adrenal Orb': 'Fifasfera',
    'Throat Spray': 'Spray gola',
    'Eject Pack': 'Zainofuga',
    # "Room Service" -> "Distorservizio" (14 glyphs) excluded — does not fit.
    # Type Gems (Gemma X)
    'Normal Gem': 'Bijounormale',
    'Fighting Gem': 'Bijoulotta',
    'Flying Gem': 'Bijouvolante',
    'Poison Gem': 'Bijouveleno',
    'Ground Gem': 'Bijouterra',
    'Rock Gem': 'Bijouroccia',
    # "Bug Gem" -> "Bijoucoleottero" (15 glyphs) excluded — Italian Bug-type
    # name "Coleottero" runs long; does not fit.
    'Ghost Gem': 'Bijouspettro',
    'Steel Gem': 'Bijouacciaio',
    'Fire Gem': 'Bijoufuoco',
    'Water Gem': 'Bijouacqua',
    'Grass Gem': 'Bijouerba',
    'Psychic Gem': 'Bijoupsico',
    'Ice Gem': 'Bijoughiaccio',
    'Dragon Gem': 'Bijoudrago',
    'Fairy Gem': 'Bijoufolletto',
    # Silvally type ROMs (Memory)
    'Fist Memory': 'ROM Lotta',
    'Sky Memory': 'ROM Volante',
    'Toxic Memory': 'ROM Veleno',
    'Earth Memory': 'ROM Terra',
    'Rock Memory': 'ROM Roccia',
    # "Bug Memory" -> "ROM Coleottero" (14 glyphs) excluded — same long
    # Bug-type name as "Bug Gem" above; does not fit.
    'Ghost Memory': 'ROM Spettro',
    'Steel Memory': 'ROM Acciaio',
    'Fire Memory': 'ROM Fuoco',
    'Water Memory': 'ROM Acqua',
    'Grass Memory': 'ROM Erba',
    'Zap Memory': 'ROM Elettro',
    'Psych Memory': 'ROM Psico',
    'Ice Memory': 'ROM Ghiaccio',
    'Draco Memory': 'ROM Drago',
    'Dark Memory': 'ROM Buio',
    'Fairy Memory': 'ROM Folletto',
    # Genesect Drives
    'Burn Drive': 'Piromodulo',
    'Douse Drive': 'Idromodulo',
    'Shock Drive': 'Voltmodulo',
    'Chill Drive': 'Gelomodulo',
    # Incenses
    'Luck Incense': 'Fortunaroma',
    'Full Incense': 'Gonfioaroma',
    'Pure Incense': 'Puroaroma',
    'Rock Incense': 'Roccioaroma',
    'Rose Incense': 'Rosaroma',
    'Wave Incense': 'Ondaroma',
    # Misc
    # "Bottle Cap" -> "Tappo d'argento" (15 glyphs) excluded — does not fit.
    # "Costume Box" is an Unbound-custom wardrobe menu item, not an official
    # Nintendo item (no PokéAPI/Bulbapedia entry); translated directly like
    # the FR/DE scripts' own coinages ("Boîte Costume" / "Kostümbox").
    'Costume Box': 'Guardaroba',
    # Mails (Messaggio X)
    'Orange Mail': 'Mess. Agrume',
    'Harbor Mail': 'Mess. Porto',
    'Wood Mail': 'Mess. Bosco',
    'Wave Mail': 'Mess. Onda',
    'Bead Mail': 'Mess. Perle',
    'Shadow Mail': 'Mess. Ombra',
    'Tropic Mail': 'Mess. Tropic',
    'Dream Mail': 'Mess. Sogno',
    'Retro Mail': 'Mess. Rétro',
    'Mech Mail': 'Mess. Tecno',
    # Fishing rods
    'Old Rod': 'Amo Vecchio',
    'Good Rod': 'Amo Buono',
    'Super Rod': 'Super Amo',
    # Key / misc items
    'Coin Case': 'Salvadanaio',
    'Meteorite': 'Meteorite',
    'Member Card': 'Scheda Soci',
    'Lunar Wing': 'Alalunare',
    'VS Seeker': 'Cercasfide',
    'Powder Jar': 'Portafarina',
    'Devon Scope': 'Devonscopio',
    'Mach Bike': 'Bici da corsa',
    'Letter': 'Lettera',
    # "Eon Ticket" -> "Biglietto Eone" (14 glyphs) excluded — does not fit.
    # Feather vitamins (Wings)
    'Health Wing': 'Piumsalute',
    'Muscle Wing': 'Piumpotenza',
    'Resist Wing': 'Piumtutela',
    'Genius Wing': 'Piumingegno',
    'Clever Wing': 'Piumintuito',
    'Swift Wing': 'Piumreazione',
    'Pretty Wing': 'Piumabella',
    'Silver Wing': 'Aladargento',
    'Rainbow Wing': "Ala d'Iride",
    # Nectars
    'Red Nectar': 'Nettare rosso',
    'Pink Nectar': 'Nettare rosa',
    'Purp Nectar': 'Nettare viola',
    # Apricorn / special Poké Balls
    'Fast Ball': 'Rapid Ball',
    'Level Ball': 'Level Ball',
    'Lure Ball': 'Esca Ball',
    'Heavy Ball': 'Peso Ball',
    'Friend Ball': 'Friend Ball',
    'Moon Ball': 'Luna Ball',
    'Sport Ball': 'Gara Ball',
    'Beast Ball': 'UC Ball',
    'Dream Ball': 'Dream Ball',
    # Standard Poké Ball line. Unlike every entry above (English in the Unbound
    # source, keyed on their English name), the base ROM ships these inline
    # cells PRE-LOCALISED TO FRENCH — so the key is the *French* source string
    # and the value is the official Italian (Italy) name. Confirmed in a built
    # GenedRom-it.gba: gItems cells 10-21/61-71 (base 0x876074) decode as
    # "Hyper Ball"/"Super Ball"/"Filet Ball"/… (French), never English. The FR
    # build needs no entry here (the source strings already ARE the correct
    # French names); IT/DE remap them. Every value fits the 13-glyph cell.
    'Hyper Ball': 'Ultra Ball',     # Ultra Ball  (FR source "Hyper Ball")
    'Super Ball': 'Mega Ball',      # Great Ball  (FR source "Super Ball")
    'Master Ball': 'Master Ball',   # Master Ball (identical FR/IT)
    'Poké Ball': 'Poké Ball',       # Poké Ball   (identical FR/IT)
    'Safari Ball': 'Safari Ball',   # Safari Ball (identical FR/IT)
    'Filet Ball': 'Rete Ball',      # Net Ball    (FR source "Filet Ball")
    'Scuba Ball': 'Sub Ball',       # Dive Ball   (FR source "Scuba Ball")
    'Faiblo Ball': 'Minor Ball',    # Nest Ball   (FR source "Faiblo Ball")
    'Bis Ball': 'Bis Ball',         # Repeat Ball (identical FR/IT)
    'Chrono Ball': 'Timer Ball',    # Timer Ball  (FR source "Chrono Ball")
    'Luxe Ball': 'Chic Ball',       # Luxury Ball (FR source "Luxe Ball")
    'Honor Ball': 'Premier Ball',   # Premier Ball(FR source "Honor Ball")
    'Mémoire Ball': 'Pregio Ball',  # Cherish Ball(FR source "Mémoire Ball")
    'Sombre Ball': 'Scuro Ball',    # Dusk Ball   (FR source "Sombre Ball")
    'Soin Ball': 'Cura Ball',       # Heal Ball   (FR source "Soin Ball")
    'Rapide Ball': 'Velox Ball',    # Quick Ball  (FR source "Rapide Ball")
    # Flutes
    'Sun Flute': 'Flauto solare',
    'Moon Flute': 'Flauto lunare',
    # Charms
    'Oval Charm': 'Ovamuleto',
    'Shiny Charm': 'Cromamuleto',
    # Fossils
    'Helix Fossil': 'Helixfossile',
    'Dome Fossil': 'Domofossile',
    'Skull Fossil': 'Fossilcranio',
    'Plume Fossil': 'Fossilpiuma',
    'Sail Fossil': 'Fossilpinna',
    'Old Amber': 'Ambra antica',
    # Hidden Machines: HM -> MN (Mossa Nascosta) in IT
    'HM01': 'MN01',
    'HM02': 'MN02',
    'HM03': 'MN03',
    'HM04': 'MN04',
    'HM05': 'MN05',
    'HM06': 'MN06',
    'HM07': 'MN07',
    'HM08': 'MN08',
    # Unbound custom battle items — trailing-space variant in source ROM
    'Muscle ': 'Muscolo+',
}

# Every inline item-name cell we translate, keyed by the in-ROM English string.
ALL_NAMES = {**BERRY_NAMES, **ITEM_NAMES}


def encode(name: str) -> bytes:
    try:
        return bytes(CHAR_TO_BYTE[c] for c in name)
    except KeyError as exc:  # pragma: no cover - guards against bad data edits
        raise ValueError(f"character {exc.args[0]!r} not in CFRU charmap") from exc


def decode_name(data, offset: int) -> str:
    """Decode the name held in the 14-byte name field (up to the 0xFF)."""
    out = []
    for i in range(NAME_FIELD):
        b = data[offset + i]
        if b == 0xFF:
            break
        out.append(BYTE_TO_CHAR.get(b, "�"))
    return "".join(out)


def apply_item_name_fixes(data: bytearray, names: dict) -> int:
    """Rewrite item name cells whose English name is a key in ``names``.

    Returns the number of cells patched. The English string must fit and the
    Italian replacement must fit the 14-byte name field; item data after the
    name field is never touched. Idempotent: cells already holding the
    Italian name are skipped.
    """
    # Pre-validate every Italian replacement fits before writing anything.
    for it in names.values():
        if len(encode(it)) + 1 > NAME_FIELD:
            raise ValueError(f"{it!r} does not fit a {NAME_FIELD}-byte name cell")

    it_by_en = names
    patched = 0
    for i in range(SCAN_COUNT):
        offset = ITEM_TABLE_BASE + i * ITEM_STRIDE
        if offset + NAME_FIELD > len(data):
            break
        current = decode_name(data, offset)
        it = it_by_en.get(current)
        if it is None:
            continue  # not a cell we translate (or already Italian → no match)
        new_bytes = encode(it)
        old_bytes = encode(current)
        # Sanity: the cell must really hold the English name + terminator.
        if (
            bytes(data[offset : offset + len(old_bytes)]) != old_bytes
            or data[offset + len(old_bytes)] != 0xFF
        ):
            continue
        # Write Italian name + terminator, then clear the rest of the span the
        # old name occupied so no stale glyphs trail past the terminator. Stays
        # entirely within the 14-byte name field.
        cleared = max(len(old_bytes), len(new_bytes)) + 1
        data[offset : offset + cleared] = (
            new_bytes + b"\xff" + bytes(cleared - len(new_bytes) - 1)
        )
        patched += 1
    return patched


# ROM offset → corrected Italian description (kept empty: no genuinely
# overflowing Italian item description has been identified yet). The function
# below is kept for structural parity with the FR script so a future overflow
# fix can be added the same way, without touching apply_item_name_fixes.
ITEM_DESC_OVERRIDES: dict[int, str] = {}

ROM_POINTER_BASE = 0x08000000
DESC_PTR_OFFSET = 0x14  # within each 44-byte item entry


def apply_item_desc_fixes(data: bytearray) -> int:
    """Overwrite specific item description strings in-place.

    Each key in ITEM_DESC_OVERRIDES is a raw ROM offset where the description
    bytes live. The new text must be shorter than (or equal to) the original
    so it always fits without relocation. The encoder appends 0xFF automatically.
    Returns the number of overrides applied.
    """
    patched = 0
    for rom_offset, italian_text in ITEM_DESC_OVERRIDES.items():
        encoded = TextEncoder.encode_pokemon(italian_text)
        if rom_offset + len(encoded) > len(data):
            print(f"  WARN: desc override at 0x{rom_offset:X} out of ROM range — skipped")
            continue
        # Measure current length to ensure we don't expand the slot
        end = data.find(b"\xff", rom_offset)
        if end < 0 or len(encoded) > (end - rom_offset + 1):
            print(f"  WARN: desc override at 0x{rom_offset:X} would expand slot — skipped")
            continue
        data[rom_offset:rom_offset + len(encoded)] = encoded
        patched += 1
    return patched


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, default=Path("output/roms/GenedRom-it.gba"))
    args = parser.parse_args()

    data = bytearray(args.rom.read_bytes())
    patched = apply_item_name_fixes(data, ALL_NAMES)
    desc_patched = apply_item_desc_fixes(data)
    if patched or desc_patched:
        args.rom.write_bytes(data)
    print(f"Item name cells translated: {patched} (of {len(ALL_NAMES)} known)")
    if desc_patched:
        print(f"Item description overrides applied: {desc_patched}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
