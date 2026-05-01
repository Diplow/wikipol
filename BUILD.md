# BUILD.md — Conventions universelles WikiPol

Ce fichier documente **comment** un vault WikiPol est construit : architecture des skills, invariants de nommage et de format, workflow git. Les skills individuelles (dans `Skills/`) décrivent leur workflow spécifique ; ce fichier contient les invariants communs à toutes les sources.

La **taxonomie concrète** (domaines, thèmes, couches) n'est pas définie ici : elle est propre à chaque source et vit dans `Sources/<NomSource>/BUILD.md`.

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
│  3. Dispatche vers les skills write-* selon les      │
│     content_types activés dans source.yaml           │
│  4. Gère le git (branche, commit, PR)                │
└───────┬──────────────────┬─────────────────┬─────────┘
        │                  │                 │
        ▼                  ▼                 ▼
   write-video        write-entity      write-evenement
   write-concept                        (basics)

┌──────────────────────────────────────────────────────┐
│  synthesize-couche (orchestrateur de synthèse)        │
│  Crée des fiches couche (advanced) à partir d'un     │
│  batch de vidéos source. Délègue la rédaction à      │
│  write-<couche> (skill source-spécifique).           │
└───────────────────────┬──────────────────────────────┘
                        │
                        ▼
                write-<couche>
              (source-specific)
```

### Principe central : séparer contexte et écriture

Chaque skill spécialisée (`write-*`) reçoit en entrée :
- Le **contexte** rassemblé par `gather-context` (fiches vault existantes, vidéos liées, entités connexes)
- Les **fiches existantes** pertinentes (déjà lues)
- Les **instructions d'écriture** spécifiques à son type

Elle ne fait **pas** de recherche extensive. Elle prend le contexte pour acquis et se concentre sur la rédaction.

### Skills

| Skill | Rôle | Tier |
|-------|------|------|
| `gather-context` | Rassembler tout ce que le vault sait sur un sujet donné | — (lecture seule) |
| `ingest-video` | Orchestrer l'ingestion d'un transcript | — (orchestration) |
| `ingest-batch` | Ingérer plusieurs transcripts par sujet pour cohérence maximale | — (orchestration) |
| `synthesize-couche` | Orchestrer la création/enrichissement d'une fiche couche à partir d'un batch | — (orchestration) |
| `write-video` | Rédiger/enrichir une fiche `Videos/` | basic |
| `write-entity` | Rédiger/enrichir une fiche `Individus/` ou `Organisations/` | basic |
| `write-concept` | Rédiger/enrichir une fiche `Concepts/` | basic |
| `write-evenement` | Rédiger/enrichir une fiche `Evenements/` | basic |

Les skills `write-*` correspondant aux **couches advanced** d'une source (Enjeux, Conjonctures, Possibles, Methodes…) sont définies dans `Sources/<NomSource>/Skills/`. Leur format dépend de la grille analytique de la source — WikiPol ne fournit pas de squelette générique. `synthesize-couche` les invoque par convention de nom (`write-<couche>`).

Une skill `write-*` ne doit s'exécuter que si son type est activé dans `content_types` du `source.yaml` actif (voir « Classification des types de contenu » ci-dessous). Si elle est invoquée pour un type désactivé, elle interrompt et signale à l'appelant de réactiver le type ou de choisir une autre skill.

---

## Classification des types de contenu

Trois tiers structurent les fiches du vault. La distinction conditionne **quand** une fiche est créée et **par quoi** elle est créée.

### Raw (brut)

Données captées hors analyse de la source. Servent de matière première à l'ingestion.

- **Transcripts** — transcripts `.md` des médias source (vidéos YouTube, podcasts, articles transcrits). Stockés sous `Sources/Transcripts/`.

### Basic (atomique)

Créés **pendant l'ingestion d'un transcript**, fiche par fiche, à partir de ce que la source dit. Atomiques, factuels, directement extraits.

- **Individus** — personnes mentionnées et analysées par la source.
- **Organisations** — partis, médias, associations, États, etc.
- **Concepts** — outils analytiques mobilisés par la source (mécanismes, grilles de lecture, terminologie).
- **Videos** — fiche par vidéo ingérée (cas standard : analyse, commentaire d'actualité).
- **Evenements** — occurrences singulières datées que la source analyse (élection, manifestation, vote, sommet, attentat).

Une source peut introduire d'autres types basic spécifiques à son format (ex : `Livres` pour une source qui chronique des ouvrages). Ces types vivent dans le `BUILD.md` de la source — pas ici.

### Advanced (couches)

Construits **à partir des fiches basic existantes**, par synthèse multi-vidéos. Théoriques, prescriptifs, rarement créés en passe unique. Chaque source définit ses couches dans `Sources/<NomSource>/BUILD.md` — exemples possibles : Enjeux (combats récurrents), Conjonctures (diagnostics du moment), Possibles (trajectoires alternatives), Methodes (procédures analytiques).

Le terme **« couche »** désigne ces types advanced dans toute la documentation WikiPol (le mot est ancré dans les frontmatters et les fichiers `.base` Obsidian).

### Pourquoi cette stratification

- Les **basics** existent pour qu'on puisse en parler par wikilink — chaque fois qu'une source mentionne quelque chose qui mérite une fiche, on en crée une.
- Les **couches** existent pour qu'on puisse poser une question de synthèse au vault — « quel est le combat de la source sur X ? » → fiche d'une couche dédiée. Elles servent aussi de points d'entrée privilégiés pour l'exploration (cf. workflow `gather-context`).
- Le **raw** est ce qui rend l'ingestion auditable : on peut toujours retrouver le passage source d'une affirmation.

### Activation par source

Toutes les sources n'utilisent pas tous les types. Le fichier `Sources/<NomSource>/source.yaml` déclare ses `content_types` activés (whitelist stricte). `Scripts/new_source.py` ne crée que les dossiers correspondants ; les skills `write-*` refusent d'écrire un type désactivé.

```yaml
content_types:
  raw:
    Transcripts: true
  basic:
    Individus: true
    Organisations: true
    Concepts: true
    Videos: true
    Evenements: false
  couches:
    Enjeux: true
    Conjonctures: false
    Possibles: false
    Methodes: false
