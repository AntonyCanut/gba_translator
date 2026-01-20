#!/usr/bin/env python3
"""
ROM Reader - Lecture et manipulation de ROMs GBA

Fournit une interface orientée objet pour lire et manipuler des ROMs Game Boy Advance.
"""

import struct
import shutil
from pathlib import Path
from typing import Optional


class ROMError(Exception):
    """Erreur liée à la manipulation ROM."""
    pass


class ROMReader:
    """
    Lecteur/écriv

eur de ROM GBA.

    Gère la lecture, l'écriture et la manipulation de fichiers ROM GBA
    avec validation des pointeurs et gestion de la mémoire.

    Attributes:
        GBA_ROM_BASE (int): Adresse de base ROM GBA (0x08000000)
        rom_path (Path): Chemin vers le fichier ROM
        rom_data (bytearray): Données ROM en mémoire
        rom_size (int): Taille de la ROM en bytes
    """

    GBA_ROM_BASE = 0x08000000

    def __init__(self, rom_path: str):
        """
        Initialise le lecteur ROM.

        Args:
            rom_path: Chemin vers le fichier ROM (.gba)
        """
        self.rom_path = Path(rom_path)
        self.rom_data = None
        self.rom_size = 0
        self._modified = False

    def load(self) -> None:
        """
        Charge la ROM en mémoire.

        Raises:
            FileNotFoundError: Si le fichier ROM n'existe pas
            ROMError: Si la ROM est invalide
        """
        if not self.rom_path.exists():
            raise FileNotFoundError(f"ROM not found: {self.rom_path}")

        with open(self.rom_path, 'rb') as f:
            self.rom_data = bytearray(f.read())

        self.rom_size = len(self.rom_data)

        if self.rom_size == 0:
            raise ROMError("ROM file is empty")

        # Vérification basique (taille minimum GBA ROM = 16 MB)
        if self.rom_size < 16 * 1024 * 1024:
            raise ROMError(f"ROM too small: {self.rom_size} bytes")

    def read_bytes(self, offset: int, length: int) -> bytes:
        """
        Lit des bytes à un offset donné.

        Args:
            offset: Offset dans la ROM
            length: Nombre de bytes à lire

        Returns:
            bytes: Données lues

        Raises:
            ROMError: Si la ROM n'est pas chargée
            ValueError: Si offset invalide
        """
        if self.rom_data is None:
            raise ROMError("ROM not loaded. Call load() first.")

        if offset < 0 or offset >= self.rom_size:
            raise ValueError(f"Invalid offset: {offset} (ROM size: {self.rom_size})")

        if offset + length > self.rom_size:
            raise ValueError(f"Read beyond ROM size: {offset}+{length} > {self.rom_size}")

        return bytes(self.rom_data[offset:offset+length])

    def read_pointer(self, offset: int) -> Optional[int]:
        """
        Lit un pointeur 32-bit little-endian à un offset donné.

        Args:
            offset: Offset du pointeur dans la ROM

        Returns:
            int ou None: Offset ROM si pointeur valide, None sinon

        Raises:
            ROMError: Si la ROM n'est pas chargée
        """
        if self.rom_data is None:
            raise ROMError("ROM not loaded. Call load() first.")

        if offset + 4 > self.rom_size:
            return None

        ptr_value = struct.unpack('<I', self.rom_data[offset:offset+4])[0]

        if self.is_valid_pointer(ptr_value):
            return ptr_value - self.GBA_ROM_BASE
        return None

    def is_valid_pointer(self, ptr_value: int) -> bool:
        """
        Vérifie si une valeur est un pointeur ROM GBA valide.

        Un pointeur valide est dans la plage 0x08000000-0x09FFFFFF
        et pointe dans la ROM.

        Args:
            ptr_value: Valeur 32-bit à vérifier

        Returns:
            bool: True si pointeur valide
        """
        if not (0x08000000 <= ptr_value < 0x0A000000):
            return False

        rom_offset = ptr_value - self.GBA_ROM_BASE
        return 0 <= rom_offset < self.rom_size

    def write_bytes(self, offset: int, data: bytes) -> None:
        """
        Écrit des bytes à un offset donné.

        Args:
            offset: Offset d'écriture
            data: Données à écrire

        Raises:
            ROMError: Si la ROM n'est pas chargée
            ValueError: Si écriture hors limites
        """
        if self.rom_data is None:
            raise ROMError("ROM not loaded. Call load() first.")

        if offset < 0 or offset >= self.rom_size:
            raise ValueError(f"Invalid offset: {offset}")

        if offset + len(data) > self.rom_size:
            raise ValueError(f"Write beyond ROM size: {offset}+{len(data)} > {self.rom_size}")

        self.rom_data[offset:offset+len(data)] = data
        self._modified = True

    def save(self, output_path: str, create_backup: bool = True) -> None:
        """
        Sauvegarde la ROM.

        Args:
            output_path: Chemin de sortie
            create_backup: Créer un backup (.bak) si fichier existe

        Raises:
            ROMError: Si la ROM n'est pas chargée
        """
        if self.rom_data is None:
            raise ROMError("ROM not loaded. Call load() first.")

        output_path = Path(output_path)

        # Créer backup si demandé
        if output_path.exists() and create_backup:
            backup_path = Path(str(output_path) + '.bak')
            shutil.copy2(output_path, backup_path)

        # Sauvegarder
        with open(output_path, 'wb') as f:
            f.write(self.rom_data)

        self._modified = False

    def is_modified(self) -> bool:
        """Vérifie si la ROM a été modifiée."""
        return self._modified

    def get_rom_info(self) -> dict:
        """
        Récupère les informations de base de la ROM.

        Returns:
            dict: Informations ROM (titre, code, taille)

        Raises:
            ROMError: Si la ROM n'est pas chargée
        """
        if self.rom_data is None:
            raise ROMError("ROM not loaded. Call load() first.")

        # Header GBA à 0xA0
        title = self.rom_data[0xA0:0xAC].decode('ascii', errors='ignore').strip('\x00')
        game_code = self.rom_data[0xAC:0xB0].decode('ascii', errors='ignore')
        maker_code = self.rom_data[0xB0:0xB2].decode('ascii', errors='ignore')

        return {
            'title': title,
            'game_code': game_code,
            'maker_code': maker_code,
            'size': self.rom_size,
            'size_mb': self.rom_size // (1024 * 1024)
        }

    def __repr__(self) -> str:
        status = "loaded" if self.rom_data is not None else "not loaded"
        modified = " (modified)" if self._modified else ""
        return f"ROMReader({self.rom_path.name}, {status}{modified})"
