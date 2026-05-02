---
name: synthesize-couche
description: >
  Crée ou enrichit une fiche couche advanced (Enjeu, Conjoncture, Possible, Methode, ou autre couche
  définie par la source) à partir d'un batch de vidéos source. La skill orchestre — gather-context,
  lecture des vidéos, commit git — et délègue la **seule rédaction** à la skill
  source-spécifique `write-<couche>`. Déclencher quand l'utilisateur lance le script
  `Scripts/synthesize.py`, ou demande "synthétise la fiche X (couche Y)", ou pointe explicitement
  vers un batch de synthèse.
date created: 2026-05-01
date modified: 2026-05-02
skill_version: synthesize-couche-2026-05-02b
---

# Skill : Synthèse d'une fiche couche

## Vue d'ensemble

Cette skill **crée ou enrichit une seule fiche couche** (Enjeu, Conjoncture, Possible, Methode, ou toute autre couche déclarée par la source) à partir d'un **batch de synthèse** : un fichier `.md` qui désigne la couche cible, le nom de la fiche, les vidéos source à mobiliser, et éventuellement des fiches pivots à intégrer en priorité.

**Pourquoi cette skill existe :** les fiches couche (advanced) sont par construction des **synthèses multi-vidéos** — elles agrègent ce que la source dit transversalement sur un sujet. Les écrire exige (a) du contexte vault, (b) la lecture des vidéos source pertinentes, (c) la connaissance du format de la couche dans la source. La skill prend en charge (a) et (b) ; elle délègue (c) à la skill source-spécifique `write-<couche>` qui sait comment formater la fiche.

**Séparation des responsabilités :**
- `synthesize-couche` (cette skill, niveau WikiPol) — orchestration : git, contexte, lecture, dispatch, commit, statut.
- `write-<couche>` (skill source-spécifique, niveau `Sources/<NomSource>/Skills/`) — **seule rédaction** de la fiche cible. Reçoit le contexte, n'a aucune logique d'orchestration.

**Sortie attendue à la fin de l'orchestration** — un commit unique qui modifie **trois ensembles de fichiers** :

1. **La fiche couche cible** (créée ou enrichie) — produite par `write-<couche>` à l'étape 6.
2. **Les ébauches** créées pour résoudre les wikilinks orphelins — étape 7.
3. **Les frontmatters des fiches Vidéos référencées dans la fiche cible** — étape 8 (back-références `<target_couche>s: [target_name]`).

⚠️ **Si le commit final ne touche que (1), c'est un échec partiel** : l'étape 8 a été oubliée. C'est l'erreur la plus fréquente et la plus invisible (rien ne casse, mais `gather-context` et les futures synthèses ne pourront plus retrouver les vidéos par grep frontmatter). Voir l'étape 8 pour la vérification obligatoire.

**Conventions partagées** (nommage, wikilinks, frontmatter, git) : voir `BUILD.md` de WikiPol.
**Contexte éditorial de la source** (ton, principes, attribution) : voir `CLAUDE.md` de la source.
**Spécifications de la couche** (critère, format, frontmatter) : voir `BUILD.md` de la source.

---

## Entrée

**Mode standard : un batch de synthèse** — un fichier `.md` typiquement stocké sous `Sources/<NomSource>/Syntheses/<slug>.md`. Frontmatter requis :

```yaml
---
type: synthesis-batch
target_couche: enjeu | conjoncture | possible | methode | <autre>
target_name: "Nom exact de la fiche cible"
generated: 2026-05-01
statut: ⏳ en attente
---
```

Corps :
- `## Objectif` — 1-3 lignes décrivant ce que la synthèse doit produire.
- `## Vidéos source` — liste de wikilinks vers des fiches `Videos/`.
- `## Fiches pivots` (optionnel) — wikilinks vers Concepts/Individus/Organisations à intégrer en priorité.

