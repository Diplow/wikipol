---
name: gather-context
description: >
  Rassemble ce que le vault (une source WikiPol) sait déjà sur un sujet et produit une synthèse
  dense + une carte de liens vers les fiches pertinentes. Démarre par les couches advanced
  (Enjeux, Conjonctures, Possibles, Methodes…) qui sont les points d'entrée naturels du graphe,
  puis rebondit vers les basics. Toujours appelée en amont des skills write-* — les write-* ne
  doivent jamais tenter de faire ce travail elles-mêmes. Déclencher quand une skill d'écriture
  va être lancée, ou quand l'utilisateur demande "quel contexte on a sur X", "qu'est-ce qu'on
  sait de X", "rassemble les infos sur X".
date created: Sunday, April 12th 2026, 6:45:00 pm
date modified: 2026-05-01
---

# Skill : Gather Context

## Vue d'ensemble

Cette skill prend un **sujet** (nom d'une fiche couche, concept, individu, organisation, thème de vidéo, ou question libre) et produit une **synthèse dense** (jusqu'à ~50K tokens) directement consommable par les skills `write-*` ou par l'utilisateur. Le fichier produit contient :

1. Une **présentation** courte du sujet (1-3 paragraphes)
2. Une **synthèse étendue** (le gros du fichier) — récit articulé qui restitue les positions, arguments, mécanismes, exemples des fiches lues
3. Une **carte de liens** vers les fiches pertinentes par catégorie

Le fichier est destiné à être consommé tel quel : la skill appelante n'a plus à explorer le vault.

## Principe

`.context-tmp.md` est **une vraie synthèse**, pas un dump mécanique ni un index minimaliste. Il doit pouvoir tenir lieu de note de cadrage pour rédiger une fiche : on y trouve les faits, les positions de la source, les connexions entre objets, les exemples saillants. Les fiches lues ne sont pas recopiées en intégralité — elles sont synthétisées et reliées.

Les **couches advanced** (Enjeux, Conjonctures, Possibles, Methodes, etc., selon la source) sont les **points d'entrée privilégiés** du graphe : elles agrègent par construction ce qui structure la pensée de la source. La skill commence donc toujours par interroger les couches activées avant de descendre vers les basics.

## Contexte éditorial de la source

Le ton et les principes de restitution (fidélité, critique, neutre…) sont définis dans le `CLAUDE.md` de la source active (`Sources/<NomSource>/CLAUDE.md`). Ce fichier dit comment formuler la présentation et la synthèse : c'est lui qui détermine si on écrit "la source affirme que X" ou "X est factuellement Y".

---

## Entrée

Un sujet, fourni sous l'une de ces formes :
- Nom d'une fiche existante (ex: un Enjeu, un Individu, un Concept, une fiche couche)
- Thème transversal
- Titre ou sujet d'une vidéo à ingérer
- Question libre

## Sortie

Un fichier temporaire **`Sources/<NomSource>/.context-tmp.md`** (ignoré par le `.gitignore` de la source) contenant la synthèse + la carte de liens. Ce fichier est écrasé à chaque appel.

