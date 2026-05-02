#!/usr/bin/env python
"""
Tag back-references pour une fiche couche déjà produite.

Utilité : rattrapper l'étape 8 de `synthesize-couche` quand elle a été oubliée
(ou en garde-fou systématique). Lit la section "Vidéos" d'une fiche couche
(Methodes/Conjonctures/Possibles/Enjeux) et ajoute son nom au frontmatter
des fiches Vidéos qu'elle référence — champ pluriel `methodes:` /
`conjonctures:` / `possibles:` / `enjeux:`.

Idempotent : ne fait rien si la valeur est déjà présente.

Usage:
    python tag_back_references.py --fiche Sources/Paduteam/Methodes/Graphique.md
    python tag_back_references.py --fiche ... --dry-run
"""
import sys
import os
import re
from pathlib import Path

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Section titles supportés (case-sensitive, sans accents non plus)
SECTION_PATTERNS = [
    r'^## Vidéos où elle est mobilisée\b',
    r'^## Vidéos clés\b',
    r'^## Vidéos où le concept est développé\b',
    r'^## Vidéos par usage\b',
    r'^## Vidéos\b',
]

# couche-singulier → champ-pluriel attendu sur les fiches Vidéos
COUCHE_TO_FIELD = {
    'methode': 'methodes',
    'conjoncture': 'conjonctures',
    'possible': 'possibles',
    'enjeu': 'enjeux',
}

WIKILINK_RE = re.compile(r'\[\[([^|\]\n]+)(?:\|[^\]]*)?\]\]')
FRONTMATTER_RE = re.compile(r'\A---\s*\n(.*?)\n---\s*\n', re.DOTALL)


def parse_fiche_metadata(fiche_path: Path) -> tuple[str, str]:
    """Retourne (target_couche, target_name) extraits du frontmatter de la fiche couche."""
    text = fiche_path.read_text(encoding='utf-8')
    m = FRONTMATTER_RE.match(text)
    if not m:
        sys.exit(f"ERREUR : pas de frontmatter dans {fiche_path}")
    fm = m.group(1)
    type_m = re.search(r'^type:\s*(\S+)', fm, re.MULTILINE)
    if not type_m:
        sys.exit(f"ERREUR : pas de champ 'type' dans le frontmatter de {fiche_path}")
    target_couche = type_m.group(1).strip()
    target_name = fiche_path.stem
    return target_couche, target_name


def extract_videos_from_fiche(fiche_path: Path, vault_root: Path) -> list[str]:
    """Liste ordonnée des fiches Vidéos référencées dans la section 'Vidéos…'."""
    text = fiche_path.read_text(encoding='utf-8')
    lines = text.splitlines()
    in_section = False
    videos: list[str] = []
    seen: set[str] = set()
    for line in lines:
        if any(re.match(p, line) for p in SECTION_PATTERNS):
            in_section = True
            continue
        if in_section and line.startswith('## '):
            break
        if not in_section:
            continue
        for wm in WIKILINK_RE.finditer(line):
            name = wm.group(1).strip()
            if name in seen:
                continue
            video_path = vault_root / 'Videos' / f'{name}.md'
            if video_path.exists():
                seen.add(name)
                videos.append(name)
    return videos


