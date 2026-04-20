# BUILD.md — Conventions universelles WikiPol

Ce fichier documente **comment** un vault WikiPol est construit : architecture des skills, invariants de nommage et de format, workflow git. Les skills individuelles (dans `Skills/`) décrivent leur workflow spécifique ; ce fichier contient les invariants communs à toutes les sources.

La **taxonomie concrète** (domaines, thèmes, enjeux) n'est pas définie ici : elle est propre à chaque source et vit dans `Sources/<NomSource>/BUILD.md`.

---

## Architecture des skills

```
┌──────────────────────────────────────────────────────┐
│  ingest-batch (optionnel)                            │
│  Regroupe N transcripts par sujet, dispatche vers    │
│  des subagents dédiés (un par vidéo) pour préserver  │
│  la finesse analytique. Un seul commit / PR.         │
└───────────────────────┬──────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────────────┐
│  ingest-video (orchestrateur principal)               │
│  1. Lit le transcript                                │
│  2. Appelle gather-context pour le sujet             │
│  3. Dispatche vers les skills spécialisées           │
│  4. Gère le git (branche, commit, PR)                │
└───────┬──────────┬──────────┬──────────┬─────────────┘
        │          │          │          │
        ▼          ▼          ▼          ▼
   write-video  write-entity  write-concept  write-enjeu
```

### Principe central : séparer contexte et écriture

Chaque skill spécialisée (`write-*`) reçoit en entrée :
- Le **contexte** rassemblé par `gather-context` (fiches vault existantes, vidéos liées, entités connexes)
- Les **fiches existantes** pertinentes (déjà lues)
- Les **instructions d'écriture** spécifiques à son type

Elle ne fait **pas** de recherche extensive. Elle prend le contexte pour acquis et se concentre sur la rédaction.

### Skills

| Skill | Rôle |
|-------|------|
| `gather-context` | Rassembler tout ce que le vault sait sur un sujet donné |
| `ingest-video` | Orchestrer l'ingestion d'un transcript |
| `write-video` | Rédiger/enrichir une fiche `Videos/` |
| `write-entity` | Rédiger/enrichir une fiche `Individus/` ou `Organisations/` |
| `write-concept` | Rédiger/enrichir une fiche `Concepts/` |
| `write-enjeu` | Rédiger/enrichir une fiche `Enjeux/` |
| `ingest-batch` | Ingérer plusieurs transcripts par sujet pour cohérence maximale |

---

## Invariants — Règles communes à toutes les skills et toutes les sources

### Attribution

L'attribution par défaut est collective — elle désigne la source (ex : "la chaîne", "les auteurs", nom collectif défini dans `source.yaml:source.attribution`). N'attribuer individuellement que quand c'est explicitement identifiable dans le transcript (segment solo, auto-identification, rôle reconnu).

Le ton et les principes d'attribution spécifiques à une source sont définis dans `Sources/<NomSource>/CLAUDE.md`.

### Noms de fichiers

- Pas d'accents ni de caractères spéciaux dans les noms de fichiers
- Les noms accentués sont définis en `aliases` dans le frontmatter
- **Individus** : Prénom Nom (`Jean-Luc Melenchon.md`)
- **Organisations** : Nom officiel complet (`France Insoumise.md`, pas `LFI.md`)
- **Concepts** : Nom descriptif capitalisé (`Eclatement du bloc central.md`)
- **Enjeux** : Nom court du combat (`Plus jamais PS.md`)
- **Vidéos** : Titre abrégé lisible (`COMMENT MELENCHON VA GAGNER EN 2027 AU SECOND TOUR.md`)

### Wikilinks

- `[[Nom Exact du Fichier]]` sans chemin, sans `.md`
- Pour les alias : `[[Nom réel|alias affiché]]` (ex: `[[Parti Communiste Français|PCF]]`)
- Le nom du fichier = le texte du wikilink
- Chaque wikilink doit pointer vers un fichier existant. Si un lien orphelin est créé, créer au minimum une fiche ébauche.

### YAML frontmatter

Toujours inclure au minimum :
- `type` : vidéo / individu / organisation / concept / enjeu
- `domaine` : 1-2 valeurs parmi celles définies dans le `BUILD.md` de la source
- `thèmes` : liste de thèmes du vocabulaire contrôlé local
- `skill_version` : identifiant de la skill + date (ex: `write-video-2026-04-20`)

Selon le type :
- **Vidéos** : + `enjeux`, `date`, `youtube_id`
- **Individus** : + `aliases`
- **Organisations** : + `aliases`
- **Concepts** : + `aliases`
- **Enjeux** : pas de champ supplémentaire spécifique

### Hashtags inline

Après le frontmatter YAML, les fiches incluent une ligne de hashtags structurés avant le titre `# Titre` :

```
#domaine/valeur #thème/valeur #enjeu/valeur
```

Inclure uniquement domaine, thèmes et enjeux (pas format ni statut). Ces hashtags matérialisent les tags comme nœuds du graphe Obsidian.

### Taxonomie des tags

3 axes structurent le tagging :

