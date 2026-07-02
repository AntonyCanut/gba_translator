#!/usr/bin/env python3
"""Translate untranslated item NAME cells (Berries + general items) in the FR ROM.

Item names live as fixed-width cells inside the CFRU item table (``gItems``)
at 0x876074, stride 44: ``name[14]`` followed by the item data (id, price,
hold-effect, description pointer at +0x14…). These *inline* name cells are
**copied byte-for-byte from the source ROM** by the build pipeline — no
translation pass touches them (they are absent from translation_ready.json,
combined_fr.txt and the Spanish extraction). The Unbound source already ships
French names for the medicine/general items *and* for the long names stored as a
ROM pointer (union: name[14] starting with an 0x08 MSB pointer → "Bright Powder"
→ "Poudre Claire" etc. are pipeline-translated). What stayed English are the
short *inline* cells: every Berry ("Aspear Berry" → "Baie Willia"), plus a large
set of general items — evolution stones, valuables, held/battle items, type Gems,
Silvally ROMs, Genesect Drives, incenses, mails, fishing rods, fossils, HMs…

This script rewrites those inline cells in place, byte-exact, with their official
French (France) names. It is data-driven: each cell whose current name exactly
matches an English key in ALL_NAMES is rewritten with the French value. Cells
that already hold the French name are skipped (idempotent), pointer cells never
match an English key, and item data after the 14-byte name field is never
touched.

French names are the official localised names (verified against Bulbapedia /
Poképédia "In other languages" tables); only names that fit the 13-glyph cell
are included here. Names whose official FR form exceeds 13 glyphs (most Mega
Stones, type Plates, "Joyau Électrik"/"Joyau Ténèbres", long fossils like
"Fossile Mâchoire", custom Unbound Mega-key items) require a pointer
relocation — out of scope for this byte-exact in-place patch — and are left as
the source ships them. Z-Crystals ("Normalium Z"…) are identical in FR by
design and need no change.

Usage:
    python3 scripts/patch_item_names_fr.py --rom output/roms/GenedRom-fr.gba
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

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

# English item name -> official French (France) name.
# Berry names verified individually against Bulbapedia / Poképédia "In other
# languages" tables (canonical localised names used by the official FR games).
# NOTE: CFRU spells the Gen VI berry "Maranga Berry" as "Marang Berry"; the key
# below matches the in-ROM English string.
BERRY_NAMES = {
    "Cheri Berry": "Baie Ceriz",
    "Chesto Berry": "Baie Maron",
    "Pecha Berry": "Baie Pêcha",
    "Rawst Berry": "Baie Fraive",
    "Aspear Berry": "Baie Willia",
    "Leppa Berry": "Baie Mepo",
    "Oran Berry": "Baie Oran",
    "Persim Berry": "Baie Kika",
    "Lum Berry": "Baie Prine",
    "Sitrus Berry": "Baie Sitrus",
    "Figy Berry": "Baie Figuy",
    "Wiki Berry": "Baie Wiki",
    "Mago Berry": "Baie Mago",
    "Aguav Berry": "Baie Gowav",
    "Iapapa Berry": "Baie Papaya",
    "Razz Berry": "Baie Framby",
    "Bluk Berry": "Baie Remu",
    "Nanab Berry": "Baie Nanab",
    "Wepear Berry": "Baie Repoi",
    "Pinap Berry": "Baie Nanana",
    "Pomeg Berry": "Baie Grena",
    "Kelpsy Berry": "Baie Alga",
    "Qualot Berry": "Baie Qualot",
    "Hondew Berry": "Baie Lonme",
    "Grepa Berry": "Baie Résin",
    "Tamato Berry": "Baie Tamato",
    "Cornn Berry": "Baie Siam",
    "Magost Berry": "Baie Mangou",
    "Rabuta Berry": "Baie Rabuta",
    "Nomel Berry": "Baie Tronci",
    "Spelon Berry": "Baie Kiwan",
    "Pamtre Berry": "Baie Palma",
    "Watmel Berry": "Baie Stekpa",
    "Durin Berry": "Baie Durin",
    "Belue Berry": "Baie Myrte",
    "Occa Berry": "Baie Chocco",
    "Passho Berry": "Baie Pocpoc",
    "Wacan Berry": "Baie Parma",
    "Rindo Berry": "Baie Ratam",
    "Yache Berry": "Baie Nanone",
    "Chople Berry": "Baie Pomroz",
    "Kebia Berry": "Baie Kébia",
    "Shuca Berry": "Baie Jouca",
    "Coba Berry": "Baie Cobaba",
    "Payapa Berry": "Baie Yapap",
    "Tanga Berry": "Baie Panga",
    "Charti Berry": "Baie Charti",
    "Kasib Berry": "Baie Sédra",
    "Haban Berry": "Baie Fraigo",
    "Colbur Berry": "Baie Lampou",
    "Babiri Berry": "Baie Babiri",
    "Chilan Berry": "Baie Zalis",
    "Liechi Berry": "Baie Lichii",
    "Ganlon Berry": "Baie Lingan",
    "Salac Berry": "Baie Sailak",
    "Petaya Berry": "Baie Pitaye",
    "Apicot Berry": "Baie Abriko",
    "Lansat Berry": "Baie Lansat",
    "Starf Berry": "Baie Frista",
    "Enigma Berry": "Baie Énigma",
    "Micle Berry": "Baie Micle",
    "Custap Berry": "Baie Chérim",
    "Jaboca Berry": "Baie Jaboca",
    "Rowap Berry": "Baie Pommo",
    "Kee Berry": "Baie Éka",
    "Marang Berry": "Baie Rangma",
    "Roseli Berry": "Baie Selro",
}

# English item name -> official French (France) name, for the non-Berry inline
# cells. Every value verified to fit the 13-glyph name cell (the apply pass
# re-validates fit before writing). Names whose official FR form is longer than
# 13 glyphs are intentionally excluded (see module docstring).
ITEM_NAMES = {
    # Evolution & special stones
    "Sun Stone": "Pierre Soleil",
    "Moon Stone": "Pierre Lune",
    "Fire Stone": "Pierre Feu",
    "Thunderstone": "Pierre Foudre",
    "Water Stone": "Pierre Eau",
    "Leaf Stone": "Pierre Plante",
    "Dusk Stone": "Pierre Nuit",
    "Dawn Stone": "Pierre Aube",
    "Shiny Stone": "Pierre Éclat",
    "Oval Stone": "Pierre Ovale",
    "Ice Stone": "Pierre Glace",
    "Everstone": "Pierre Stase",
    # Valuables
    "Pearl": "Perle",
    "Big Pearl": "Grosse Perle",
    "Stardust": "Poudre Étoile",
    "Nugget": "Pépite",
    "Big Nugget": "Grosse Pépite",
    "Heart Scale": "Écaille Cœur",
    "Rare Bone": "Os Rare",
    "TinyMushroom": "Petit Champi",
    "Big Mushroom": "Gros Champi",
    "Prism Scale": "Bel'Écaille",
    "Dragon Scale": "Écaille Draco",
    "Relic Copper": "Vieux Cuivre",
    "Relic Silver": "Vieil Argent",
    "Relic Gold": "Vieil Or",
    "Relic Vase": "Vieux Vase",
    "Relic Band": "Vieux Bijou",
    "Relic Statue": "Vieille Idole",
    # Evolution-trigger held items
    "Protector": "Protecteur",
    "Magmarizer": "Magmariseur",
    "Electirizer": "Électriseur",
    "Razor Claw": "Griffe Rasoir",
    "Razor Fang": "Croc Rasoir",
    "Reaper Cloth": "Tissu Spectre",
    "Up-Grade": "Améliorator",
    "Metal Coat": "Peau Métal",
    "King's Rock": "Roche Royale",
    "Dragon Fang": "Croc Dragon",
    "Whip Dream": "Crème Fouet",
    # General held / battle items
    "Choice Band": "Bandeau Choix",
    "White Herb": "Herbe Blanche",
    "Macho Brace": "Brac. Macho",
    "Exp. Share": "Multi Exp",
    "Quick Claw": "Vive Griffe",
    "Soothe Bell": "Grelot Zen",
    "Mental Herb": "Herbe Mental",
    "Amulet Coin": "Pièce Rune",
    "Cleanse Tag": "Rune Purif",
    "Smoke Ball": "Boule Fumée",
    "Focus Band": "Bandeau",
    "Scope Lens": "Lentilscope",
    "Soft Sand": "Sable Doux",
    "Miracle Seed": "Graine Mira",
    "Black Belt": "Ceinturnoire",
    "Magnet": "Aimant",
    "Mystic Water": "Eau Mystique",
    "Sharp Beak": "Bec Pointu",
    "Poison Barb": "Pic Venin",
    "Spell Tag": "Rune Sort",
    "Charcoal": "Charbon",
    "Silk Scarf": "Mouchoir Soie",
    "Shell Bell": "Grelot Coque",
    "Sea Incense": "Encens Marin",
    "Lax Incense": "Encens Doux",
    "Lucky Punch": "Poing Chance",
    "Metal Powder": "Poudre Métal",
    "Thick Club": "Os Épais",
    "Leek": "Poireau",
    "Rocky Helmet": "Casque Brut",
    "Wide Lens": "Loupe",
    "Zoom Lens": "Lentille Zoom",
    "Destiny Knot": "Nœud Destin",
    "Smooth Rock": "Roche Lisse",
    "Damp Rock": "Roche Humide",
    "Heat Rock": "Roche Chaude",
    "Icy Rock": "Roche Glacée",
    "Big Root": "Grosse Racine",
    "Light Clay": "Lumargile",
    "Big Malasada": "Gros Malasada",
    "Iron Ball": "Balle Fer",
    "Lagging Tail": "Reste-Là",
    "Sticky Barb": "Pic Toxik",
    "Muscle Band": "Bandeau Force",
    "Expert Belt": "Ceinture Pro",
    "Power Herb": "Herbe Pouvoir",
    "Float Stone": "Pierre Lest",
    "Grip Claw": "Accro Griffe",
    "Eviolite": "Évoluroc",
    "Red Card": "Carte Rouge",
    "Eject Button": "Bouton Fuite",
    "Air Balloon": "Ballon",
    "Absorb Bulb": "Bulbe",
    "Cell Battery": "Pile",
    "Snowball": "Boule Neige",
    "Metronome": "Métronome",
    "Quick Powder": "Poudre Vite",
    "Shed Shell": "Carapace Mue",
    "Binding Band": "Bandeau Lien",
    "Ring Target": "Cible",
    "Adrenal Orb": "Orbe Adréna",
    "Throat Spray": "Spray Gorge",
    "Eject Pack": "Sac Fuite",
    "Room Service": "Service Salle",
    # Type Gems (Joyau X) — only those that fit the cell
    "Normal Gem": "Joyau Normal",
    "Fighting Gem": "Joyau Combat",
    "Flying Gem": "Joyau Vol",
    "Poison Gem": "Joyau Poison",
    "Ground Gem": "Joyau Sol",
    "Rock Gem": "Joyau Roche",
    "Bug Gem": "Joyau Insecte",
    "Ghost Gem": "Joyau Spectre",
    "Steel Gem": "Joyau Acier",
    "Fire Gem": "Joyau Feu",
    "Water Gem": "Joyau Eau",
    "Grass Gem": "Joyau Plante",
    "Psychic Gem": "Joyau Psy",
    "Ice Gem": "Joyau Glace",
    "Dragon Gem": "Joyau Dragon",
    "Fairy Gem": "Joyau Fée",
    # Silvally type ROMs (Memory)
    "Fist Memory": "ROM Combat",
    "Sky Memory": "ROM Vol",
    "Toxic Memory": "ROM Poison",
    "Earth Memory": "ROM Sol",
    "Rock Memory": "ROM Roche",
    "Bug Memory": "ROM Insecte",
    "Ghost Memory": "ROM Spectre",
    "Steel Memory": "ROM Acier",
    "Fire Memory": "ROM Feu",
    "Water Memory": "ROM Eau",
    "Grass Memory": "ROM Plante",
    "Zap Memory": "ROM Élektrik",
    "Psych Memory": "ROM Psy",
    "Ice Memory": "ROM Glace",
    "Draco Memory": "ROM Dragon",
    "Dark Memory": "ROM Ténèbres",
    "Fairy Memory": "ROM Fée",
    # Genesect Drives
    "Burn Drive": "Module Pyro",
    "Douse Drive": "Module Aqua",
    "Shock Drive": "Module Choc",
    "Chill Drive": "Module Cryo",
    # Incenses
    "Luck Incense": "Encens Veine",
    "Full Incense": "Encens Plein",
    "Pure Incense": "Encens Pur",
    "Rock Incense": "Encens Roc",
    "Rose Incense": "Encens Rose",
    "Wave Incense": "Encens Vague",
    # Misc
    "Bottle Cap": "Capsule",
    "Costume Box": "Boîte Costume",
    # Mails (Lettre X)
    "Orange Mail": "Lettre Orange",
    "Harbor Mail": "Lettre Port",
    "Wood Mail": "Lettre Bois",
    "Wave Mail": "Lettre Vague",
    "Bead Mail": "Lettre Perle",
    "Shadow Mail": "Lettre Ombre",
    "Tropic Mail": "Lettre Tropic",
    "Dream Mail": "Lettre Rêve",
    "Retro Mail": "Lettre Rétro",
    "Mech Mail": "Lettre Méca",
    # Fishing rods
    "Old Rod": "Canne",
    "Good Rod": "Super Canne",
    "Super Rod": "Méga Canne",
    # Key / misc items
    "Coin Case": "Étui à Jetons",
    "Meteorite": "Météorite",
    "Member Card": "Carte Membre",
    "Lunar Wing": "Aile Lunaire",
    "VS Seeker": "ChercheDuel",
    "Powder Jar": "Bocal Poudre",
    "Devon Scope": "Scope Devon",
    "Mach Bike": "Vélo Course",
    "Letter": "Lettre",
    "Eon Ticket": "Ticket Éon",
    # Feather vitamins (Wings)
    "Health Wing": "Aile Santé",
    "Muscle Wing": "Aile Muscle",
    "Resist Wing": "Aile Défense",
    "Genius Wing": "Aile Génie",
    "Clever Wing": "Aile Esprit",
    "Swift Wing": "Aile Vitesse",
    "Pretty Wing": "Jolie Plume",
    "Silver Wing": "Aile Argentée",
    "Rainbow Wing": "Aile Aurore",
    # Nectars
    "Red Nectar": "Nectar Rouge",
    "Pink Nectar": "Nectar Rose",
    "Purp Nectar": "Nectar Violet",
    # Apricorn / special Poké Balls (FR names; "Ultra Ball" is FR for Beast Ball)
    "Fast Ball": "Speed Ball",
    "Level Ball": "Niveau Ball",
    "Lure Ball": "Appât Ball",
    "Heavy Ball": "Masse Ball",
    "Friend Ball": "Copain Ball",
    "Moon Ball": "Lune Ball",
    "Sport Ball": "Compét Ball",
    "Beast Ball": "Ultra Ball",
    "Dream Ball": "Rêve Ball",
    # Flutes
    "Sun Flute": "Flûte Soleil",
    "Moon Flute": "Flûte Lune",
    # Charms
    "Oval Charm": "Charme Ovale",
    "Shiny Charm": "Charme Chroma",
    # Fossils that fit the cell (long ones need a pointer relocation → skipped)
    "Helix Fossil": "Fossile Hélix",
    "Dome Fossil": "Fossile Dôme",
    "Skull Fossil": "Fossile Crâne",
    "Plume Fossil": "Fossile Plume",
    "Sail Fossil": "Fossile Voile",
    "Old Amber": "Vieil Ambre",
    # Hidden Machines: HM → CS (Capacité Secrète) in FR
    "HM01": "CS01",
    "HM02": "CS02",
    "HM03": "CS03",
    "HM04": "CS04",
    "HM05": "CS05",
    "HM06": "CS06",
    "HM07": "CS07",
    "HM08": "CS08",
    # Unbound custom battle items — trailing-space variant in source ROM
    "Muscle ": "Muscle+",
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
    French replacement must fit the 14-byte name field; item data after the
    name field is never touched. Idempotent: cells already holding the French
    name are skipped.
    """
    # Pre-validate every French replacement fits before writing anything.
    for fr in names.values():
        if len(encode(fr)) + 1 > NAME_FIELD:
            raise ValueError(f"{fr!r} does not fit a {NAME_FIELD}-byte name cell")

    fr_by_en = names
    patched = 0
    for i in range(SCAN_COUNT):
        offset = ITEM_TABLE_BASE + i * ITEM_STRIDE
        if offset + NAME_FIELD > len(data):
            break
        current = decode_name(data, offset)
        fr = fr_by_en.get(current)
        if fr is None:
            continue  # not a cell we translate (or already French → no match)
        new_bytes = encode(fr)
        old_bytes = encode(current)
        # Sanity: the cell must really hold the English name + terminator.
        if (
            bytes(data[offset : offset + len(old_bytes)]) != old_bytes
            or data[offset + len(old_bytes)] != 0xFF
        ):
            continue
        # Write French name + terminator, then clear the rest of the span the
        # old name occupied so no stale glyphs trail past the terminator. Stays
        # entirely within the 14-byte name field.
        cleared = max(len(old_bytes), len(new_bytes)) + 1
        data[offset : offset + cleared] = (
            new_bytes + b"\xff" + bytes(cleared - len(new_bytes) - 1)
        )
        patched += 1
    return patched


# ROM offset → corrected French description (3 lines max to fit the bag window).
# "Muscle " (item #83) ships a 4-line description that overflows the display;
# the shorter version below fits without cutting any meaning.
ITEM_DESC_OVERRIDES: dict[int, str] = {
    0xB40FC0: (
        "Monte fortement le taux de\n"
        "critiques. Usage unique. Annulé\n"
        "si le Pokémon se retire."
    ),
}

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
    for rom_offset, french_text in ITEM_DESC_OVERRIDES.items():
        encoded = TextEncoder.encode_pokemon(french_text)
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
    parser.add_argument("--rom", type=Path, default=Path("output/roms/GenedRom-fr.gba"))
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
