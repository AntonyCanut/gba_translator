"""Gardes source des lots de contenu allemand du ticket F-601."""

from __future__ import annotations

import importlib
import json
import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.rom

from src.core.collision_check import live_target, plausible_sites
from src.core.text_codec import GERMAN_UMLAUT_CHARS, TextDecoder, TextEncoder


ROOT = Path(__file__).resolve().parents[3]
COMBINED_DE = ROOT / "languages" / "de" / "combined_de.txt"
ENGLISH_TEXTS = ROOT / "output" / "extracted" / "extracted_texts" / "englishrom_texts.json"
ENGLISH_ROM = ROOT / "input" / "roms" / "englishrom.gba"
BUILT_DE_ROM = ROOT / "output" / "roms" / "GenedRom-de.gba"
Builder = importlib.import_module(
    "src.translators.19_build_translated_rom_generic"
).TranslatedROMBuilder

EXPECTED = {
    # Menus et invites de voyage.
    0x1EE7EBB: "<0xFC><0x01><0x02>Nach Crater Town fliegen?",
    0x1EE7ED2: "<0xFC><0x01><0x02>Nach Blizzard City fliegen?",
    0x1F4F15E: "Verbindungsinfo",
    0x1F4F16E: "Kampfrekorde",
    0x1F4F19F: "Ruhmeshalle",
    0x1F68047: "<0xFC><0x01><0x02>Nach <0xFC><0x01><0x06>Dehara City<0xFC><0x01><0x02> zurückkehren?",
    # Spectacle Croagunk.
    0x1F53057: "Alle Croagunk bereit!\nKommt zusammen!",
    0x1F53080: "Das Croagunk, dem ihr heute\nfolgen sollt, ist...",
    0x1F530B3: "Dieses Croagunk hier mit dem\n<0xFD><0x03>!<0xFB>Es trägt ein <0xFD><0x02>!\nAuf die Plätze, fertig, los!",
    0x1F531E9: "<0xFC><0x01><0x04>Du liegst...\n...<0xFA>ungeheuer falsch!<0xFB>Tut mir leid...",
    0x1F5321B: "<0xFC><0x01><0x04>Damit endet unsere große\nCroagunk-Show!<0xFB>Vielen Dank an euch alle!",
    0x1F53268: "Wie schade...\nAber sie ist garantiert großartig.",
    0x1F53298: "Willst du die Croagunk noch\neinmal sehen?<0xFB>Die Vorbereitung dauert eine\nWeile, komm also morgen<0xFA>wieder!",
    # Mission de pêche.
    0x1F53440: "Durchschnittsangler",
    0x1F5344F: "Großer Angler",
    0x1F5345E: "Angelmeister",
    0x1F5346C: "Hol deine Angel heraus und\nleg los! Fange <0xFD><0x02> Pokémon.",
    0x1F534AD: "Wirf den Köder aus und locke\ndie Fische an! Fange <0xFD><0x02> Pokémon.",
    0x1F534F4: "Stell dich fest hin und schau\nnach vorn. Fange <0xFD><0x02> Pokémon.",
    0x1F5378E: "Nach deiner tollen Leistung habe ich\nnun eine neue Aufgabe für dich.<0xFB>Wirb weiter für die Angeln der\nCube Corp., indem du Pokémon<0xFA>mindestens <0xFC><0x01><0x06><0xFD><0x02><0xFC><0x01><0x08>-mal angelst.",
    0x1F53912: "Großartig, Trainer!<0xFB>Die Cube Corp. meldet mir,\ndass du ihre Marke insgesamt<0xFA><0xFC><0x01><0x06><0xFD><0x03><0xFC><0x01><0x08>-mal beworben hast!<0xFB>Hier ist deine Belohnung!",
    0x1F53999: "Dank deiner Angelerfolge wurde ich\nbefördert!<0xFB>Jetzt bin ich Assistent des\nRegionalleiters der Angelabteilung<0xFA>der Cube Corp.!<0xFB>Bald leite ich\nden Laden selbst!",
    0x1F53A46: "Meine Quellen bei der Cube Corp.\nsagen, du hast bisher nur <0xFC><0x01><0x06><0xFD><0x03><0xFC><0x01><0x08><0xFA>Pokémon geangelt.<0xFB>Für die Belohnung musst du mindestens\n<0xFC><0x01><0x06><0xFD><0x02><0xFC><0x01><0x08> fangen.",
    0x1F53ADB: "Zumindest würde ich dir gern eines\ngeben, aber dein Team hat dafür<0xFA>keinen Platz.",
    0x1F5428A: "Insgesamt gibt es 120 TMs.\nKannst du sie alle finden?",
    # Descriptions de CT.
    0x1F545CC: "Diese TM wurde im äußeren\nHeckenlabyrinth gefunden.",
    0x1F545F9: "Diese TM lag an den Schneeklippen\nund war nur mit Kraxler erreichbar.",
    0x1F54637: "Diese TM wurde im UG1 nach\nÜberqueren der blauen Brücke gefunden.",
    0x1F54670: "Diese TM wurde auf dem\nMarktplatz gekauft.",
    0x1F5469A: "Diese TM wurde im großen Raum\nim EG nach Surfer gefunden.",
    0x1F546D6: "Diese TM wurde östlich im Sumpf\nnach Surfer gefunden.",
    0x1F54716: "Ein Clown gab dir diese TM,\nnachdem du ihm bei der Flucht halfst.",
    0x1F54752: "Diese TM wurde auf dem\nMarktplatz gekauft.",
    0x1F5477C: "Diese TM wurde östlich der Route\nnach Einsatz von Zerschneider gefunden.",
    0x1F547BD: "Der Mann für Kraftreserve gab dir\ndiese TM in seinem Haus.",
    0x1F547F9: "Ein Clown gab dir diese TM,\nnachdem du ihm Solrock oder\nSolgaleo gezeigt hast.",
    0x1F54842: "Diese TM war hinter\ndem Poké Mart versteckt.",
    0x1F5486C: "Diese TM wurde im 4F nach\ndem Sieg über zwei Ass-Trainer gefunden.",
    0x1F548AC: "Diese TM wurde im UG1 nach\ndem Schieben eines Felsens ins Loch gefunden.",
    0x1F548EA: "Diese TM wurde im 4F gekauft.",
    0x1F54907: "Diese TM wurde für\n2000 Münzen gekauft.",
    0x1F5492D: "Diese TM wurde auf dem\nMarktplatz gekauft.",
    0x1F54957: "Ein Clown gab dir diese TM,\nnachdem du ihn im Versteck fandest.",
    0x1F54993: "Diese TM wurde mit Zerschneider\nnahe dem Ausgang zur Cube Corp. gefunden.",
    0x1F549D1: "Diese TM wurde für 16 GP\nim Laden gekauft.",
    0x1F54A00: "Diese TM wurde im UG1 nach\ndem mühsamen Überqueren des\nrissigen Bodens gefunden.",
    0x1F54A51: "Diese TM wurde unter einer\nBaumkrone im südlichen Teil der\nöstlichen Routenhälfte gefunden.",
    0x1F54AAC: "Diese TM wurde nach dem Auftauchen\nmit dem ADM gefunden.",
    0x1F54ADE: "Diese TM wurde im EG nahe dem\nEingang von Epidimy Town mit\nSurfer gefunden.",
    0x1F54B25: "Diese TM wurde nahe dem Gipfel\nmit Kraxler gefunden.",
    # Textes de combat et titre de mission qui contenait du français.
    0x1F9703A: "Huah!<0xFB>Bei <0xFC><0x01><0x06><0xFD><0x02><0xFC><0x01><0x08> kann ich den <0xFC><0x01><0x06><0xFD><0x03><0xFC><0x01><0x08>-Wert\num <0xFC><0x01><0x06><0xFD><0x04><0xFC><0x01><0x08> Punkte erhöhen!<0xFB>Soll ich das tun?",
    0x1F970D7: "Huah!<0xFB>Ich habe bei <0xFC><0x01><0x06><0xFD><0x02><0xFC><0x01><0x08> den <0xFC><0x01><0x06><0xFD><0x03><0xFC><0x01><0x08>-Wert\nauf <0xFC><0x01><0x06><0xFD><0x04><0xFC><0x01><0x08> FP erhöht!<0xFB>Gern geschehen!",
    0x1F9712F: "Huah!<0xFB>Ich habe bei <0xFC><0x01><0x06><0xFD><0x02><0xFC><0x01><0x08> den <0xFC><0x01><0x06><0xFD><0x03><0xFC><0x01><0x08>-Wert\nauf <0xFC><0x01><0x06>null<0xFC><0x01><0x08> FP gesenkt!<0xFB>Gern geschehen!",
    0x1FA64DC: "Nicht gesehene Herde",
}
EXPECTED = {offset: value.replace("\n", r"\n") for offset, value in EXPECTED.items()}


