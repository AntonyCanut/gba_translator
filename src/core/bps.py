"""Création et vérification de patchs BPS1 déterministes."""

from __future__ import annotations

import zlib
from dataclasses import dataclass

BPS_MAGIC = b"BPS1"
SOURCE_READ = 0
TARGET_READ = 1
FOOTER_SIZE = 12


class BpsError(ValueError):
    """Signale un patch BPS invalide ou incompatible avec sa ROM source."""


@dataclass(frozen=True)
class BpsPatchInfo:
    """Métadonnées vérifiées d'un patch BPS, lisibles sans sa source."""

    source_size: int
    target_size: int
    source_crc32: str
    target_crc32: str
    patch_crc32: str


def _encode_number(value: int) -> bytes:
    if value < 0:
        raise BpsError("un entier BPS ne peut pas être négatif")
    encoded = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value == 0:
            encoded.append(byte | 0x80)
            return bytes(encoded)
        encoded.append(byte)
        value -= 1


def _decode_number(data: bytes, cursor: int, limit: int) -> tuple[int, int]:
    value = 0
    shift = 1
    while cursor < limit:
        byte = data[cursor]
        cursor += 1
        value += (byte & 0x7F) * shift
        if byte & 0x80:
            return value, cursor
        shift <<= 7
        value += shift
    raise BpsError("entier BPS tronqué")


def _emit_action(patch: bytearray, action: int, length: int) -> None:
    if length > 0:
        patch.extend(_encode_number(((length - 1) << 2) | action))


def create_bps_patch(source: bytes, target: bytes) -> bytes:
    """Crée un patch BPS1 déterministe entre deux images binaires.

    Le flux volontairement simple alterne ``SourceRead`` et ``TargetRead``.
    Il compresse efficacement une ROM traduite, dont la majorité des octets
    reste identique à la source, sans dépendance externe.

    Args:
        source: Image ROM source attendue par le patch.
        target: Image ROM construite à reproduire.

    Returns:
        Patch BPS1 complet avec les trois CRC32 réglementaires.
    """
    patch = bytearray(BPS_MAGIC)
    patch.extend(_encode_number(len(source)))
    patch.extend(_encode_number(len(target)))
    patch.extend(_encode_number(0))

    offset = 0
    while offset < len(target):
        source_match = offset < len(source) and source[offset] == target[offset]
        end = offset + 1
        if source_match:
            while (
                end < len(target)
                and end < len(source)
                and source[end] == target[end]
            ):
                end += 1
            _emit_action(patch, SOURCE_READ, end - offset)
        else:
            while end < len(target) and (
                end >= len(source) or source[end] != target[end]
            ):
                end += 1
            _emit_action(patch, TARGET_READ, end - offset)
            patch.extend(target[offset:end])
        offset = end

    patch.extend(zlib.crc32(source).to_bytes(4, "little"))
    patch.extend(zlib.crc32(target).to_bytes(4, "little"))
    patch.extend(zlib.crc32(patch).to_bytes(4, "little"))
    return bytes(patch)


