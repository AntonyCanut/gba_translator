#!/usr/bin/env python3
"""Translate untranslated item NAME cells (Berries + general items) in the DE ROM.

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
"Wilbirbeere"), plus a large set of general items — evolution stones,
valuables, held/battle items, type Gems, Silvally ROMs, Genesect Drives,
incenses, mails, fishing rods, fossils, HMs…

This script rewrites those inline cells in place, byte-exact, with their
official German (Germany) names. It is data-driven: each cell whose current
name exactly matches an English key in ALL_NAMES is rewritten with the German
value. Cells that already hold the German name are skipped (idempotent),
pointer cells never match an English key, and item data after the 14-byte
name field is never touched.

German names are the official localised names (verified against Bulbapedia
"In other languages" tables / Pokéwiki); only names that fit the 13-glyph
cell are included here. Names whose official DE form exceeds 13 glyphs
(most Mega Stones, type Plates, "Bizarroservice", "Silberkronkorken",
"Purpurner Nektar", most Poké Ball-related long compounds, custom Unbound
Mega-key items) require a pointer relocation — out of scope for this
byte-exact in-place patch — and are left as the source ships them. German
compounds are frequently *longer* than their English/French counterparts, so
this exclusion list is meaningfully larger than the French script's.

Usage:
    python3 scripts/patch_item_names_de.py --rom output/roms/GenedRom-de.gba
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.text.charmap_data import BYTE_TO_CHAR, CHAR_TO_BYTE

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

# English item name -> official German (Germany) name.
# Berry names verified individually against Bulbapedia "In other languages"
# tables (canonical localised names used by the official DE games). German
# Berry names do NOT follow a simple "translate the English root" pattern —
# the flavor/berry mapping was substantially reshuffled at localisation time
# (e.g. "Cheri Berry" -> "Amrenabeere", not a Cheri-rooted word) — every entry
# below was looked up individually, not derived from a pattern.
# NOTE: CFRU spells the Gen VI berry "Maranga Berry" as "Marang Berry"; the key
# below matches the in-ROM English string.
BERRY_NAMES = {
    "Cheri Berry": "Amrenabeere",
    "Chesto Berry": "Maronbeere",
    "Pecha Berry": "Pirsifbeere",
    "Rawst Berry": "Fragiabeere",
    "Aspear Berry": "Wilbirbeere",
    "Leppa Berry": "Jonagobeere",
    "Oran Berry": "Sinelbeere",
    "Persim Berry": "Persimbeere",
    "Lum Berry": "Prunusbeere",
    "Sitrus Berry": "Tsitrubeere",
    "Figy Berry": "Giefebeere",
    "Wiki Berry": "Wikibeere",
    "Mago Berry": "Magobeere",
    "Aguav Berry": "Gauvebeere",
    "Iapapa Berry": "Yapabeere",
    "Razz Berry": "Himmihbeere",
    "Bluk Berry": "Morbbeere",
    "Nanab Berry": "Nanabbeere",
    "Wepear Berry": "Nirbebeere",
    "Pinap Berry": "Sananabeere",
    "Pomeg Berry": "Granabeere",
    "Kelpsy Berry": "Setangbeere",
    "Qualot Berry": "Qualotbeere",
    "Hondew Berry": "Honmelbeere",
    "Grepa Berry": "Labrusbeere",
    "Tamato Berry": "Tamotbeere",
    "Cornn Berry": "Saimbeere",
    "Magost Berry": "Magostbeere",
    "Rabuta Berry": "Rabutabeere",
    "Nomel Berry": "Tronzibeere",
    "Spelon Berry": "Kiwanbeere",
    "Pamtre Berry": "Pallmbeere",
    "Watmel Berry": "Wasmelbeere",
    "Durin Berry": "Durinbeere",
    "Belue Berry": "Myrtilbeere",
    "Occa Berry": "Koakobeere",
    "Passho Berry": "Foepasbeere",
    "Wacan Berry": "Kerzalbeere",
    "Rindo Berry": "Grindobeere",
    "Yache Berry": "Kiroyabeere",
    "Chople Berry": "Rospelbeere",
    "Kebia Berry": "Grarzbeere",
    "Shuca Berry": "Schukebeere",
    "Coba Berry": "Kobabeere",
    "Payapa Berry": "Pyapabeere",
    "Tanga Berry": "Tanigabeere",
    "Charti Berry": "Chiaribeere",
    "Kasib Berry": "Zitarzbeere",
    "Haban Berry": "Terirobeere",
    "Colbur Berry": "Burleobeere",
    "Babiri Berry": "Babiribeere",
    "Chilan Berry": "Latchibeere",
    "Liechi Berry": "Lydzibeere",
    "Ganlon Berry": "Linganbeere",
    "Salac Berry": "Salkabeere",
    "Petaya Berry": "Tahaybeere",
    "Apicot Berry": "Apikobeere",
    "Lansat Berry": "Lansatbeere",
    "Starf Berry": "Krambobeere",
    "Enigma Berry": "Enigmabeere",
    "Micle Berry": "Wunfrubeere",
    "Custap Berry": "Eipfelbeere",
    "Jaboca Berry": "Jabocabeere",
    "Rowap Berry": "Roselbeere",
    "Kee Berry": "Akibeere",
    "Marang Berry": "Tarabeere",
    "Roseli Berry": "Hibisbeere",
}

# English item name -> official German (Germany) name, for the non-Berry
# inline cells. Every value verified to fit the 13-glyph name cell (the apply
# pass re-validates fit before writing). Names whose official DE form is
# longer than 13 glyphs are intentionally excluded (see module docstring);
# German compounds run long, so several items that fit in FR do not fit here
# (e.g. "Room Service" -> "Bizarroservice" is 14 glyphs, "Bottle Cap" ->
# "Silberkronkorken" is 16, "Purp Nectar"/Purple Nectar -> "Purpurner Nektar"
# is 16 with the space).
ITEM_NAMES = {
    # Evolution & special stones
    "Sun Stone": "Sonnenstein",
    "Moon Stone": "Mondstein",
    "Fire Stone": "Feuerstein",
    "Thunderstone": "Donnerstein",
    "Water Stone": "Wasserstein",
    "Leaf Stone": "Blattstein",
    "Dusk Stone": "Finsterstein",
    "Dawn Stone": "Funkelstein",
    "Shiny Stone": "Leuchtstein",
    "Oval Stone": "Ovaler Stein",
    "Ice Stone": "Eisstein",
    "Everstone": "Ewigstein",
    # Valuables
    "Pearl": "Perle",
    "Big Pearl": "Riesenperle",
    "Stardust": "Sternenstaub",
    "Nugget": "Nugget",
    "Big Nugget": "Riesennugget",
    "Heart Scale": "Herzschuppe",
    "Rare Bone": "Steinknochen",
    "TinyMushroom": "Minipilz",
    "Big Mushroom": "Riesenpilz",
    "Prism Scale": "Schönschuppe",
    "Dragon Scale": "Drachenhaut",
    "Relic Copper": "Alter Heller",
    "Relic Silver": "Alter Taler",
    "Relic Gold": "Alter Dukat",
    "Relic Vase": "Alte Vase",
    "Relic Band": "Alter Reif",
    "Relic Statue": "Alte Statue",
    # Evolution-trigger held items
    "Protector": "Schützer",
    "Magmarizer": "Magmaisierer",
    "Electirizer": "Stromisierer",
    "Razor Claw": "Scharfklaue",
    "Razor Fang": "Scharfzahn",
    "Reaper Cloth": "Düsterumhang",
    "Up-Grade": "Up-Grade",
    "Metal Coat": "Metallmantel",
    "King's Rock": "King-Stein",
    "Dragon Fang": "Drachenzahn",
    "Whip Dream": "Sahnehäubchen",
    # General held / battle items
    "Choice Band": "Wahlband",
    "White Herb": "Schlohkraut",
    "Macho Brace": "Machoband",
    "Exp. Share": "EP-Teiler",
    "Quick Claw": "Flinkklaue",
    "Soothe Bell": "Sanftglocke",
    "Mental Herb": "Mentalkraut",
    "Amulet Coin": "Münzamulett",
    "Cleanse Tag": "Schutzband",
    "Smoke Ball": "Rauchball",
    "Focus Band": "Fokus-Band",
    "Scope Lens": "Scope-Linse",
    "Soft Sand": "Pudersand",
    "Miracle Seed": "Wundersaat",
    "Black Belt": "Schwarzgurt",
    "Magnet": "Magnet",
    "Mystic Water": "Zauberwasser",
    "Sharp Beak": "Hackattack",
    "Poison Barb": "Giftstich",
    "Spell Tag": "Bannsticker",
    "Charcoal": "Holzkohle",
    "Silk Scarf": "Seidenschal",
    "Shell Bell": "Seegesang",
    "Sea Incense": "Seerauch",
    "Lax Incense": "Laxrauch",
    "Lucky Punch": "Lucky Punch",
    "Metal Powder": "Metallstaub",
    "Thick Club": "Kampfknochen",
    "Leek": "Lauchstange",
    "Rocky Helmet": "Beulenhelm",
    "Wide Lens": "Großlinse",
    "Zoom Lens": "Zoomlinse",
    "Destiny Knot": "Fatumknoten",
    "Smooth Rock": "Glattbrocken",
    "Damp Rock": "Nassbrocken",
    "Heat Rock": "Heißbrocken",
    "Icy Rock": "Eisbrocken",
    "Big Root": "Großwurzel",
    "Light Clay": "Lichtlehm",
    "Big Malasada": "Maxi-Malasada",
    "Iron Ball": "Eisenkugel",
    "Lagging Tail": "Schwerschweif",
    "Sticky Barb": "Klettdorn",
    "Muscle Band": "Muskelband",
    "Expert Belt": "Expertengurt",
    "Power Herb": "Energiekraut",
    "Float Stone": "Leichtstein",
    "Grip Claw": "Griffklaue",
    "Eviolite": "Evolith",
    "Red Card": "Rote Karte",
    "Eject Button": "Fluchtknopf",
    "Air Balloon": "Luftballon",
    "Absorb Bulb": "Knolle",
    "Cell Battery": "Akku",
    "Snowball": "Schneeball",
    "Metronome": "Metronom",
    "Quick Powder": "Flottstaub",
    "Shed Shell": "Wechselhülle",
    "Binding Band": "Klammerband",
    "Ring Target": "Zielscheibe",
    "Adrenal Orb": "Zitterorb",
    "Throat Spray": "Halsspray",
    "Eject Pack": "Fluchttasche",
    # "Room Service": "Bizarroservice" excluded — 14 glyphs, does not fit.
    # Type Gems (X-Juwel) — only those that fit the cell
    "Normal Gem": "Normaljuwel",
    "Fighting Gem": "Kampfjuwel",
    "Flying Gem": "Flugjuwel",
    "Poison Gem": "Giftjuwel",
    "Ground Gem": "Bodenjuwel",
    "Rock Gem": "Gesteinsjuwel",
    "Bug Gem": "Käferjuwel",
    "Ghost Gem": "Geisterjuwel",
    "Steel Gem": "Stahljuwel",
    "Fire Gem": "Feuerjuwel",
    "Water Gem": "Wasserjuwel",
    "Grass Gem": "Pflanzenjuwel",
    "Psychic Gem": "Psychojuwel",
    "Ice Gem": "Eisjuwel",
    "Dragon Gem": "Drakojuwel",
    "Fairy Gem": "Feenjuwel",
    # Silvally type ROMs (Memory / "-Disc" in German)
    "Fist Memory": "Kampf-Disc",
    "Sky Memory": "Flug-Disc",
    "Toxic Memory": "Gift-Disc",
    "Earth Memory": "Boden-Disc",
    "Rock Memory": "Gesteins-Disc",
    "Bug Memory": "Käfer-Disc",
    "Ghost Memory": "Geister-Disc",
    "Steel Memory": "Stahl-Disc",
    "Fire Memory": "Feuer-Disc",
    "Water Memory": "Wasser-Disc",
    "Grass Memory": "Pflanzen-Disc",
    "Zap Memory": "Elektro-Disc",
    "Psych Memory": "Psycho-Disc",
    "Ice Memory": "Eis-Disc",
    "Draco Memory": "Drachen-Disc",
    "Dark Memory": "Unlicht-Disc",
    "Fairy Memory": "Feen-Disc",
    # Genesect Drives
    "Burn Drive": "Flammenmodul",
    "Douse Drive": "Aquamodul",
    "Shock Drive": "Blitzmodul",
    "Chill Drive": "Gefriermodul",
    # Incenses
    "Luck Incense": "Glücksrauch",
    "Full Incense": "Lahmrauch",
    "Pure Incense": "Scheuchrauch",
    "Rock Incense": "Steinrauch",
    "Rose Incense": "Rosenrauch",
    "Wave Incense": "Wellenrauch",
    # Misc
    # "Bottle Cap": "Silberkronkorken" excluded — 16 glyphs, does not fit.
    # "Costume Box" is an Unbound-custom wardrobe menu item, not an official
    # Nintendo item (no Bulbapedia entry); translated directly like the FR
    # script's own coinage ("Boîte Costume").
    "Costume Box": "Kostümbox",
    # Mails (X-Brief)
    "Orange Mail": "Zigzagbrief",
    "Harbor Mail": "Hafenbrief",
    "Wood Mail": "Waldbrief",
    "Wave Mail": "Wellenbrief",
    "Bead Mail": "Perlenbrief",
    "Shadow Mail": "Dunkelbrief",
    "Tropic Mail": "Tropenbrief",
    "Dream Mail": "Traumbrief",
    "Retro Mail": "Retrobrief",
    "Mech Mail": "Eilbrief",
    # Fishing rods
    "Old Rod": "Angel",
    "Good Rod": "Profiangel",
    "Super Rod": "Superangel",
    # Key / misc items
    "Coin Case": "Münzkorb",
    "Meteorite": "Meteorit",
    # "Mitgl.Karte" is the real, era-appropriate official abbreviated German
    # name for Member Card (Gen IV-VI); the modern unabbreviated
    # "Mitgliedskarte" is 14 glyphs and does not fit.
    "Member Card": "Mitgl.Karte",
    "Lunar Wing": "Lunarfeder",
    "VS Seeker": "Kampffahnder",
    "Powder Jar": "Puderdöschen",
    "Devon Scope": "Devon-Scope",
    "Mach Bike": "Eilrad",
    "Letter": "Brief",
    "Eon Ticket": "Äon-Ticket",
    # Feather vitamins (Wings)
    "Health Wing": "Heilfeder",
    "Muscle Wing": "Kraftfeder",
    "Resist Wing": "Abwehrfeder",
    "Genius Wing": "Geniefeder",
    "Clever Wing": "Espritfeder",
    "Swift Wing": "Flinkfeder",
    "Pretty Wing": "Prachtfeder",
    "Silver Wing": "Silberflügel",
    "Rainbow Wing": "Buntschwinge",
    # Nectars
    "Red Nectar": "Roter Nektar",
    "Pink Nectar": "Rosa Nektar",
    # "Purp Nectar" (Purple Nectar) -> "Purpurner Nektar" excluded — 16
    # glyphs incl. space, does not fit.
    # Apricorn / special Poké Balls
    "Fast Ball": "Turboball",
    "Level Ball": "Levelball",
    "Lure Ball": "Köderball",
    "Heavy Ball": "Schwerball",
    "Friend Ball": "Freundesball",
    "Moon Ball": "Mondball",
    "Sport Ball": "Turnierball",
    "Beast Ball": "Ultraball",
    "Dream Ball": "Traumball",
    # Flutes
    "Sun Flute": "Sonnenflöte",
    "Moon Flute": "Mondflöte",
    # Charms
    "Oval Charm": "Ovalpin",
    "Shiny Charm": "Schillerpin",
    # Fossils
    "Helix Fossil": "Helixfossil",
    "Dome Fossil": "Domfossil",
    "Skull Fossil": "Kopffossil",
    "Plume Fossil": "Federfossil",
    "Sail Fossil": "Flossenfossil",
    "Old Amber": "Altbernstein",
    # Hidden Machines: HM -> VM (Versteckte Maschine) in DE
    "HM01": "VM01",
    "HM02": "VM02",
    "HM03": "VM03",
    "HM04": "VM04",
    "HM05": "VM05",
    "HM06": "VM06",
    "HM07": "VM07",
    "HM08": "VM08",
    # Unbound custom battle items — trailing-space variant in source ROM
    "Muscle ": "Muskel+",
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
    German replacement must fit the 14-byte name field; item data after the
    name field is never touched. Idempotent: cells already holding the German
    name are skipped.
    """
    # Pre-validate every German replacement fits before writing anything.
    for de in names.values():
        if len(encode(de)) + 1 > NAME_FIELD:
            raise ValueError(f"{de!r} does not fit a {NAME_FIELD}-byte name cell")

    de_by_en = names
    patched = 0
    for i in range(SCAN_COUNT):
        offset = ITEM_TABLE_BASE + i * ITEM_STRIDE
        if offset + NAME_FIELD > len(data):
            break
        current = decode_name(data, offset)
        de = de_by_en.get(current)
        if de is None:
            continue  # not a cell we translate (or already German → no match)
        new_bytes = encode(de)
        old_bytes = encode(current)
        # Sanity: the cell must really hold the English name + terminator.
        if (
            bytes(data[offset : offset + len(old_bytes)]) != old_bytes
            or data[offset + len(old_bytes)] != 0xFF
        ):
            continue
        # Write German name + terminator, then clear the rest of the span the
        # old name occupied so no stale glyphs trail past the terminator. Stays
        # entirely within the 14-byte name field.
        cleared = max(len(old_bytes), len(new_bytes)) + 1
        data[offset : offset + cleared] = (
            new_bytes + b"\xff" + bytes(cleared - len(new_bytes) - 1)
        )
        patched += 1
    return patched


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, default=Path("output/roms/GenedRom-de.gba"))
    args = parser.parse_args()

    data = bytearray(args.rom.read_bytes())
    patched = apply_item_name_fixes(data, ALL_NAMES)
    if patched:
        args.rom.write_bytes(data)
    print(f"Item name cells translated: {patched} (of {len(ALL_NAMES)} known)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