```

La sous-clé `couches:` liste les couches advanced activées par la source. Les noms y sont libres : chaque source y déclare les couches qu'elle a définies dans son `BUILD.md`.

Les sources peuvent activer un type plus tard ; il suffit d'éditer `source.yaml` et de créer le dossier (manuellement ou via un script utilitaire). Désactiver un type **n'efface pas** les fiches existantes — il bloque seulement la création de nouvelles fiches par les skills.

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
- **Vidéos** : Titre abrégé lisible (`COMMENT MELENCHON VA GAGNER EN 2027 AU SECOND TOUR.md`)

Les conventions de nommage des fiches couche (Enjeux, Conjonctures, etc.) sont définies par la source dans son `BUILD.md`.

### Wikilinks

- `[[Nom Exact du Fichier]]` sans chemin, sans `.md`
- Pour les alias : `[[Nom réel|alias affiché]]` (ex: `[[Parti Communiste Français|PCF]]`)
- Le nom du fichier = le texte du wikilink
- Chaque wikilink doit pointer vers un fichier existant. Si un lien orphelin est créé, créer au minimum une fiche ébauche.

### YAML frontmatter — règles communes

Toujours inclure au minimum :
- `type` : pour les types raw/basic universels, valeurs `vidéo`, `individu`, `organisation`, `concept`, `evenement`, `transcript`. Pour les couches advanced (`enjeu`, `conjoncture`, `possible`, `methode`, etc.) et les types basic source-spécifiques (`livre`, …), voir le `BUILD.md` de la source.
- `domaine` : 1-2 valeurs parmi celles définies dans le `BUILD.md` de la source.
- `thèmes` : liste de thèmes du vocabulaire contrôlé local (peut être vide pour les fiches squelettes).
- `skill_version` : identifiant de la skill + date (ex: `write-video-2026-04-20`).

Cette section liste, **par type**, les champs requis et optionnels pour les types raw/basic universels — c'est la référence pour les skills d'écriture **et** pour les agents qui font des recherches par grep sur le frontmatter (ex : `grep -l "type: concept"` dans `Concepts/`).

### Frontmatter par type

#### Transcript (raw)

Stockés dans `Sources/Transcripts/`. Le frontmatter est minimal car les transcripts ne sont pas indexés ni traversés par `gather-context`.

- **Requis** : `type: transcript`, `date` (date de publication du média), `youtube_id` (ou identifiant équivalent pour la plateforme source).
- **Optionnels** : `titre_video` (si différent du basename), `aliases`.

```yaml
---
type: transcript
date: 2025-07-30
youtube_id: "XXXXXXXXXXX"
---
```

#### Vidéo (basic)

Stockés dans `Videos/`. Cas par défaut produit par `write-video`.

- **Requis** : `type: vidéo`, `domaine`, `thèmes`, `date`, `youtube_id`, `skill_version`.
- **Optionnels** : `aliases`.
- **Champs de référence vers les couches** : le frontmatter peut contenir des champs qui pointent vers les couches advanced de la source (par convention : nom de la couche au pluriel, ex. `enjeux:`, `methodes:`, `conjonctures:`, `possibles:`). Ces champs permettent un grep depuis les couches vers les vidéos qui les mobilisent (et alimentent les vues `.base` Obsidian). La liste précise de ces champs est définie par chaque source dans son `BUILD.md`.

```yaml
---
type: vidéo
domaine: [politique-intérieure]
thèmes: [élections]
enjeux: [union-populaire]
date: 2025-07-30
youtube_id: "XXXXXXXXXXX"
skill_version: write-video-2026-04-20
aliases: [Titre alternatif]
---
```

#### Individu (basic)

Stockés dans `Individus/`. Produits par `write-entity`.

- **Requis** : `type: individu`, `domaine`, `thèmes`, `skill_version`.
- **Optionnels** : `aliases` (très recommandé pour gérer accents et variantes de nom).

```yaml
---
type: individu
domaine: [politique-intérieure]
thèmes: [élections, guerre-des-gauches]
aliases: [François Hollande]
skill_version: write-entity-2026-04-20
---
```

#### Organisation (basic)

Stockés dans `Organisations/`. Produits par `write-entity`.

- **Requis** : `type: organisation`, `domaine`, `thèmes`, `skill_version`.
- **Optionnels** : `aliases`.

```yaml
---
type: organisation
domaine: [politique-intérieure]
thèmes: []
aliases: [PS, Parti Socialiste]
skill_version: write-entity-2026-04-20
---
```

#### Concept (basic)

Stockés dans `Concepts/`. Produits par `write-concept`.

- **Requis** : `type: concept`, `domaine`, `thèmes`, `skill_version`.
- **Optionnels** : `aliases`.

```yaml
---
type: concept
domaine: [théorie]
thèmes: [élections]
aliases: [Saint Graphique, Le Graphique]
skill_version: write-concept-2026-04-20
---
```

Une source peut ajouter ses propres champs (ex : `couche:` pour marquer un concept comme relevant d'une couche advanced via une vue virtuelle). Ces extensions sont documentées dans le `BUILD.md` de la source.

#### Evenement (basic)

Stockés dans `Evenements/`. Produits par `write-evenement`. Une fiche Evenement existe pour un fait daté **analysé en profondeur** par la source — pas pour chaque date mentionnée.

- **Requis** : `type: evenement`, `domaine`, `thèmes`, `date_debut`, `skill_version`.
- **Optionnels** : `date_fin` (si l'événement s'étale dans le temps), `lieu`, `acteurs` (liste de wikilinks vers Individus/Organisations principaux), `aliases`.

```yaml
---
type: evenement
domaine: [politique-intérieure]
thèmes: [élections]
date_debut: 2025-07-30
date_fin: 2025-08-02
lieu: "Paris"
acteurs: ["[[Jean-Luc Melenchon]]", "[[France Insoumise]]"]
skill_version: write-evenement-2026-04-26
---
```

Organisable par période en sous-dossiers (ex: `Evenements/2026/`, `Evenements/1950-1979/`) si le volume le justifie.

#### Couches advanced — frontmatter

Les frontmatters des fiches couche (Enjeu, Conjoncture, Possible, Methode, etc.) sont définis par chaque source dans `Sources/<NomSource>/BUILD.md`. WikiPol n'impose pas de schéma — seulement les règles communes (`type`, `domaine`, `thèmes`, `skill_version`).

### Hashtags inline

Après le frontmatter YAML, les fiches incluent une ligne de hashtags structurés avant le titre `# Titre` :

