"""Offsets FR appartenant exclusivement aux patchs post-build dédiés.

Les générateurs CSV/JSON doivent laisser ces cellules intactes. Le passe inline
possède un sous-ensemble distinct : les panneaux de carte ont leur propre flux
historique, tandis que le titre de mission doit impérativement être ignoré.
Les tests synchronisent ces constantes avec les ``TARGETS`` des patchs.
"""

MISSION_TITLE_OFFSETS = frozenset({0x1FA4E10})

# Libellés PC conservés dans combined_fr.txt comme source canonique, puis
# relocalisés à des adresses fixes par pc_move_labels.py. Les trois valeurs déjà
# connues du générateur gardent leur ancienne empreinte pour ne pas décaler les
# chaînes suivantes ; le préfixe absent du CSV reste entièrement exclu.
GENERIC_PLACEHOLDER_TRANSLATIONS = {
    0x41858D: "Dépl Pokémon",
    0x41859A: "Dépl. objet",
    0x4185A5: "À plus !",
}
PC_LABEL_OFFSETS = frozenset({0x4186CD})

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
    MISSION_TITLE_OFFSETS | WORLD_MAP_JUNCTION_OFFSETS | PC_LABEL_OFFSETS
)
INLINE_OVERRIDE_OFFSETS = MISSION_TITLE_OFFSETS
