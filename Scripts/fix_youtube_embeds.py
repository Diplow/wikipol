#!/usr/bin/env python
"""
Normalise les embeds YouTube dans les fiches Videos/ d'une source.

Le format canonique (cf. Skills/write-video/SKILL.md) est :

    ![TITRE](https://www.youtube.com/watch?v=YOUTUBE_ID)

placé juste après la ligne des hashtags, avant le `# Titre`. Cette syntaxe
fait afficher à Obsidian un lecteur YouTube embarqué.

Le script :
  - **convertit** le format legacy thumbnail-cliquable
    `[![…](https://img.youtube.com/vi/ID/0.jpg)](https://www.youtube.com/watch?v=ID)`
    vers le format lecteur canonique
  - **ajoute** l'embed canonique aux fiches qui ont `youtube_id` en frontmatter
    mais aucun embed dans le body
  - **ignore** les fiches sans `youtube_id` (consigne SKILL.md : ne pas inventer d'ID)
  - **ignore** la méta-doc `Videos/CLAUDE.md`

Idempotent : ne touche pas les fiches déjà au format canonique.

Usage :
    python Scripts/fix_youtube_embeds.py --source Sources/Paduteam --dry-run
    python Scripts/fix_youtube_embeds.py --source Sources/Paduteam
"""
import sys
import re
from pathlib import Path

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

FRONTMATTER_RE = re.compile(r'\A---\s*\n(.*?)\n---\s*\n', re.DOTALL)
YOUTUBE_ID_RE = re.compile(
    r'^youtube_id:\s*["\']?([A-Za-z0-9_-]{6,})["\']?\s*$',
    re.MULTILINE,
)
PLAYER_EMBED_RE = re.compile(
    r'^!\[([^\]]*)\]\(https://www\.youtube\.com/watch\?v=([A-Za-z0-9_-]+)[^)]*\)\s*$',
    re.MULTILINE,
)
THUMB_EMBED_RE = re.compile(
    r'^\[!\[([^\]]*)\]\(https://img\.youtube\.com/vi/[A-Za-z0-9_-]+/'
    r'(?:0|maxresdefault|hqdefault|mqdefault|sddefault)\.jpg\)\]'
    r'\(https://www\.youtube\.com/watch\?v=([A-Za-z0-9_-]+)\)\s*$',
    re.MULTILINE,
)
# Pour la déduplication : la ligne thumbnail à supprimer (avec son saut de ligne final)
THUMB_LINE_RE = re.compile(
    r'^\[!\[[^\]]*\]\(https://img\.youtube\.com/vi/[A-Za-z0-9_-]+/'
    r'(?:0|maxresdefault|hqdefault|mqdefault|sddefault)\.jpg\)\]'
    r'\(https://www\.youtube\.com/watch\?v=[A-Za-z0-9_-]+\)\s*\n+',
    re.MULTILINE,
)
H1_RE = re.compile(r'^#\s+([^\n#].*?)\s*$', re.MULTILINE)
HASHTAG_LINE_RE = re.compile(r'^#[A-Za-zÀ-ÿ][^\n]*$', re.MULTILINE)


def parse_arg(args, flag, default=None):
    if flag not in args:
        return default
    i = args.index(flag)
    return args[i + 1] if i + 1 < len(args) else default