def _last_wins() -> dict[int, str]:
    result: dict[int, str] = {}
    pattern = re.compile(r"^0x([0-9A-Fa-f]+):\s?(.*)$")
    for line in COMBINED_DE.read_text(encoding="utf-8").splitlines():
        if match := pattern.match(line):
            result[int(match.group(1), 16)] = match.group(2)
    return result


def _english_raw() -> dict[int, bytes]:
    payload = json.loads(ENGLISH_TEXTS.read_text(encoding="utf-8"))
    entries = payload.get("texts", payload)
    return {
        int(entry["offset"]): bytes.fromhex(entry["raw_bytes"])
        for entry in entries
        if int(entry.get("offset", -1)) in EXPECTED
    }


def _controls(raw: bytes) -> list[bytes]:
    return [bytes(sequence) for sequence in Builder._extract_control_sequences_from_raw(raw)]


def _encode_combined(value: str) -> bytes:
    return TextEncoder.encode_pokemon(
        value.replace(r"\n", "<0xFE>"), skip_aliases=GERMAN_UMLAUT_CHARS
    )


def _without_layout(raw: bytes) -> str:
    if raw.endswith(b"\xFF"):
        raw = raw[:-1]
    text = TextDecoder.decode_pokemon(raw, preserve_unknown=True)
    return re.sub(r" +", " ", text.replace("\n", " ").replace("<0xFA>", " ")).strip()