Si l'utilisateur fournit un sujet libre sans batch file, **demander qu'un batch file soit créé d'abord**. Cette skill ne travaille qu'à partir d'un batch existant — c'est ce qui garantit reproductibilité et logging.

**Note worktree** : cette skill n'a **pas besoin** d'être lancée dans un worktree git. Elle travaille directement sur `develop`. Ne pas créer de worktree pour l'exécuter.

---

## Workflow

### Étape 1 — Charger la config et le batch

1. Identifier la source active (cwd ou via `Scripts/source_config.py`). Lire `Sources/<NomSource>/source.yaml`.
2. Lire le batch file en entier. Extraire :
   - `target_couche` (ex. `enjeu`, `conjoncture`, `possible`, `methode`)
   - `target_name` (nom exact de la fiche cible)
   - `statut` (doit être `⏳ en attente` ; sinon signaler à l'utilisateur)
   - Liste des vidéos source (résolues par leur basename de fiche `Videos/`)
   - Liste des fiches pivots (optionnelles)
   - Texte de l'objectif
3. **Vérifier l'activation de la couche** dans `source.yaml:content_types.couches`. Si désactivée, interrompre et demander à l'utilisateur de l'activer (ou de choisir une autre couche).
4. **Vérifier que la skill `write-<target_couche>` existe** dans `Sources/<NomSource>/Skills/`. Si elle n'existe pas, interrompre — il manque une skill source-spécifique pour cette couche.

### Étape 2 — État du vault (gather-context)

Appeler `gather-context` avec `target_name` comme sujet. Cela produit `Sources/<NomSource>/.context-tmp.md` — une synthèse dense + une carte de liens.

Ce fichier sera passé tel quel à la skill `write-<target_couche>` à l'étape 6.

### Étape 3 — Vérifier l'existence de la fiche cible

- Si le fichier `Sources/<NomSource>/<DossierCouche>/<target_name>.md` existe déjà → mode **enrichissement**.
- Sinon → mode **création**.

Le `<DossierCouche>` est dérivé de `target_couche` selon la convention de la source (ex : `enjeu` → `Enjeux/`, `conjoncture` → `Conjonctures/`).

### Étape 4 — Mettre develop à jour

1. `git fetch origin`
2. `git checkout develop && git pull origin develop`

Le travail se fait directement sur `develop` — pas de branche dédiée.

### Étape 5 — Lire les vidéos source

Pour chaque vidéo listée dans `## Vidéos source` du batch :
1. Lire la fiche `Sources/<NomSource>/Videos/<basename>.md` en entier.
2. Si une fiche pivot est listée, lire aussi la fiche correspondante en entier.

**Ne pas lire les transcripts.** Comme pour `ingest-batch` étape 6, la granularité « fiche vidéo » suffit — elle a déjà extrait les thèses et données matérielles.

### Étape 6 — Déléguer la rédaction à `write-<target_couche>`

Lancer un subagent dédié via l'outil `Agent` (subagent_type: `general-purpose`) qui invoque la skill source-spécifique `write-<target_couche>`. Le subagent reçoit :

- `target_name`
- `target_couche`
- Mode : création ou enrichissement (selon §3)
- Chemin de `.context-tmp.md` (à lire intégralement)
- Liste des chemins de fiches Vidéos lues à l'étape 5
- Liste des chemins de fiches pivots
- L'objectif extrait du batch file
- Pointeurs vers `BUILD.md` source (spécification de la couche), `CLAUDE.md` source (ton), `BUILD.md` WikiPol (invariants).

**Le subagent ne fait que rédiger.** Il ne touche pas à git, ne modifie pas le batch file, ne lance pas d'autres skills d'orchestration. Il produit ou enrichit `Sources/<NomSource>/<DossierCouche>/<target_name>.md` et signale les wikilinks orphelins éventuels.

Si le subagent échoue ou produit une fiche manifestement incomplète, analyser la cause et le relancer — ne pas committer un état dégradé.

### Étape 7 — Vérification liens orphelins

Parcourir la fiche produite/enrichie. Pour chaque `[[wikilink]]`, vérifier que le fichier cible existe. Créer des ébauches pour les liens restants (en suivant les conventions de nommage de la source).

### Étape 8 — Pose des back-références frontmatter (OBLIGATOIRE)

⚠️ **Étape la plus oubliée. Ne pas la sauter.** Sans elle, les futures synthèses ne pourront pas retrouver ces vidéos par grep frontmatter — le graphe inversé est cassé silencieusement.

**Le plus simple — invoquer le script utilitaire** :

```bash
python Scripts/tag_back_references.py --fiche Sources/<NomSource>/<DossierCouche>/<target_name>.md
```

Le script lit la section « Vidéos » de la fiche cible, identifie les `[[wikilinks]]` qui pointent vers `Videos/`, et propage le tag de manière idempotente. Output sous la forme `+ ajouté` / `= déjà OK` / `! erreur`. **Toujours préférer le script à une réécriture manuelle** — il gère correctement les cas inline `[a, b]`, multiline `- a`, et l'insertion de champ absent.

**Si on procède manuellement** (cas exceptionnel — script indisponible, source avec format frontmatter atypique) :

La fiche couche fraîchement produite (étape 6) contient une section listant les vidéos qui mobilisent réellement la couche (« Vidéos où elle est mobilisée », « Vidéos clés », « Vidéos où le concept est développé », etc. — selon le format défini dans le `BUILD.md` source pour cette couche). Pour chaque wikilink `[[Titre]]` de cette section qui pointe vers une fiche `Sources/<NomSource>/Videos/`, mettre à jour son frontmatter :

- **Champ cible** : `<target_couche>s` au pluriel (`methodes`, `conjonctures`, `possibles`, `enjeux`).
- Si le champ n'existe pas → l'ajouter avec `[target_name]`.
- Si le champ existe et ne contient pas `target_name` → ajouter `target_name` à la liste, en respectant le style YAML existant (inline `[a, b]` ou multiline `- a\n  - b`).
- Si le champ contient déjà `target_name` → ne rien faire (idempotent).

**Position d'insertion canonique** : juste après le champ `enjeux:` (ou après `thèmes:` si pas d'`enjeux:`). Préserver l'indentation et le style YAML utilisés dans le frontmatter cible.