def process_file(path: Path, dry_run: bool) -> str:
    """Renvoie un statut : ok / converted / added / no-id / no-h1 / no-frontmatter / meta."""
    if path.name == 'CLAUDE.md':
        return 'meta'

    text = path.read_text(encoding='utf-8')
    fm_m = FRONTMATTER_RE.match(text)
    if not fm_m:
        return 'no-frontmatter'

    fm = fm_m.group(1)
    id_m = YOUTUBE_ID_RE.search(fm)
    if not id_m:
        return 'no-id'
    youtube_id = id_m.group(1)

    body_start = fm_m.end()
    body = text[body_start:]

    # Cas A : embed canonique déjà présent
    if PLAYER_EMBED_RE.search(body):
        # Sous-cas A' : un thumbnail legacy en doublon traîne → le supprimer
        if THUMB_LINE_RE.search(body):
            new_body = THUMB_LINE_RE.sub('', body, count=1)
            if not dry_run:
                path.write_text(text[:body_start] + new_body, encoding='utf-8')
            return 'dedup'
        return 'ok'

    # Cas B : thumbnail legacy → convertir (préserve l'alt-text existant)
    thumb_m = THUMB_EMBED_RE.search(body)
    if thumb_m:
        alt_text = thumb_m.group(1)
        new_line = f'![{alt_text}](https://www.youtube.com/watch?v={youtube_id})'
        new_body = body[:thumb_m.start()] + new_line + body[thumb_m.end():]
        if not dry_run:
            path.write_text(text[:body_start] + new_body, encoding='utf-8')
        return 'converted'

    # Cas C : aucun embed → insérer juste avant le H1
    h1_m = H1_RE.search(body)
    if not h1_m:
        return 'no-h1'

    h1_title = h1_m.group(1).strip()
    insert_at = h1_m.start()
    # On veut : <hashtag line>\n\n![title](url)\n\n# H1
    # Le body actuel est en général : <hashtag line>\n\n# H1  ou  <hashtag line>\n# H1
    # On insère "![title](url)\n\n" juste avant le "# H1", en s'assurant qu'il y a
    # une ligne vide avant l'embed.
    before = body[:insert_at]
    embed = f'![{h1_title}](https://www.youtube.com/watch?v={youtube_id})\n\n'

    # Garantir une ligne vide entre les hashtags et l'embed.
    # `before` se termine probablement par "\n" (juste après le H1 \n) ou "\n\n".
    if before.endswith('\n\n'):
        new_body = before + embed + body[insert_at:]
    elif before.endswith('\n'):
        new_body = before + '\n' + embed + body[insert_at:]
    else:
        new_body = before + '\n\n' + embed + body[insert_at:]

    if not dry_run:
        path.write_text(text[:body_start] + new_body, encoding='utf-8')
    return 'added'


def main():
    args = sys.argv[1:]
    source = parse_arg(args, '--source')
    if not source:
        sys.exit("Usage: python fix_youtube_embeds.py --source <path-source> [--dry-run]")
    dry_run = '--dry-run' in args

    videos_dir = Path(source) / 'Videos'
    if not videos_dir.is_dir():
        sys.exit(f"ERREUR : dossier introuvable : {videos_dir}")

    files = sorted(videos_dir.glob('*.md'))
    print(f"Source     : {source}")
    print(f"Dossier    : {videos_dir}")
    print(f"Fichiers   : {len(files)}")
    print(f"Mode       : {'DRY RUN' if dry_run else 'WRITE'}")
    print()

    counters: dict[str, int] = {}
    converted_files: list[str] = []
    added_files: list[str] = []
    error_files: list[tuple[str, str]] = []

    for f in files:
        status = process_file(f, dry_run=dry_run)
        counters[status] = counters.get(status, 0) + 1
        if status == 'converted':
            converted_files.append(f.name)
        elif status == 'added':
            added_files.append(f.name)
        elif status in ('no-h1', 'no-frontmatter'):
            error_files.append((status, f.name))

    print(f"  ok            : {counters.get('ok', 0):4d}  (déjà au format canonique)")
    print(f"  converted     : {counters.get('converted', 0):4d}  (thumbnail legacy → lecteur)")
    print(f"  added         : {counters.get('added', 0):4d}  (embed ajouté)")
    print(f"  dedup         : {counters.get('dedup', 0):4d}  (thumbnail legacy en doublon supprimé)")
    print(f"  no-id         : {counters.get('no-id', 0):4d}  (pas de youtube_id, ignoré)")
    print(f"  meta          : {counters.get('meta', 0):4d}  (CLAUDE.md, ignoré)")
    print(f"  no-h1         : {counters.get('no-h1', 0):4d}  (cas C sans H1, ignoré)")
    print(f"  no-frontmatter: {counters.get('no-frontmatter', 0):4d}  (sans frontmatter, ignoré)")
    print()
    total_modified = (
        counters.get('converted', 0)
        + counters.get('added', 0)
        + counters.get('dedup', 0)
    )
    print(f"Total modifié : {total_modified}")

    if error_files:
        print()
        print("Anomalies à examiner :")
        for status, name in error_files:
            print(f"  [{status}] {name}")


if __name__ == '__main__':
    main()