def test_f601_batches_are_exact_last_wins_values() -> None:
    current = _last_wins()
    assert {offset: current.get(offset) for offset in EXPECTED} == EXPECTED


def test_f601_batches_preserve_control_order_and_arity() -> None:
    sources = _english_raw()
    assert set(sources) == set(EXPECTED)
    for offset, expected in EXPECTED.items():
        assert _controls(_encode_combined(expected)) == _controls(sources[offset]), (
            f"0x{offset:X}: séquences de contrôle différentes"
        )


@pytest.mark.rom
def test_f601_batches_are_decoded_from_live_de_pointers() -> None:
    if not BUILT_DE_ROM.exists():
        pytest.skip("GenedRom-de.gba non construite")

    english_rom = ENGLISH_ROM.read_bytes()
    german_rom = BUILT_DE_ROM.read_bytes()
    payload = json.loads(ENGLISH_TEXTS.read_text(encoding="utf-8"))
    entries = payload.get("texts", payload)
    by_offset = {
        int(entry["offset"]): entry
        for entry in entries
        if int(entry.get("offset", -1)) in EXPECTED
    }

    for offset, expected in EXPECTED.items():
        raw_sites = by_offset[offset].get("pointer_offsets") or []
        if not isinstance(raw_sites, list):
            raw_sites = [raw_sites]
        sites = plausible_sites(
            english_rom,
            offset,
            [int(site, 0) if isinstance(site, str) else int(site) for site in raw_sites],
        )
        wanted = _without_layout(_encode_combined(expected))
        delivered = []
        for site in sites:
            target = live_target(german_rom, site)
            if target is None:
                continue
            end = german_rom.find(b"\xFF", target, min(len(german_rom), target + 0x1000))
            if end < 0:
                continue
            decoded = _without_layout(german_rom[target : end + 1])
            if decoded == wanted:
                delivered.append((site, target))

        assert delivered, f"0x{offset:X}: aucune valeur allemande au pointeur vivant"
