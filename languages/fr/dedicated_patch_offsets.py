"""Offsets FR appartenant exclusivement aux patchs post-build dédiés.

Les générateurs CSV/JSON doivent laisser ces cellules intactes. Le passe inline
possède un sous-ensemble distinct : les panneaux de carte ont leur propre flux
historique, tandis que le titre de mission doit impérativement être ignoré.
Les tests synchronisent ces constantes avec les ``TARGETS`` des patchs.
"""

MISSION_TITLE_OFFSETS = frozenset({0x1FA4E10})

WORLD_MAP_JUNCTION_OFFSETS = frozenset({
    0x1F70E41,
    0x1F72353,
    0x1F72691,
    0x1F726C0,
    0x1F726FC,
    0x1F72735,
    0x1F7276E,
    0x1F727A7,
    0x1F727D0,
    0x1F72808,
})

GENERIC_TRANSLATION_OFFSETS = (
    MISSION_TITLE_OFFSETS | WORLD_MAP_JUNCTION_OFFSETS
)
INLINE_OVERRIDE_OFFSETS = MISSION_TITLE_OFFSETS
