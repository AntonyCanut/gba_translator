---
name: unbound-gender-buffer-exhaustive-sweep
description: "Traque exhaustive des buffers pronom genré : tracer les pointeurs vers les 2 tables de pronoms (0x789224, 0x1FA764E) → 15 sites bufferstring → 4 clusters de scripts ; textes à ±2-4 Ko des sites"
metadata:
  node_type: memory
  type: project
  originSessionId: 64aaaf73-a7de-4c0f-a4ea-0b243a790741
---

Pour trouver TOUTES les répliques utilisant un buffer pronom genré (ticket « Suppression
genre », 2026-07-02) : ne PAS filtrer les ~1200 strings EN à FD02/03/04 (noms de
Pokémon/objets/nombres = faux positifs massifs). Méthode fiable qui borne l'ensemble :

1. Deux tables de pronoms EN : `0x789224` (him/he/He/her/she/She) et `0x1FA764E`
   (him/her/his). En ROM FR elles rendent le/il/Il/la.
2. Scanner la ROM EN pour les pointeurs 32-bit LE `0x08000000+addr` vers ces 6+3 chaînes
   → **15 sites** `bufferstring` (opcode `85 <buf_idx>` juste avant le pointeur),
   groupés en **4 clusters de scripts** (0x7522AD Aros, 0x7BD1A9 goons Dresco,
   0x1E709F5 NG+/Lucario, 0x1EAB917 gentleman immobilier + Granbull).
3. Les dialogues genrés = pointeurs texte à ±2-4 Ko des sites dont l'EN contient
   FD02/03/04. La scène Hoopa (0x1F2CC7E/0x1F2CDA7) échappe au scan par proximité
   (script hors fenêtre) — compléter par les captures utilisateur / scan du cluster.
4. PIÈGE : vérifier l'opcode qui remplit le buffer avant de neutraliser — `0x7D` =
   bufferpokemon (ex. 0x1FA5E48 « {FD:02} went flying » = nom d'espèce, PAS un pronom) ;
   « Only {FD:02} left » (0x7C0F3E) = nombre.

11 répliques neutralisées (recette 0 accolade → FD droppé, cf.
[[unbound-gender-pronoun-variable-removal]]) : 0x1F2CC7E « L'intrus est K.O. »,
0x1F2CDA7 datif neutre « ce que tu lui voulais », 0x7527C2/0x77F52F « enfant » (Aros),
0x753107, 0x78910F « C'est sans doute une victime », 0x7BCA5F « C'est toi qui »,
0x1FA6F85 « ce môme »/« Vous l'avez sous-estimé », 0x1FA7D3B/0x1FA804E/0x1FA8CA1
« jeune personne ». Test source-level : `tests/test_gender_neutral_hoopa_estate_fr.py`.
Usages grammaticaux laissés (sujets il/elle, clitiques le/la : 0x1FA6CB5).

Piège annexe : `verify_user_rom_givecs.py` comparait le struct objet 44 o byte-exact à
l'EN → rouge permanent depuis la traduction des cellules nom (« TM »→« CT ») ; fixé en
excluant name[14] mais en exigeant le 0xFF.
