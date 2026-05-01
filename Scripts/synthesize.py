#!/usr/bin/env python
"""
Runner de synthèse pour une source WikiPol.

Lit un batch file de synthèse (`Sources/<NomSource>/Syntheses/<slug>.md`),
vérifie que la couche cible est activée et que la skill `write-<target_couche>`
existe dans la source, puis invoque `claude` via la skill `synthesize-couche`.

Usage:
    python synthesize.py --source Sources/MaSource --batch Sources/MaSource/Syntheses/2026-05-foo.md
    python synthesize.py --source Sources/MaSource --batch ... --dry-run
    python synthesize.py --source Sources/MaSource --batch ... --model opus
"""
import sys
import os
import re
import subprocess
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from source_config import parse_source_arg, SourceConfig  # noqa: E402

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

TIMEOUT = 10800  # 3h
CLAUDE_CMD = "claude"

# Mapping standard : target_couche (singulier kebab-case) → nom du dossier dans source.yaml.
# Une source peut surcharger via le champ `target_dir` du frontmatter du batch.
DEFAULT_COUCHE_DIRS = {
    "enjeu": "Enjeux",
    "conjoncture": "Conjonctures",
    "possible": "Possibles",
    "methode": "Methodes",
    "evenement": "Evenements",
}


# =====================================================================
#  LOGGING
# =====================================================================

def make_logger(log_path: str):
    def log(msg: str):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{ts}] {msg}"
        print(line)
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(line + "\n")
    return log


# =====================================================================
#  PARSING DU BATCH FILE
# =====================================================================

FRONTMATTER_RE = re.compile(r'\A---\s*\n(.*?)\n---\s*\n', re.DOTALL)


def parse_batch_file(batch_path: str) -> dict:
    """Parse le frontmatter YAML du batch file. Retourne un dict avec les champs requis."""
    if not os.path.isfile(batch_path):
        print(f"ERREUR : batch file introuvable : {batch_path}", file=sys.stderr)
        sys.exit(1)

    with open(batch_path, 'r', encoding='utf-8') as f:
        content = f.read()

    m = FRONTMATTER_RE.match(content)
    if not m:
        print(f"ERREUR : pas de frontmatter YAML détecté dans {batch_path}", file=sys.stderr)
        sys.exit(1)

    try:
        import yaml  # type: ignore
    except ImportError:
        print("ERREUR : PyYAML requis. pip install pyyaml", file=sys.stderr)
        sys.exit(1)

    fm = yaml.safe_load(m.group(1)) or {}

    if fm.get('type') != 'synthesis-batch':
        print(f"ERREUR : type frontmatter attendu 'synthesis-batch', reçu {fm.get('type')!r}",
              file=sys.stderr)
        sys.exit(1)

    target_couche = fm.get('target_couche')
    target_name = fm.get('target_name')
    if not target_couche or not target_name:
        print("ERREUR : `target_couche` et `target_name` sont requis dans le frontmatter.",
              file=sys.stderr)
        sys.exit(1)

    return {
        'target_couche': str(target_couche).strip().lower(),
        'target_name': str(target_name).strip(),
        'target_dir': fm.get('target_dir'),  # optionnel
        'statut': fm.get('statut', '').strip(),
        'generated': fm.get('generated', ''),
    }


def resolve_target_dir(target_couche: str, override: str | None) -> str:
    """Dérive le nom du dossier de la couche depuis target_couche (ou override)."""
    if override:
        return override
    if target_couche in DEFAULT_COUCHE_DIRS:
        return DEFAULT_COUCHE_DIRS[target_couche]
    # Convention par défaut : capitaliser + ajouter "s" si pas déjà terminé par "s"
    capped = target_couche.capitalize()
    if not capped.endswith('s'):
        capped += 's'
    return capped


# =====================================================================
#  VÉRIFICATIONS PRÉALABLES
# =====================================================================

def check_couche_enabled(cfg: SourceConfig, target_dir: str, log) -> bool:
    if cfg.content_type_enabled(target_dir):
        log(f"Couche `{target_dir}` activée dans source.yaml — OK")
        return True
    log(f"ERREUR : couche `{target_dir}` désactivée dans {cfg.source_root}/source.yaml.")
    log("        Activer la couche, ou choisir une autre cible.")
    return False


def check_skill_exists(cfg: SourceConfig, target_couche: str, log) -> bool:
    skill_path = os.path.join(cfg.source_root, "Skills", f"write-{target_couche}", "SKILL.md")
    if os.path.isfile(skill_path):
        log(f"Skill `write-{target_couche}` trouvée — OK ({skill_path})")
        return True
    log(f"ERREUR : skill source-spécifique `write-{target_couche}` introuvable.")
    log(f"        Attendu : {skill_path}")
    log(f"        WikiPol ne fournit pas de version générique — la source doit la définir.")
    return False


