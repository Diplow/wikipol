#!/usr/bin/env python
"""
Ingestion hebdomadaire — fetch + bookkeeping + ingest en une seule commande.

Pipeline :
1. Interroge yt-dlp pour les N dernières vidéos de la chaîne, ajoute les
   nouvelles à l'inventaire et extrait les transcripts manquants
   (équivalent de `batch_transcripts.py --recent N`).
2. Identifie les vidéos avec transcript mais sans batch attribué dans
   le tracker chronologique.
3. Append un nouveau "## Batch X" en queue du tracker, statut ⏳.
4. Commit + push dans la source ; bump du superproject git si applicable.
5. Lance `run_ingest --batch X` pour ingérer le batch.

Si aucune vidéo nouvelle n'est trouvée, sortie propre sans rien modifier.
Idempotent : peut être relancé après une interruption (les vidéos avec
transcript mais sans batch sont reprises).

Usage:
    python Scripts/weekly_ingest.py --source Sources/Paduteam
    python Scripts/weekly_ingest.py --source Sources/Paduteam --n 15
    python Scripts/weekly_ingest.py --source Sources/Paduteam --dry-run
    python Scripts/weekly_ingest.py --source Sources/Paduteam --no-ingest
    python Scripts/weekly_ingest.py --source Sources/Paduteam --no-commit
    python Scripts/weekly_ingest.py --source Sources/Paduteam --model opus
"""
import sys
import os
import re
import subprocess
import unicodedata
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from source_config import parse_source_arg, SourceConfig  # noqa: E402
import batch_transcripts as bt  # noqa: E402
import run_ingest as ri  # noqa: E402

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

DEFAULT_RECENT_N = 20


# =====================================================================
#  PARSING DU TRACKER
# =====================================================================

def find_max_batch(tracking_path: str) -> int:
    """Plus grand numéro de batch dans le tracker, 0 si fichier absent."""
    if not os.path.exists(tracking_path):
        return 0
    with open(tracking_path, 'r', encoding='utf-8') as f:
        content = f.read()
    nums = [int(m.group(1)) for m in re.finditer(r'^## Batch (\d+)', content, re.MULTILINE)]
    return max(nums) if nums else 0


def normalize_title(title: str) -> str:
    """Normalise un titre pour comparaison fuzzy (lowercase, sans accent, sans ponctuation)."""
    title = unicodedata.normalize('NFD', title).encode('ascii', 'ignore').decode('ascii')
    title = title.lower()
    title = re.sub(r'[^a-z0-9]+', ' ', title).strip()
    return title


def collect_known_titles(tracking_path: str) -> set[str]:
    """Ensemble des titres normalisés présents dans une bullet du tracker."""
    if not os.path.exists(tracking_path):
        return set()
    with open(tracking_path, 'r', encoding='utf-8') as f:
        content = f.read()
    titles = set()
    for line in content.split('\n'):
        m = re.match(r'^- \[[ x]\] (.+)$', line)
        if not m:
            continue
        title = m.group(1)
        title = re.sub(r'\s+—\s+\d{4}-\d{2}-\d{2}\s*$', '', title)
        title = re.sub(r'\s*\([^)]*transcript récupéré[^)]*\)\s*$', '', title)
        titles.add(normalize_title(title))
    return titles


# =====================================================================
#  RECHERCHE DES VIDÉOS À INGÉRER
# =====================================================================

def find_videos_to_ingest(cfg: SourceConfig) -> list[dict]:
    """Vidéos avec transcript dans l'inventaire mais absentes du tracker."""
    _, entries = bt.parse_inventaire(cfg.inventaire_path)
    known = collect_known_titles(cfg.tracking_file)

    pending = []
    for e in entries:
        transcript = e.get('transcript', '')
        if not transcript or '[[' not in transcript:
            continue
        if normalize_title(e['title']) in known:
            continue
        pending.append(e)
    return pending


# =====================================================================
#  AJOUT D'UN BATCH AU TRACKER
# =====================================================================

def append_batch(tracking_path: str, batch_num: int, videos: list[dict]) -> str:
    """Append une section ## Batch N à la fin du tracker. Retourne le titre."""
    dates = [v['date'] for v in videos if v.get('date')]
    if dates:
        d_min, d_max = min(dates), max(dates)
        title = f"Hebdo (auto) {d_min} → {d_max}"
    else:
        title = f"Hebdo (auto) {date.today().isoformat()}"

    sorted_videos = sorted(videos, key=lambda v: v.get('date') or '9999')
    lines = [
        '',
        f'## Batch {batch_num} — {title}',
        '',
        'Statut : ⏳ en attente',
        '',
    ]
    for v in sorted_videos:
        date_suffix = f" — {v['date']}" if v.get('date') else ''
        lines.append(f"- [ ] {v['title']}{date_suffix}")
    lines.extend(['', '---'])

    with open(tracking_path, 'r', encoding='utf-8') as f:
        content = f.read()
    if not content.endswith('\n'):
        content += '\n'
    content += '\n'.join(lines) + '\n'
    with open(tracking_path, 'w', encoding='utf-8') as f:
        f.write(content)
    return title


