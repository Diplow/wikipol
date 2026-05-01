# WikiPol — Instructions méta

## Objectif

WikiPol est l'ossature générique qui permet de construire un graphe de connaissances Obsidian à partir d'une source média (une chaîne YouTube, demain potentiellement un podcast ou un corpus d'articles).

Une **source** est un vault Obsidian autonome rangé dans `Sources/<NomSource>/`. Chaque source :
- définit son propre contexte éditorial dans `Sources/<NomSource>/CLAUDE.md` (ton, principes, pièges de lecture)
- définit sa propre taxonomie dans `Sources/<NomSource>/BUILD.md` (domaines, thèmes, couches advanced, construits par induction)
- déclare ses paramètres techniques dans `Sources/<NomSource>/source.yaml` (URL chaîne, slug git, chemins)
- fournit ses propres skills `write-<couche>` (Enjeux, Conjonctures, Possibles, Methodes, etc.) dans `Sources/<NomSource>/Skills/` — WikiPol ne contient pas de version générique de ces skills

Les skills Claude (`Skills/`), les scripts Python (`Scripts/`) et les conventions universelles (`BUILD.md`) sont partagés entre toutes les sources.

## Comment travailler sur une source

Lorsque l'utilisateur demande d'ingérer une vidéo, d'analyser un batch, ou de répondre à une question en utilisant une source :

1. **Identifier la source active**. L'utilisateur nomme la source explicitement ("ingère le batch X de MaChaine") ou la working directory est `Sources/<NomSource>/`. Si ambiguë, demander.
2. **Charger le contexte source**. Lire `Sources/<NomSource>/CLAUDE.md` — c'est ce fichier qui dicte le ton, les principes éditoriaux, les pièges, la grille analytique. Il complète et surcharge ce fichier-ci.
3. **Lire la config**. `Sources/<NomSource>/source.yaml` contient les paramètres techniques (URL chaîne, nom affiché, chemins, slug git). Les scripts et skills s'y réfèrent via le helper `Scripts/source_config.py`.
4. **Appliquer les conventions**. `BUILD.md` (ce repo) pour les invariants universels + `Sources/<NomSource>/BUILD.md` pour la taxonomie locale.

## Répartition des responsabilités

| Niveau | Fichier | Contient |
|--------|---------|----------|
| WikiPol | `CLAUDE.md` (ce fichier) | Instructions méta : comment WikiPol fonctionne |
| WikiPol | `BUILD.md` | Conventions universelles : nommage, wikilinks, frontmatter, git |
| WikiPol | `Skills/` | Skills d'ingestion, de synthèse et d'écriture génériques (basics) — agnostiques à la source |
| WikiPol | `Scripts/` | Scripts Python (ingestion, synthèse, bootstrap), lisent `source.yaml` |
| Source | `CLAUDE.md` | Contexte éditorial spécifique : qui produit, ton, pièges |
| Source | `BUILD.md` | Taxonomie locale : domaines, thèmes, spécifications des couches advanced (inductif) |
| Source | `source.yaml` | Paramètres techniques + `content_types` activés (whitelist stricte) |
| Source | `Skills/` | Skills `write-<couche>` (Enjeux, Conjonctures, …) propres à la source ; peut aussi surcharger les skills génériques par même nom |
| Source | `Videos/`, `Individus/`, `Organisations/`, `Concepts/`, plus les couches activées (ex: `Enjeux/`) | Contenu du vault (un dossier par type activé) |

## Découverte des skills

Quand une skill est invoquée pendant un travail sur une source, regarder dans cet ordre :

1. **`Sources/<NomSource>/Skills/<skill-name>/SKILL.md`** — skill propre à la source. Si elle existe, **elle l'emporte** sur la version générique (même nom = override).
2. **`Skills/<skill-name>/SKILL.md`** à la racine de WikiPol — skill générique, valable pour toutes les sources.

**Skills `write-<couche>` source-spécifiques par construction.** Les skills qui rédigent les fiches couche advanced (`write-enjeu`, `write-conjoncture`, `write-possible`, `write-methode`, etc.) n'existent pas au niveau WikiPol — chaque source les fournit dans son propre `Skills/`. La skill `synthesize-couche` (générique, niveau WikiPol) les invoque par convention de nom.

**Skills basic source-spécifiques (override).** Une source peut surcharger les skills basic génériques (`write-video`, `write-concept`, etc.) si son format diverge trop du modèle pour être paramétrable. Tant que la signature reste la même (entrées, sortie, prérequis), l'override est transparent pour les orchestrateurs (`ingest-video`, `ingest-batch`).

Avant de créer une skill source-spécifique, vérifier que le besoin n'est pas paramétrable côté générique — un override coûte cher en maintenance.

## Activation des types de fiches

Chaque source déclare ses `content_types` activés dans `Sources/<NomSource>/source.yaml` (whitelist stricte). Une skill `write-*` invoquée pour un type désactivé doit s'interrompre et signaler à l'appelant. Avant d'écrire, charger la config via `Scripts/source_config.py` et vérifier `cfg.content_type_enabled("Enjeux")` (ou le type concerné).

Voir `BUILD.md` pour la classification raw/basic/couches et la spec frontmatter des types universels (les couches sont définies par chaque source).

## Synthèse de fiches couche

Pour créer ou enrichir une fiche couche (Enjeu, Conjoncture, Possible, Methode, …), utiliser le workflow `synthesize` :

```bash
python Scripts/synthesize.py --source Sources/<NomSource> --batch <chemin-batch>.md
```

Le batch file (Markdown structuré) liste les vidéos source et précise la couche cible. Le script lance la skill `synthesize-couche` qui orchestre `gather-context`, lecture des vidéos, et délègue la rédaction à `write-<couche>` (skill source-spécifique).

## Créer une nouvelle source

```bash
python Scripts/new_source.py --name "NomSource" --slug "nomsource" \
    --youtube-url "https://www.youtube.com/@Chaine/videos"
```

Le script crée la structure, copie les templates, et affiche les prochaines étapes (remplir `CLAUDE.md` éditorial, découvrir les vidéos, lancer l'ingestion).

## Principes d'auto-amélioration

Comme dans chaque source, chaque ingestion est une occasion de raffiner le système. Si un transcript révèle un besoin générique (un type de skill manquant, une convention à étendre), mettre à jour `BUILD.md` ou les skills au niveau WikiPol. Si c'est spécifique à la source, mettre à jour `Sources/<NomSource>/CLAUDE.md` ou `BUILD.md`.

Rien n'est figé.