# =====================================================================
#  INVOCATION CLAUDE
# =====================================================================

def run_synthesize(cfg: SourceConfig, batch_path: str, batch: dict,
                   log, dry_run: bool = False, model: str | None = None) -> bool:
    """Invoque claude via la skill synthesize-couche. Retourne True si succès."""
    batch_relative = os.path.relpath(batch_path, cfg.source_root)
    prompt = (
        f"Synthétise la fiche \"{batch['target_name']}\" "
        f"(couche {batch['target_couche']}) "
        f"à partir du batch {batch_relative} "
        f"(mode automatique)"
    )
    active_model = model or cfg.default_model

    if dry_run:
        log(f"[DRY RUN] Couche       : {batch['target_couche']}")
        log(f"[DRY RUN] Cible        : {batch['target_name']}")
        log(f"[DRY RUN] Batch        : {batch_relative}")
        log(f"[DRY RUN] Modèle       : {active_model}")
        log(f"[DRY RUN] Prompt       : {prompt}")
        log(f"[DRY RUN] cwd          : {cfg.source_root}")
        return True

    cmd = [CLAUDE_CMD, "--dangerously-skip-permissions", "--model", active_model, "-p", prompt]
    log(f"Lancement : {' '.join(cmd[:3])} \"...\"")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=TIMEOUT,
            cwd=cfg.source_root,
        )
    except subprocess.TimeoutExpired:
        log(f"TIMEOUT ({TIMEOUT}s) — synthèse {batch['target_name']}")
        return False
    except FileNotFoundError:
        log(f"ERREUR : commande '{CLAUDE_CMD}' introuvable. Vérifier que claude CLI est installé.")
        sys.exit(1)

    for line in (result.stdout or "").splitlines():
        log(f"  stdout: {line}")
    if result.stderr and result.stderr.strip():
        for line in result.stderr.splitlines():
            log(f"  stderr: {line}")

    if result.returncode == 0:
        log(f"✓ Synthèse {batch['target_name']} ({batch['target_couche']}) — succès.")
        return True
    log(f"ÉCHEC (code {result.returncode}) — synthèse {batch['target_name']}")
    return False


# =====================================================================
#  ORCHESTRATION
# =====================================================================

def run(cfg: SourceConfig, batch_path: str, dry_run: bool = False, model: str | None = None):
    log_path = os.path.join(cfg.source_root, "synthesize.log")
    log = make_logger(log_path)

    batch = parse_batch_file(batch_path)
    target_dir = resolve_target_dir(batch['target_couche'], batch.get('target_dir'))

    log(f"{'='*60}")
    log(f"SYNTHÈSE — {cfg.name}")
    log(f"{'='*60}")
    log(f"Source         : {cfg.source_root}")
    log(f"Batch          : {batch_path}")
    log(f"Couche cible   : {batch['target_couche']} → dossier `{target_dir}`")
    log(f"Fiche cible    : {batch['target_name']}")
    log(f"Statut batch   : {batch['statut'] or '(non précisé)'}")
    log(f"Modèle         : {model or cfg.default_model}")
    if dry_run:
        log(f"Mode           : DRY RUN")

    if batch['statut'] and '✅' in batch['statut']:
        log("Le batch est déjà marqué ✅ fait. Annulation pour éviter une relance accidentelle.")
        log("Pour relancer, mettre `statut: ⏳ en attente` dans le frontmatter du batch.")
        return

    if not check_couche_enabled(cfg, target_dir, log):
        sys.exit(1)
    if not check_skill_exists(cfg, batch['target_couche'], log):
        sys.exit(1)

    success = run_synthesize(cfg, batch_path, batch, log, dry_run=dry_run, model=model)

    log(f"{'='*60}")
    log("TERMINÉ — succès" if success else "TERMINÉ — échec")
    log(f"{'='*60}")
    if not success:
        sys.exit(1)


# =====================================================================
#  MAIN
# =====================================================================

def parse_str_arg(args, flag, default=None):
    if flag not in args:
        return default
    idx = args.index(flag)
    if idx + 1 >= len(args):
        print(f"ERREUR : {flag} attend une valeur.", file=sys.stderr)
        sys.exit(1)
    return args[idx + 1]


def main():
    args = sys.argv[1:]
    dry_run = '--dry-run' in args
    model = parse_str_arg(args, '--model', default=None)
    batch = parse_str_arg(args, '--batch', default=None)

    if not batch:
        print("ERREUR : --batch <chemin> requis.", file=sys.stderr)
        print("Usage : python synthesize.py --source <source> --batch <batch.md> [--dry-run] [--model opus]",
              file=sys.stderr)
        sys.exit(1)

    if not os.path.isabs(batch):
        batch = os.path.abspath(batch)

    cfg = parse_source_arg(args)
    run(cfg, batch, dry_run=dry_run, model=model)


if __name__ == '__main__':
    main()
