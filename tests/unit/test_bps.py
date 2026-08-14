"""Tests du codec BPS utilisé pour les releases sans ROM."""

from __future__ import annotations

import pytest

from src.core.bps import BpsError, apply_bps_patch, create_bps_patch


def test_create_bps_patch_matches_a_hand_checked_bps1_vector() -> None:
    """Une dérive de l'encodage BPS doit casser le vecteur de référence."""
    patch = create_bps_patch(b"abc", b"axc")

    assert patch.hex() == "4250533183838080817880c241243519bb098592c28fe3"


def test_created_patch_rebuilds_the_target_byte_for_byte() -> None:
    """Le patch doit reproduire une cible de taille différente sans perte."""
    source = b"HEADER" + bytes(range(64)) + b"TAIL"
    target = b"HEADER" + bytes(range(20)) + b"traduit" + bytes(range(20, 64))

    patch = create_bps_patch(source, target)

    assert apply_bps_patch(source, patch) == target
    assert create_bps_patch(source, target) == patch


def test_apply_bps_patch_rejects_the_wrong_source() -> None:
    """Une ROM source différente doit être refusée par son CRC BPS."""
    patch = create_bps_patch(b"source correcte", b"cible")

    with pytest.raises(BpsError, match="CRC de la source"):
        apply_bps_patch(b"source corracte", patch)


def test_apply_bps_patch_rejects_a_corrupted_patch() -> None:
    """Une corruption du payload ne doit jamais produire une ROM silencieuse."""
    patch = bytearray(create_bps_patch(b"source", b"target"))
    patch[8] ^= 0x01

    with pytest.raises(BpsError, match="CRC du patch"):
        apply_bps_patch(b"source", bytes(patch))
