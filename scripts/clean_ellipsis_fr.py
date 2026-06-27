#!/usr/bin/env python3
"""Nettoie les points de suspension surutilisés dans combined_fr.txt.

Contexte (demande utilisateur) :
  - Le jeu rend un caractère spécial « … » (ellipsis) qui économise 2 octets
    par rapport à trois points ASCII « ... ».
  - Les « ... » sont parfois utilisés à outrance / placés n'importe comment
    (rangées de points « … … … … », « ……… ……… ……… », doublons « …… »)
    et ne servent pas le dialogue.

Politique (sûre — ne fait QUE raccourcir les chaînes, donc jamais de
débordement de pointeur ; ne supprime jamais une ellipsis isolée qui sert le
dialogue) :
  T1  Trois points ASCII (3+) « ... » -> « … » (réalise l'économie de 2 octets).
  T2  Toute SUITE de 2 ellipses ou plus, séparées uniquement par des espaces
      (« …… », « … … », « ……… », « … … … … ») -> une seule « … ».
      (Garde une pause/beat unique, supprime le spam de points.)
  T3  Espace(s) entre le MOT d'avant et « … » quand AUCUN mot n'est collé
      après l'ellipsis (« Non … » -> « Non… », « vu … rien » -> « vu… rien »)
      -> on colle l'ellipsis au mot précédent.
      Cas conservés : un mot collé APRÈS (« vu …rien » = ellipsis de tête ->
      l'espace d'avant reste) et une ponctuation ouvrante / tiret de dialogue
      avant l'espace (« « … », « — … ») dont l'espace est typographique.

NE TOUCHE PAS :
  - une ellipsis isolée « … » (hésitation, fin en suspens — sert le dialogue) ;
  - les beats de pause sur des pages séparées « …\\p… » (rythme volontaire) ;
  - les codes de contrôle ({...}, \\n \\p \\l) — aucun ne contient de points.

Insertion chirurgicale : seules les lignes contenant des points de suspension
sont modifiées ; tout le reste (offsets, formatage, fins de ligne LF) est
préservé octet pour octet.
"""
import argparse
import re
import sys

# Suite d'ellipses (… ou ... déjà normalisés) séparées par des espaces.
RUN = re.compile(r'…(?:[ \t]*…)+')
# 3 points ASCII ou plus.
ASCII_DOTS = re.compile(r'\.{3,}')
# Caractères qui, juste avant l'espace, FONT GARDER l'espace : ponctuation
# ouvrante, guillemets, apostrophes, tirets de dialogue (l'espace y est
# typographique, pas un « mot d'avant »).
_KEEP_BEFORE = '«("“‘\'’[{¿¡—–-…'
# T3 : espace(s) entre un mot et « … » lorsqu'aucun mot n'est collé après
# l'ellipsis (lookahead négatif `\w`). Le motif EXIGE un vrai caractère de
# contenu avant l'espace (groupe 1) — il n'agit donc jamais sur l'espace de
# format en tête d'entrée ni après une ponctuation ouvrante.
SPACE_BEFORE = re.compile(
    r'([^\s' + re.escape(_KEEP_BEFORE) + r'])[ \t]+…(?!\w)')


def clean_body(body: str) -> str:
    # T1 : ASCII -> caractère ellipsis (économie 2 octets/occurrence).
    body = ASCII_DOTS.sub('…', body)
    # T2 : suite de 2+ ellipses -> une seule.
    body = RUN.sub('…', body)
    # T3 : colle « … » au mot précédent si aucun mot n'est collé après.
    body = SPACE_BEFORE.sub(r'\1…', body)
    return body


def transform_line(line: str) -> str:
    # Protège le préfixe « 0xOFFSET: » (sans points/ellipses de toute façon).
    idx = line.find(':')
    if idx < 0:
        return clean_body(line)
    prefix, body = line[:idx + 1], line[idx + 1:]
    return prefix + clean_body(body)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('path', nargs='?', default="languages/fr/combined_fr.txt")
    ap.add_argument('--apply', action='store_true',
                    help='écrit les modifications (sinon dry-run + diff)')
    ap.add_argument('--max-show', type=int, default=0,
                    help='nb max d\'entrées modifiées à afficher (0 = toutes)')
    args = ap.parse_args()

    with open(args.path, encoding='utf-8') as fh:
        lines = fh.read().split('\n')

    changed = []
    for i, line in enumerate(lines):
        if '...' not in line and '…' not in line:
            continue
        new = transform_line(line)
        if new != line:
            changed.append((i, line, new))
            lines[i] = new

    print(f'Entrées modifiées : {len(changed)}')
    shown = changed if args.max_show == 0 else changed[:args.max_show]
    for i, old, new in shown:
        off = old.split(':', 1)[0]
        print(f'\n--- {off} (ligne {i + 1})')
        print(f'  AVANT: {old[:200]}')
        print(f'  APRÈS: {new[:200]}')

    if args.apply:
        with open(args.path, 'w', encoding='utf-8') as fh:
            fh.write('\n'.join(lines))
        print(f'\nÉcrit {args.path} ({len(changed)} entrées nettoyées).')
    else:
        print('\n[dry-run] Relancer avec --apply pour écrire.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