```
#domaine/valeur #thème/valeur
```

Inclure au minimum domaine et thèmes (pas format ni statut). Une source peut ajouter d'autres axes selon sa taxonomie locale (ex : `#enjeu/valeur`, `#méthode/valeur`). Ces hashtags matérialisent les tags comme nœuds du graphe Obsidian.

### Taxonomie des tags

2 axes universels structurent le tagging :

1. **domaine** — champ d'analyse (liste finie, définie par la source)
2. **thèmes** — sujets spécifiques récurrents (vocabulaire contrôlé, extensible par la source)

Une source peut ajouter d'autres axes (ex : `enjeux` pour des combats récurrents). Les valeurs concrètes de ces axes sont déclarées dans `Sources/<NomSource>/BUILD.md`. Elles croissent **par induction** au fil des ingestions : ajouter un nouveau thème si un sujet revient dans 2+ vidéos, etc.

### Sourcing YouTube

Les fiches vidéo incluent un lien YouTube embarqué en haut (avant le résumé) et des notes de bas de page avec timestamps pour sourcer les points clés.

**Lien embarqué** (en haut de chaque fiche vidéo, après les hashtags, avant le `# Titre`) :
```markdown
![TITRE](https://www.youtube.com/watch?v=YOUTUBE_ID)
```