1. **domaine** — champ d'analyse (liste finie, définie par la source)
2. **thèmes** — sujets spécifiques récurrents (vocabulaire contrôlé, extensible par la source)
3. **enjeux** — combats stratégiques récurrents (définis par la source)

Les valeurs concrètes de ces axes sont déclarées dans `Sources/<NomSource>/BUILD.md`. Elles croissent **par induction** au fil des ingestions : ajouter un nouveau thème si un sujet revient dans 2+ vidéos, un nouvel enjeu si un combat revient dans 3+ vidéos avec une position constante.

### Sourcing YouTube

Les fiches vidéo incluent un lien YouTube embarqué en haut (avant le résumé) et des notes de bas de page avec timestamps pour sourcer les points clés.

**Lien embarqué** (en haut de chaque fiche vidéo, après les hashtags, avant le `# Titre`) :
```markdown
![TITRE](https://www.youtube.com/watch?v=YOUTUBE_ID)
```

Obsidian reconnaît cette syntaxe image pointant vers une URL YouTube et affiche un lecteur embarqué. Ne **pas** utiliser de thumbnail cliquable via `img.youtube.com` — cette forme donne une image statique sans lecteur.

**Notes de bas de page avec timestamp** (dans le corps des fiches — vidéos, entités, concepts, enjeux) :
```markdown
La source affirme que X est structurellement incapable de Y[^1].

[^1]: [12:34](https://www.youtube.com/watch?v=YOUTUBE_ID&t=754) — "citation exacte ou résumé du passage"
```

Le `youtube_id` est stocké dans le frontmatter de la fiche vidéo. Pour convertir un timestamp `MM:SS` en secondes, utiliser le helper `Scripts/timestamp_to_seconds.py`.

Pour les fiches non-vidéo (entités, concepts, enjeux), les footnotes référencent la vidéo source via son `youtube_id` — récupéré depuis la fiche vidéo correspondante.

### Style

- Phrases courtes, pas de remplissage
- Ton analytique, pas encyclopédique
- Fidélité à l'analyse de la source — restituer, pas neutraliser

Les principes éditoriaux spécifiques (restituer sans challenger, nuancer, contextualiser, etc.) sont définis dans `Sources/<NomSource>/CLAUDE.md` selon la nature de la source.

### Volume

Être ambitieux dans la création de fiches. Chaque personne mentionnée significativement, chaque organisation citée, chaque mécanisme analytique décrit mérite sa fiche. Il vaut mieux créer une fiche minimale (ébauche) que de laisser un lien orphelin.

---

## Workflow git

Chaque source est versionnée dans son propre dépôt GitHub (paramètre `git.repo` dans `source.yaml`). WikiPol — l'ossature — est versionné dans un dépôt distinct.

### Stratégie de branches

```
main              ← production (publication du wiki)
 └── develop      ← intégration (état courant du vault)
      ├── ingest/<slug-video>            ← ingestion unitaire (1 vidéo)
      └── ingest-batch/<slug-sujet>      ← ingestion batch (N vidéos d'un même sujet)
```

- **`main`** : état publié du wiki. Jamais de push direct.
- **`develop`** : branche d'intégration. Toutes les ingestions sont mergées ici.
- **`ingest/<slug>`** : branche éphémère pour une ingestion unitaire. Slug = titre de la vidéo en minuscules, sans accents, tirets, tronqué à ~50 chars.
- **`ingest-batch/<slug>`** : branche éphémère pour un batch thématique. Slug = nom du sujet (ex: `paduteam-2024-w47-w48`), ~40 chars max. Un seul commit et une seule PR couvrant toutes les vidéos du batch.

### En début d'ingestion

1. Se placer sur develop à jour : `git checkout develop && git pull origin develop`
2. Créer la branche : `git checkout -b ingest/<slug>` (ou `ingest-batch/<slug>`)

### En fin d'ingestion

1. Stage les fichiers modifiés/créés par nom (pas `git add -A`)
2. Commit avec message structuré :
   ```
   ingest: TITRE ABRÉGÉ DE LA VIDÉO

   Fiches créées: X (liste)
   Fiches enrichies: Y (liste)
   Corrections ortho: Z (liste si applicable)

   Co-Authored-By: Claude <noreply@anthropic.com>
   ```
3. Push : `git push -u origin ingest/<slug>`
4. Merge dans develop (PR ou merge direct selon convention de la source)

---

## Chemins d'un vault source

```
Sources/<NomSource>/
├── CLAUDE.md                     ← contexte éditorial de la source
├── BUILD.md                      ← taxonomie locale
├── source.yaml                   ← config paramétrique
├── Sources/
│   ├── Inventaire.md             ← table des vidéos (Dataview)
│   └── Transcripts/              ← transcripts bruts (.md)
├── Videos/                       ← 1 fiche par vidéo ingérée
├── Individus/                    ← 1 fiche par personne
├── Organisations/                ← 1 fiche par parti/asso/média
├── Concepts/                     ← 1 fiche par concept analytique
├── Enjeux/                       ← 1 fiche par combat stratégique
└── <SLUG>_CHRONOLOGIQUE.md       ← fichier de suivi d'ingestion batch
```
