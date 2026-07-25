"""Tests de l'audit des chaînes anglaises atteignables dans une ROM traduite."""

from __future__ import annotations

import importlib
import importlib.util
import struct

from src.core.text_codec import TextEncoder

GBA_BASE = 0x08000000


def _module():
    spec = importlib.util.find_spec("src.core.live_english_audit")
    assert spec is not None, "le module d'audit des chaînes anglaises n'existe pas"
    return importlib.import_module("src.core.live_english_audit")


def _encoded(text: str) -> bytes:
    return TextEncoder.encode_pokemon(text)


def _roms(
    *,
    english_text: str = "This text is still English.",
    french_text: str | None = None,
    pointer_site: int = 0x40,
) -> tuple[bytes, bytes, bytes, list[dict[str, object]]]:
    english = bytearray(b"\xFF" * 0x800)
    french = bytearray(b"\xFF" * 0x800)
    spanish = bytearray(b"\xFF" * 0x800)
    source_offset = 0x200
    target_offset = 0x300

    english_raw = _encoded(english_text)
    french_raw = _encoded(french_text or english_text)
    english[source_offset : source_offset + len(english_raw)] = english_raw
    french[target_offset : target_offset + len(french_raw)] = french_raw
    spanish[source_offset : source_offset + len(english_raw)] = english_raw

    struct.pack_into("<I", english, pointer_site, GBA_BASE + source_offset)
    struct.pack_into("<I", french, pointer_site, GBA_BASE + target_offset)
    struct.pack_into("<I", spanish, pointer_site, GBA_BASE + source_offset)

    entries = [
        {
            "offset": source_offset,
            "decoded_text": english_text,
            "raw_bytes": english_raw.hex(),
            "pointer_offsets": [f"0x{pointer_site:08X}"],
        }
    ]
    return bytes(english), bytes(french), bytes(spanish), entries


def test_audit_follows_a_relocated_live_pointer():
    audit = _module()
    english, french, spanish, entries = _roms()

    findings = audit.find_live_english(english, french, spanish, entries)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.source_offset == 0x200
    assert finding.target_offset == 0x300
    assert finding.pointer_sites == (0x40,)
    assert finding.english_text == "This text is still English."
    assert finding.spanish_translated is False


def test_audit_ignores_dead_english_bytes_after_translation():
    audit = _module()
    english, french, spanish, entries = _roms(
        french_text="Ce texte est maintenant français."
    )

    findings = audit.find_live_english(english, french, spanish, entries)

    assert findings == []


def test_audit_rejects_an_unaligned_false_pointer():
    audit = _module()
    english, french, spanish, entries = _roms(pointer_site=0x42)

    findings = audit.find_live_english(english, french, spanish, entries)

    assert findings == []


def test_spanish_repointing_marks_player_delivered_content():
    audit = _module()
    english, french, spanish, entries = _roms()
    spanish = bytearray(spanish)
    spanish_target = 0x400
    spanish_raw = _encoded("Este texto sí se tradujo.")
    spanish[spanish_target : spanish_target + len(spanish_raw)] = spanish_raw
    struct.pack_into("<I", spanish, 0x40, GBA_BASE + spanish_target)

    findings = audit.find_live_english(english, french, bytes(spanish), entries)

    assert len(findings) == 1
    assert findings[0].spanish_translated is True


def test_exception_requires_the_exact_offset_and_text():
    audit = _module()
    english, french, spanish, entries = _roms()
    finding = audit.find_live_english(english, french, spanish, entries)[0]
    exception = audit.EnglishException(
        source_offset=0x200,
        category="base-unused",
        english_text="Another string.",
        reason="Donnée FireRed inutilisée.",
    )

    result = audit.classify_findings([finding], [exception])

    assert result.base_unused == ()
    assert result.intentional == ()
    assert result.delivered == ()
    assert result.unclassified == (finding,)
    assert result.stale_exceptions == (exception,)


def test_classification_separates_delivered_and_explicit_exceptions():
    audit = _module()
    english, french, spanish, entries = _roms()
    first = audit.find_live_english(english, french, spanish, entries)[0]
    delivered = audit.LiveEnglishFinding(
        source_offset=0x210,
        target_offset=0x310,
        pointer_sites=(0x44,),
        english_text="A shipped English sentence.",
        spanish_translated=True,
    )
    base_exception = audit.EnglishException(
        source_offset=0x200,
        category="base-unused",
        english_text=first.english_text,
        reason="Donnée FireRed inutilisée.",
    )

    result = audit.classify_findings([first, delivered], [base_exception])

    assert result.base_unused == (first,)
    assert result.delivered == (delivered,)
    assert result.intentional == ()
    assert result.unclassified == ()
    assert result.stale_exceptions == ()