Obsidian reconnaît cette syntaxe image pointant vers une URL YouTube et affiche un lecteur embarqué. Ne **pas** utiliser de thumbnail cliquable via `img.youtube.com` — cette forme donne une image statique sans lecteur.

**Notes de bas de page avec timestamp** (dans le corps des fiches — vidéos, entités, concepts, fiches couche) :
```markdown
La source affirme que X est structurellement incapable de Y[^1].

[^1]: [12:34](https://www.youtube.com/watch?v=YOUTUBE_ID&t=754) — "citation exacte ou résumé du passage"
```

Le `youtube_id` est stocké dans le frontmatter de la fiche vidéo. Pour convertir un timestamp `MM:SS` en secondes, utiliser le helper `Scripts/timestamp_to_seconds.py`.

Pour les fiches non-vidéo (entités, concepts, fiches couche), les footnotes référencent la vidéo source via son `youtube_id` — récupéré depuis la fiche vidéo correspondante.

### Style

- Phrases courtes, pas de remplissage
- Ton analytique, pas encyclopédique
- Fidélité à l'analyse de la source — restituer, pas neutraliser

Les principes éditoriaux spécifiques (restituer sans challenger, nuancer, contextualiser, etc.) sont définis dans `Sources/<NomSource>/CLAUDE.md` selon la nature de la source.

### Volume

Être ambitieux dans la création de fiches. Chaque personne mentionnée significativement, chaque organisation citée, chaque mécanisme analytique décrit mérite sa fiche. Il vaut mieux créer une fiche minimale (ébauche) que de laisser un lien orphelin.

---

## Workflow git

Chaque source est versionnée dans son propre dépôt GitHub (paramètre `git.repo` dans `source.yaml`). WikiPol — l'ossature — est versionné dans un dépôt distinct, et les sources sont rattachées comme submodules.

### Branches

```
main              ← production (publication du wiki)
 └── develop      ← intégration et travail courant
```

- **`main`** : état publié du wiki. Jamais de push direct — promu depuis `develop` par l'utilisateur.
- **`develop`** : branche unique de travail. Les ingestions, synthèses et corrections committent **directement** sur `develop`. Pas de branches éphémères, pas de PR internes, pas de merges `--no-ff`.

### En début d'ingestion ou de synthèse

1. Se placer sur `develop` à jour : `git checkout develop && git pull origin develop`

### En fin d'ingestion ou de synthèse

1. Stage les fichiers modifiés/créés par nom (pas `git add -A`)
2. Commit avec message structuré :
   ```
   ingest: TITRE ABRÉGÉ DE LA VIDÉO

   Fiches créées: X (liste)
   Fiches enrichies: Y (liste)
   Corrections ortho: Z (liste si applicable)

   Co-Authored-By: Claude <noreply@anthropic.com>
   ```
   Préfixes selon le type d'opération :
   - `ingest: …` pour une ingestion unitaire (1 vidéo)
   - `ingest-batch: …` pour un batch d'ingestion
   - `synthesize: COUCHE — Nom cible` pour une synthèse de fiche couche
3. Push direct : `git push origin develop`

---

## Chemins d'un vault source

```
Sources/<NomSource>/
├── CLAUDE.md                     ← contexte éditorial de la source
├── BUILD.md                      ← taxonomie locale + spécifications des couches
├── source.yaml                   ← config paramétrique (content_types, git, model)
├── Skills/                       ← (optionnel) skills propres à la source qui surchargent
│   └── <skill-name>/SKILL.md     ←   les skills génériques de WikiPol/Skills/
├── Sources/
│   ├── Inventaire.md             ← table des vidéos (Dataview)
│   └── Transcripts/              ← transcripts bruts (.md) — type raw
├── Syntheses/                    ← (optionnel) batch files de synthèse pour synthesize-couche
├── Videos/                       ← basic (cas standard)
├── Individus/                    ← basic
├── Organisations/                ← basic
├── Concepts/                     ← basic
├── Evenements/                   ← basic (optionnel ; sous-dossiers par période possibles)
├── Enjeux/                       ← couche advanced (optionnel)
├── Conjonctures/                 ← couche advanced (optionnel)
├── Possibles/                    ← couche advanced (optionnel)
├── Methodes/                     ← couche advanced (optionnel)
└── <SLUG>_CHRONOLOGIQUE.md       ← fichier de suivi d'ingestion batch
```

Les dossiers marqués « optionnel » ne sont créés que si activés dans `source.yaml:content_types`. Une source peut introduire d'autres dossiers (ex : `Livres/` pour une source qui chronique des ouvrages) — documentés dans son `BUILD.md`.
