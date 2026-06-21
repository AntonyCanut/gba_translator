#!/usr/bin/env python3
"""Translate the 'Black Emboar' / 'Black {PLAYER}' gang dialogue to French.

Black Emboar  -> Roitiflam Noir          (Emboar = Roitiflam #500, Noir postposed)
Black {PLAYER}-> {PLAYER} Noir           (gang renamed after the player)

Line/scroll breaks (\\n, \\l) inside a split gang name are preserved so the
text box wrapping is unchanged.  Page breaks (\\p) and the two runtime-gender
entries are hand-written (CUSTOM) because a naive swap would split the gang
name across two text boxes or leave an incoherent gendered pronoun.

Gender fix: 0x1F9DBD7 / 0x1FA13F5 reference the player through buffered
pronoun codes <0xFD><0x03>/<0xFD><0x02> ("as he/she did", "my boy/girl").
Those render incoherently in French, so -- exactly like the Spanish build --
we replace them with the player-name buffer <0xFD><0x01> (raw token, no brace,
so the positional placeholder pass leaves it alone) or with neutral wording.

Only the LAST occurrence of each offset is edited (combined_fr.txt last-wins).
0x23E7A1 (fixed-width Trainer-class cell) and 'Black Ferrothorn' are out of scope.
"""
import re
import sys
from pathlib import Path

PATH = Path(__file__).resolve().parents[1] / 'combined_fr.txt'
LINE_RE = re.compile(r'^\s*0x([0-9A-Fa-f]+)\s*:\s*(.*)$')
GANG = re.compile(r'Black(\\[nlp]| )(Emboar|\{PLAYER\})')

# Hand-written replacements (full body, after the "0x...: " prefix).
CUSTOM = {
    '1f9d8d9': r"Pas si mauvais, gamin…\nJe t'aime bien. Écoute\pça… À partir de\pmaintenant, notre nom de\ngang sera le\p{PLAYER} Noir ! Ouais ! On\nadopte ton nom viril !\pC'est un nom plus\nsauvage pour une équipe\pplus sauvage ! Le\n{PLAYER} Noir ! Gwa ha ha ha ! Génial !",
    '1f9de57': r"C'est une puissante moto que\ntous les membres des\p{PLAYER} Noir possèdent ! Tu peux\nappuyer sur {L_BUTTON} pour\lactiver le turbo, ou y aller\pcool en pédalant. Passe nous\nvoir si tu viens à Ville d'Antisis.\pOn t'accueillera à bras ouverts.",
    '1f9df34': r"Bienvenue chez les\p{PLAYER} Noir, gamin ! Passe nous\nvoir si tu viens à Ville d'Antisis.\pOn t'accueillera à bras ouverts.",
    '1f9e3fb': r"{COLOR}ËHé ! Qui t'a dit que\ntu pouvais passer par ici ?\pC'est le territoire du\pRoitiflam Noir ! Retourne d'où tu viens !",
    # --- runtime-gender entries: raw <0xFD><0x01> = player name, no braces ---
    '1f9dbd7': r"Laisse-moi te dire ! Personne ne\pm'a jamais autant démoli\nque <0xFD><0x01> ! J'ai même\prenommé le Roitiflam Noir en\n<0xFD><0x01> Noir, en son honneur !\pC'est l'heure d'un nouveau\pdépart. Les <0xFD><0x01> Noir et\nmoi, on s'installe à Ville d'Antisis ! J'ai entendu dire que\nl'ancien gang qui dirigeait\pl'endroit s'est fait chasser. Un\ntruc avec un Granbull Terrible,\pje sais plus… Cette ville est\nmûre pour être cueillie par les\p<0xFD><0x01> Noir ! Gwa ha ha ha !",
    '1fa13f5': r"<0xFD><0x01> ! Mon pote !\pTu le\psens ? On est\npresque prêts à tomber\pces Black Ferrothorns, tu vois ?\nMaintenant qu'ils n'ont plus leur\ldopant, ils tiendront pas face à\lnous, les <0xFD><0x01> Noir !",
}


def regex_translate(body: str) -> str:
    body = body.replace(r'Black\n{PLAYER}', r'{PLAYER}\nNoir')
    body = body.replace(r'Black\l{PLAYER}', r'{PLAYER}\lNoir')
    body = body.replace('Black {PLAYER}', '{PLAYER} Noir')
    body = body.replace(r'Black\nEmboar', r'Roitiflam\nNoir')
    body = body.replace(r'Black\lEmboar', r'Roitiflam\lNoir')
    body = body.replace('Black Emboar', 'Roitiflam Noir')
    return body


def main(apply: bool) -> int:
    raw = PATH.read_text(encoding='utf-8')
    lines = raw.split('\n')

    last_occ = {}
    for i, l in enumerate(lines):
        m = LINE_RE.match(l)
        if m:
            last_occ[m.group(1).lower().lstrip('0')] = i

    changed = 0
    problems = []
    for i, l in enumerate(lines):
        m = LINE_RE.match(l)
        if not m:
            continue
        off = m.group(1).lower().lstrip('0')
        body = m.group(2)
        if off == '23e7a1':
            continue
        if last_occ[off] != i:
            continue  # only the last occurrence wins
        if off in CUSTOM:
            new_body = CUSTOM[off]
        elif GANG.search(body):
            # count non-{COLOR} braces must be preserved (positional mapping)
            before = len(re.findall(r'\{(?!COLOR\})[^}]+\}', body))
            new_body = regex_translate(body)
            after = len(re.findall(r'\{(?!COLOR\})[^}]+\}', new_body))
            if before != after:
                problems.append(f"0x{off}: brace count {before}->{after}")
        else:
            continue
        if new_body == body:
            continue
        # safety: no residual 'Black' except 'Black Ferrothorn'
        residual = re.sub(r'Black(\\[nlp]| )?Ferrothorn', '', new_body)
        if 'Black' in residual:
            problems.append(f"0x{off}: residual 'Black' -> {residual[:80]}")
        prefix = l[:l.index(':') + 2]
        lines[i] = prefix + new_body
        changed += 1
        if not apply:
            print(f"--- 0x{off.upper()}")
            print(f"  - {body[:160]}")
            print(f"  + {new_body[:160]}")

    print(f"\n{'APPLIED' if apply else 'DRY-RUN'}: {changed} lines changed")
    if problems:
        print("PROBLEMS:")
        for p in problems:
            print("  ", p)
        return 2
    if apply:
        PATH.write_text('\n'.join(lines), encoding='utf-8')
    return 0


if __name__ == '__main__':
    sys.exit(main(apply='--apply' in sys.argv))