def update_video_frontmatter(video_path: Path, field: str, value: str,
                             dry_run: bool = False) -> str:
    """Ajoute `value` à `field` dans le frontmatter. Retourne 'added' / 'skipped' / 'error'."""
    text = video_path.read_text(encoding='utf-8')
    m = FRONTMATTER_RE.match(text)
    if not m:
        return 'error:no-frontmatter'
    fm = m.group(1)

    # Cas 1 : champ inline `field: [a, b]`
    inline_re = re.compile(rf'^({re.escape(field)}):\s*\[(.*?)\]\s*$', re.MULTILINE)
    inline_m = inline_re.search(fm)
    if inline_m:
        existing = [v.strip() for v in inline_m.group(2).split(',') if v.strip()]
        if value in existing:
            return 'skipped'
        new_list = existing + [value]
        new_line = f'{field}: [{", ".join(new_list)}]'
        new_fm = fm[:inline_m.start()] + new_line + fm[inline_m.end():]
        if not dry_run:
            video_path.write_text(text.replace(fm, new_fm, 1), encoding='utf-8')
        return 'added'

    # Cas 2 : champ multiline `field:\n  - a\n  - b`
    multiline_re = re.compile(
        rf'^({re.escape(field)}):\s*\n((?:[ \t]+- [^\n]+\n)+)',
        re.MULTILINE,
    )
    multiline_m = multiline_re.search(fm + '\n')  # +'\n' pour matcher si dernière ligne
    if multiline_m:
        block = multiline_m.group(2)
        existing = [
            l.strip().lstrip('-').strip()
            for l in block.splitlines() if l.strip()
        ]
        if value in existing:
            return 'skipped'
        # Préserve l'indentation du bloc existant
        first_item_line = block.splitlines()[0]
        indent = first_item_line[:len(first_item_line) - len(first_item_line.lstrip())]
        new_block = block + f'{indent}- {value}\n'
        new_match = multiline_m.group(0).replace(block, new_block, 1)
        new_fm = fm.replace(multiline_m.group(0).rstrip('\n'), new_match.rstrip('\n'), 1)
        if not dry_run:
            video_path.write_text(text.replace(fm, new_fm, 1), encoding='utf-8')
        return 'added'

    # Cas 3 : champ absent → insérer après enjeux: ou thèmes:
    for anchor in ('enjeux', 'thèmes'):
        anchor_re = re.compile(rf'^({re.escape(anchor)}:[^\n]*)$', re.MULTILINE)
        anchor_m = anchor_re.search(fm)
        if anchor_m:
            new_fm = (
                fm[:anchor_m.end()]
                + f'\n{field}: [{value}]'
                + fm[anchor_m.end():]
            )
            if not dry_run:
                video_path.write_text(text.replace(fm, new_fm, 1), encoding='utf-8')
            return 'added'

    return 'error:no-anchor'


def parse_arg(args, flag, default=None):
    if flag not in args:
        return default
    i = args.index(flag)
    return args[i + 1] if i + 1 < len(args) else default


def main():
    args = sys.argv[1:]
    fiche_arg = parse_arg(args, '--fiche')
    if not fiche_arg:
        sys.exit("Usage: python tag_back_references.py --fiche <chemin> [--dry-run]")
    dry_run = '--dry-run' in args
    fiche_path = Path(fiche_arg).resolve()
    if not fiche_path.is_file():
        sys.exit(f"ERREUR : fiche introuvable : {fiche_path}")

    # Trouver la racine de la source (parent du dossier couche)
    vault_root = fiche_path.parent.parent  # Methodes/X.md → ../

    target_couche, target_name = parse_fiche_metadata(fiche_path)
    field = COUCHE_TO_FIELD.get(target_couche)
    if not field:
        sys.exit(f"ERREUR : type '{target_couche}' inconnu (attendu : {list(COUCHE_TO_FIELD)})")

    videos = extract_videos_from_fiche(fiche_path, vault_root)
    print(f"Fiche       : {fiche_path}")
    print(f"Couche      : {target_couche} → champ frontmatter '{field}'")
    print(f"Target name : {target_name}")
    print(f"Vidéos      : {len(videos)} référencées")
    if dry_run:
        print("Mode        : DRY RUN (aucune modification écrite)")
    print()

    counters = {'added': 0, 'skipped': 0, 'error': 0}
    for v in videos:
        video_path = vault_root / 'Videos' / f'{v}.md'
        result = update_video_frontmatter(video_path, field, target_name, dry_run=dry_run)
        if result == 'added':
            counters['added'] += 1
            print(f"  + {v}")
        elif result == 'skipped':
            counters['skipped'] += 1
            print(f"  = {v} (déjà tagué)")
        else:
            counters['error'] += 1
            print(f"  ! {v} ({result})")

    print()
    print(f"Résumé : {counters['added']} ajoutés, {counters['skipped']} déjà OK, "
          f"{counters['error']} erreurs")


if __name__ == '__main__':
    main()