# =====================================================================
#  GIT (source + superproject)
# =====================================================================

def git(repo: str, *args, check=True):
    return subprocess.run(
        ['git'] + list(args), cwd=repo, check=check,
        capture_output=True, text=True, encoding='utf-8', errors='replace',
    )


def get_superproject(repo: str) -> str | None:
    res = git(repo, 'rev-parse', '--show-superproject-working-tree', check=False)
    if res.returncode != 0:
        return None
    path = res.stdout.strip()
    return path or None


def commit_and_push(cfg: SourceConfig, batch_num: int, batch_title: str):
    src = cfg.source_root
    git(src, 'add', '-A')
    res = git(src, 'diff', '--cached', '--quiet', check=False)
    if res.returncode == 0:
        print('  (rien à committer dans la source)')
        return
    msg = (
        f"chore: ingestion hebdo — batch {batch_num} ({batch_title})\n\n"
        f"Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>\n"
    )
    git(src, 'commit', '-m', msg)
    git(src, 'push')
    print(f"  ✓ source committée et pushée")

    super_path = get_superproject(src)
    if not super_path:
        return
    rel = os.path.relpath(src, super_path).replace('\\', '/')
    git(super_path, 'add', rel)
    res = git(super_path, 'diff', '--cached', '--quiet', check=False)
    if res.returncode == 0:
        return
    msg = (
        f"chore: bump {os.path.basename(src)} (batch {batch_num})\n\n"
        f"Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>\n"
    )
    git(super_path, 'commit', '-m', msg)
    git(super_path, 'push')
    print(f"  ✓ superproject bumpé et pushé")


# =====================================================================
#  MAIN
# =====================================================================

def main():
    args = sys.argv[1:]
    dry_run   = '--dry-run' in args
    no_ingest = '--no-ingest' in args
    no_commit = '--no-commit' in args
    n         = ri.parse_int_arg(args, '--n') or DEFAULT_RECENT_N
    model     = ri.parse_str_arg(args, '--model', default=None)

    cfg = parse_source_arg(args)
    if not cfg.channel_url:
        print(f"ERREUR : youtube.channel_url non défini dans {cfg.source_root}/source.yaml")
        sys.exit(1)

    print(f"=== Ingestion hebdo : {cfg.name} ===")
    print(f"  Source     : {cfg.source_root}")
    print(f"  Tracker    : {os.path.basename(cfg.tracking_file)}")
    print(f"  Récents (n): {n}")
    print(f"  Modèle     : {model or cfg.default_model}")
    if dry_run:
        print(f"  Mode       : DRY RUN")
    print()

    print(f"--- Étape 1 : fetch + extract ({n} dernières vidéos) ---")
    bt.cmd_recent(cfg, n, dry_run=dry_run)

    print(f"\n--- Étape 2 : identifier les vidéos sans batch ---")
    pending = find_videos_to_ingest(cfg)
    if not pending:
        print("Aucune vidéo nouvelle à ingérer — tracker à jour.")
        return
    print(f"{len(pending)} vidéo(s) avec transcript et sans batch :")
    for v in pending:
        print(f"  - {v['title']}  [{v.get('date') or '?'}]")

    next_num = find_max_batch(cfg.tracking_file) + 1

    if dry_run:
        print(f"\n[DRY RUN] Batch {next_num} aurait été ajouté avec ces {len(pending)} vidéos")
        return

    title = append_batch(cfg.tracking_file, next_num, pending)
    print(f"\n--- Étape 3 : tracker mis à jour ---")
    print(f"  ✓ Batch {next_num} — {title}")

    if no_commit:
        print("\n--no-commit — pas de commit/push")
    else:
        print(f"\n--- Étape 4 : commit + push ---")
        commit_and_push(cfg, next_num, title)

    if no_ingest:
        rel = os.path.relpath(cfg.source_root)
        print(f"\n--no-ingest — pour lancer l'ingestion plus tard :")
        print(f"  python Scripts/run_ingest.py --source {rel} --batch {next_num}")
        return

    print(f"\n--- Étape 5 : ingestion du batch {next_num} ---\n")
    ri.run_all(cfg, dry_run=False, single_batch=next_num, model=model)


if __name__ == '__main__':
    main()