def inspect_bps_patch(patch: bytes) -> BpsPatchInfo:
    """Valide la structure d'un BPS et retourne son contrat source/cible.

    Cette inspection ne reconstruit pas la cible et ne nécessite donc aucune
    ROM. Elle contrôle le CRC du patch, les tailles, les actions prises en
    charge et l'absence de données superflues.

    Args:
        patch: Contenu complet du fichier BPS1.

    Returns:
        Tailles et CRC32 déclarés par le patch validé.

    Raises:
        BpsError: Si le patch est corrompu, tronqué ou non pris en charge.
    """
    if len(patch) < len(BPS_MAGIC) + 3 + FOOTER_SIZE or not patch.startswith(BPS_MAGIC):
        raise BpsError("en-tête BPS1 invalide")
    expected_patch_crc = int.from_bytes(patch[-4:], "little")
    if zlib.crc32(patch[:-4]) != expected_patch_crc:
        raise BpsError("CRC du patch invalide")

    footer_start = len(patch) - FOOTER_SIZE
    cursor = len(BPS_MAGIC)
    source_size, cursor = _decode_number(patch, cursor, footer_start)
    target_size, cursor = _decode_number(patch, cursor, footer_start)
    metadata_size, cursor = _decode_number(patch, cursor, footer_start)
    cursor += metadata_size
    if cursor > footer_start:
        raise BpsError("métadonnées BPS tronquées")

    target_offset = 0
    while target_offset < target_size:
        action_value, cursor = _decode_number(patch, cursor, footer_start)
        action = action_value & 3
        length = (action_value >> 2) + 1
        if target_offset + length > target_size:
            raise BpsError("action BPS au-delà de la taille cible")
        if action == SOURCE_READ:
            if target_offset + length > source_size:
                raise BpsError("lecture BPS au-delà de la source")
        elif action == TARGET_READ:
            cursor += length
            if cursor > footer_start:
                raise BpsError("payload BPS tronqué")
        else:
            raise BpsError("action BPS de copie relative non prise en charge")
        target_offset += length

    if cursor != footer_start:
        raise BpsError("données superflues avant le pied BPS")
    return BpsPatchInfo(
        source_size=source_size,
        target_size=target_size,
        source_crc32=f"{int.from_bytes(patch[-12:-8], 'little'):08x}",
        target_crc32=f"{int.from_bytes(patch[-8:-4], 'little'):08x}",
        patch_crc32=f"{expected_patch_crc:08x}",
    )


def apply_bps_patch(source: bytes, patch: bytes) -> bytes:
    """Réapplique un patch produit par :func:`create_bps_patch`.

    Ce vérificateur interne accepte uniquement les actions ``SourceRead`` et
    ``TargetRead`` émises par notre encodeur. Ce n'est pas un applicateur BPS
    générique pour les patchs tiers utilisant les copies relatives.

    Args:
        source: Image ROM source à vérifier puis transformer.
        patch: Contenu BPS1 à appliquer.

    Returns:
        Image cible reconstruite.

    Raises:
        BpsError: Si le patch est corrompu, tronqué, non pris en charge ou si
            la source n'est pas exactement celle attendue.
    """
    info = inspect_bps_patch(patch)

    footer_start = len(patch) - FOOTER_SIZE
    cursor = len(BPS_MAGIC)
    source_size, cursor = _decode_number(patch, cursor, footer_start)
    target_size, cursor = _decode_number(patch, cursor, footer_start)
    metadata_size, cursor = _decode_number(patch, cursor, footer_start)
    cursor += metadata_size
    if cursor > footer_start:
        raise BpsError("métadonnées BPS tronquées")
    if source_size != info.source_size or target_size != info.target_size:
        raise BpsError("en-tête BPS incohérent")
    if len(source) != source_size:
        raise BpsError("taille de la source incompatible")
    expected_source_crc = int.from_bytes(patch[-12:-8], "little")
    if zlib.crc32(source) != expected_source_crc:
        raise BpsError("CRC de la source incompatible")

    target = bytearray()
    while len(target) < target_size:
        action_value, cursor = _decode_number(patch, cursor, footer_start)
        action = action_value & 3
        length = (action_value >> 2) + 1
        if len(target) + length > target_size:
            raise BpsError("action BPS au-delà de la taille cible")
        if action == SOURCE_READ:
            start = len(target)
            end = start + length
            if end > len(source):
                raise BpsError("lecture BPS au-delà de la source")
            target.extend(source[start:end])
        elif action == TARGET_READ:
            end = cursor + length
            if end > footer_start:
                raise BpsError("payload BPS tronqué")
            target.extend(patch[cursor:end])
            cursor = end
        else:
            raise BpsError("action BPS de copie relative non prise en charge")

    if cursor != footer_start:
        raise BpsError("données superflues avant le pied BPS")
    expected_target_crc = int.from_bytes(patch[-8:-4], "little")
    if zlib.crc32(target) != expected_target_crc:
        raise BpsError("CRC de la cible invalide")
    return bytes(target)