La détection de la source active se fait via le cwd (remontée jusqu'à `source.yaml`) ou via `Scripts/source_config.py`.

---

## Workflow

### Étape 0 — Détecter la source et les couches activées

1. Lire `Sources/<NomSource>/source.yaml` pour récupérer la liste des couches activées (`content_types.couches`). C'est cette liste qui guide les recherches de l'étape 1 — pas une liste fixe.
2. Lire `Sources/<NomSource>/BUILD.md` (section sur les couches) pour connaître les conventions locales (champs frontmatter, sémantique de chaque couche).

### Étape 1 — Couches advanced en priorité

Pour chaque couche activée par la source :

1. Chercher les fiches de cette couche dont le sujet est central :
   - Match exact du basename de fiche
   - Match dans les `aliases` du frontmatter
   - Grep dans le titre et le corps
   - Match dans les champs de référence frontmatter (ex : une vidéo qui liste cette couche dans son frontmatter pointe vers une fiche couche pertinente)
2. **Lire en entier** les fiches couche les plus pertinentes (typiquement 1-5). Elles agrègent par construction les positions de la source sur le sujet.
3. Si le sujet correspond à plusieurs couches, lire dans toutes les couches activées (ex : un sujet peut toucher un Enjeu *et* une Conjoncture).

### Étape 2 — Basics rebondis depuis les couches

Depuis les wikilinks trouvés dans les fiches couche lues à l'étape 1 :

1. Identifier les Individus, Organisations, Concepts, Vidéos qui reviennent (ceux qui apparaissent dans 2+ fiches couche lues, ou ceux qui sont marqués comme centraux par leur position dans les fiches).
2. Lire les fiches basic correspondantes — en entier pour les plus structurantes, en survol pour les autres.
3. Pour les Vidéos : lire les fiches Vidéos dont le frontmatter référence le sujet (champ couche au pluriel — ex. `enjeux: [Sujet]`, `methodes: [Sujet]`).

**Critère d'arrêt** : ~30-50 fiches lues maximum. Au-delà, la synthèse perd en cohérence. Si le sujet est tellement transversal que ce volume sature, raffiner le sujet avant de continuer.

### Étape 3 — Grep complémentaire

La recherche par fiches et wikilinks ne trouve que ce qui est déjà explicitement lié. Pour découvrir des connexions non encore formalisées :

1. **Mots-clés du sujet** : générer 5-10 mots-clés et synonymes liés au sujet (incluant noms propres, expressions canoniques de la source, surnoms ou périphrases récurrentes).
2. **Grep dans les fiches** uniquement — couches activées + `Individus/`, `Organisations/`, `Concepts/`, `Videos/`, `Evenements/`. **Ne pas grep les transcripts** : ils ne sont pas lus à cette étape, et leur rôle (source brute) ne les qualifie pas pour construire la synthèse.
3. **Évaluer les pistes** : parmi les résultats grep, identifier les fiches qui n'étaient pas déjà trouvées aux étapes 1-2. Les lire si elles semblent apporter un angle nouveau.

Cette étape est particulièrement utile pour :
- Les sujets transversaux qui touchent beaucoup de fiches sans y être centraux
- Les connexions non formalisées (un concept utilisé dans une vidéo mais pas encore lié à une fiche couche)

### Étape 4 — Écrire le fichier `.context-tmp.md`

Écrire `Sources/<NomSource>/.context-tmp.md` avec la structure suivante. **La synthèse étendue est le cœur du fichier** : elle peut occuper l'essentiel des ~50K tokens autorisés. Ne pas s'auto-censurer pour rester court — une synthèse trop sommaire force l'appelant à relire les fiches.

```markdown
# Contexte : {SUJET}

Généré le {DATE} par gather-context — source : {NomSource}.

## Présentation

{1-3 paragraphes synthétisant :
- les faits essentiels du sujet (ce qu'il est, son cadre temporel, les acteurs en jeu)
- la position globale de la source (combat, grilles de lecture mobilisées)
Ton : voir CLAUDE.md de la source. Pas de citation longue ici — c'est une accroche.}

## Synthèse

{Récit articulé qui couvre les axes principaux du sujet — la part la plus dense du fichier.
Organiser par sous-sections selon ce qui structure le sujet (axes thématiques, acteurs,
chronologie, mécanismes…). Pour chaque axe :
- Restituer les positions et arguments clés des fiches lues
- Citer les exemples saillants (avec wikilinks vers les fiches d'origine)
- Connecter aux concepts, méthodes, conjonctures, événements pertinents
- Quand la source a une analyse spécifique d'un objet, la rendre — ne pas neutraliser
- Quand des fiches lues se contredisent ou divergent, le signaler

C'est ici qu'on consolide ce que le vault dit collectivement sur le sujet. Il ne s'agit pas
de recopier les fiches mais d'en extraire la trame analytique. Wikilinks abondants pour
permettre à l'appelant d'aller au détail si nécessaire.}

## Fiches liées

### Couches
- [[Nom Fiche Couche]] — {1 ligne sur son rapport au sujet}

### Vidéos
- [[Vidéo 1]] — {angle sous lequel elle traite le sujet}

### Concepts
- [[Concept X]] — {rapport, 1 ligne}

### Individus
- [[Personne Y]] — {rapport, 1 ligne}

### Organisations
- [[Org Z]] — {rapport, 1 ligne}

### Evenements
- [[Evenement W]] — {rapport, 1 ligne}
```

Règles de forme :

- **Omettre une sous-section vide.** Si le sujet n'a pas de fiche de telle couche, ne pas la lister.
- **Annotations informatives.** L'annotation d'un lien répond à « pourquoi cette fiche pour ce sujet ? ». Pas de tautologie (« Concept X → parle de X »), pas de résumé — une indication de rapport.
- **Wikilinks dans le corps.** Les wikilinks dans la « Synthèse » sont aussi importants que ceux du « Fiches liées ». Ils permettent de naviguer en lecture.
- **Volume.** Cible ~30K tokens, plafond ~50K. La synthèse doit être assez dense pour rendre les fiches d'origine optionnelles à relire — mais pas un copier-coller.

### Étape 5 — Inviter l'appelant à lire

Au lieu de produire un résumé verbal, simplement signaler que `Sources/<NomSource>/.context-tmp.md` est prêt et inviter l'appelant à le lire intégralement avant la suite de son travail.

---

## Règles

- **Ne pas modifier le vault.** Cette skill est en lecture seule — elle ne crée ni ne modifie aucune fiche. Elle écrit uniquement `.context-tmp.md`.
- **Ne pas lire les transcripts.** Les transcripts sont la source brute des fiches vidéo. Leur rôle est en amont (ingestion). Pour le contexte, gather-context se concentre sur les fiches déjà produites.
- **Couches d'abord, basics ensuite.** L'ordre des étapes 1 → 2 → 3 n'est pas négociable. Les couches sont les points d'entrée pensés pour ça par construction. Sauter l'étape 1 produit une synthèse plate qui rate l'analyse de la source.
- **Synthèse, pas dump.** Le fichier `.context-tmp.md` n'est pas une concaténation de fiches. Il en extrait la trame analytique. Si on se contente de copier-coller, l'appelant ferait aussi bien de lire les fiches directement — la skill ne sert plus.
- **Fidélité au ton de la source.** Voir `CLAUDE.md` de la source. Ne pas neutraliser ni encyclopédiser une analyse polémique.