**Ne tagger que les vidéos *réellement listées dans la fiche couche produite*** — pas l'ensemble des vidéos du batch source. Le batch est large pour donner de la matière à `write-<couche>` ; la fiche finale a fait le tri éditorial. Les `BUILD.md` sources rappellent généralement de ne pas remplir ces champs gratuitement.

**Vérification finale obligatoire avant l'étape 11 (commit)** :

```bash
git status
```

La sortie doit montrer **plusieurs fichiers `Videos/*.md` modifiés** en plus de la fiche cible. Si seule la fiche cible apparaît, l'étape 8 a échoué — relancer `tag_back_references.py` avant de committer. Garder la liste exacte des fiches Vidéos modifiées pour le commit (étape 11) et pour le résumé (étape 12).

### Étape 9 — Vérification orthographique

Passe unique sur la fiche produite/enrichie.

### Étape 10 — Mise à jour du statut du batch file

Modifier le frontmatter du batch file : `statut: ⏳ en attente` → `statut: ✅ fait`. Ajouter optionnellement une ligne dans le corps avec la date de réalisation.

### Étape 11 — Commit direct sur develop

**Un seul commit pour la synthèse**, directement sur `develop` :

```
synthesize: COUCHE — Nom de la fiche cible

Mode: création | enrichissement
Vidéos source: N
- {Titre 1}
- {Titre 2}
- ...

Fiches créées: X (liste — fiche cible + ébauches orphelines créées)
Fiches enrichies: Y (liste)
Fiches Vidéos taguées: Z (back-références frontmatter <target_couche>s)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

1. `git add` fichier par fichier (pas `-A`) — la fiche cible, les ébauches créées, le batch file mis à jour, **et chaque fiche Vidéo dont le frontmatter a été modifié à l'étape 8**.
2. Commit avec le message ci-dessus sur `develop`.
3. Push : `git push origin develop`.

### Étape 12 — Résumé à l'utilisateur

Présenter :
- Couche cible, nom de la fiche, mode (création vs enrichissement)
- Nombre de vidéos source mobilisées
- Liste des fiches créées (cible + ébauches) et enrichies
- Nombre de fiches Vidéos taguées en back-référence (étape 8)
- Confirmation que `develop` est à jour (commit poussé)
- Inviter l'utilisateur à examiner la fiche produite

---

## Règles

- **Skill `write-<couche>` source-spécifique obligatoire.** Cette skill ne contient aucune logique de rédaction — toute la spécificité de la couche (format, sections, frontmatter) vit dans la skill source. Si elle n'existe pas, interrompre.
- **Une seule fiche cible par synthèse.** Si l'utilisateur veut produire plusieurs fiches, il doit créer plusieurs batch files et les lancer séparément.
- **Pas de lecture de transcripts.** Comme pour `ingest-batch` en consolidation finale, on travaille à la granularité « fiche vidéo » — sinon on sature le contexte.
- **Pas de modification de fiches basic, sauf back-références frontmatter.** La skill ne touche que (a) la fiche cible de la couche, (b) les ébauches qu'elle crée pour résoudre des wikilinks orphelins, et (c) le **frontmatter** des fiches Vidéos listées dans la section « Vidéos » de la fiche cible — uniquement pour ajouter `target_name` au champ `<target_couche>s` (étape 8). Le **corps** des fiches Vidéos reste lu, pas modifié. Les fiches Concepts/Individus/Organisations restent intégralement lues, pas modifiées.
- **L'étape 8 est obligatoire — pas optionnelle.** Une synthèse sans back-références est un échec partiel : la fiche couche existe mais le graphe inversé est cassé. L'erreur ne se voit pas tout de suite (rien ne plante), mais les futures synthèses ne retrouveront pas ces vidéos par grep frontmatter. Avant l'étape 11 (commit), `git status` doit montrer plusieurs fiches `Videos/*.md` modifiées. Si tel n'est pas le cas, relancer `Scripts/tag_back_references.py --fiche <chemin-fiche-cible>` qui implémente l'étape 8 de manière idempotente.
- **Un seul commit sur develop.** Même si la fiche cible est enrichie + plusieurs ébauches sont créées, c'est 1 commit direct sur `develop` (pas de branche, pas de merge).
- **Ne jamais référencer le « batch » ou la skill dans la fiche produite.** La fiche cible est lue par d'autres usagers du vault qui n'ont pas accès au batch file. Pas de phrase comme « consolidé à partir du batch X » — l'origine de la synthèse est dans l'historique git, pas dans la fiche.
- **Statut obligatoirement à jour.** Si le batch file n'est pas marqué `✅ fait` à la fin, c'est un bug — la skill doit garantir l'idempotence (pas de relance accidentelle d'une synthèse déjà faite).

---

## Feedback système

À la fin de la synthèse, évaluer si la rédaction a révélé des éléments qui devraient mettre à jour le système :
- Le format de la couche dans `BUILD.md` source est-il toujours adéquat, ou la fiche produite a-t-elle dû le contourner ?
- Des fiches pivots manquaient-elles dans le batch (visible aux orphelins fréquents) ? Suggérer à l'utilisateur de les ajouter dans les futurs batches.
- Le `gather-context` a-t-il fourni assez de matière, ou la skill `write-<couche>` a-t-elle dû se rabattre sur des intuitions ?

Signaler à l'utilisateur sans modifier automatiquement.
