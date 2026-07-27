---
marp: true
theme: default
paginate: true
size: 16:9
footer: "Bluesky iPhone Posts — Pipeline serverless & dashboard"
style: |
  section {
    font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
    padding: 56px 72px;
    color: #262a33;
  }
  h1 {
    color: #1c5399;
    font-size: 1.7em;
    border-bottom: 4px solid #2a78d6;
    padding-bottom: 0.2em;
  }
  h2 { color: #2a78d6; }
  section.lead {
    background: linear-gradient(135deg, #eef4fd 0%, #ffffff 60%);
  }
  section.lead h1 {
    font-size: 2.4em;
    border-bottom: none;
    color: #1c5399;
  }
  section.lead h2 {
    color: #5b6270;
    font-weight: 400;
    font-size: 1.1em;
  }
  table { font-size: 0.78em; }
  th { background-color: #eef4fd; color: #1c5399; }
  img[alt~="full"] {
    display: block;
    margin: 0 auto;
  }
  .columns {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 1.6em;
  }
  footer { color: #9aa1ad; font-size: 0.55em; }
---

<!-- _class: lead -->

# Bluesky iPhone Posts

## Pipeline serverless & dashboard — Terraform + Scaleway

Observer en temps quasi-réel ce qui se dit sur l'iPhone sur Bluesky, sans gérer le moindre serveur.

---

# Le contexte

- Bluesky expose une API de recherche publique — on peut y chercher tous les posts contenant un mot-clé.
- **Idée** : suivre en continu les posts mentionnant *"iphone"*, les classer par thème et visualiser les tendances.
- **Contrainte** : tout doit tourner en **serverless** — pas de VM à gérer, coût quasi nul à l'arrêt.
- **Résultat** : un pipeline de collecte → classification IA → stockage → API → dashboard, entièrement défini en Terraform.

---

# Vue d'ensemble

![full](assets/architecture.png)

Quatre briques, toutes provisionnées par Terraform et hébergées sur **Scaleway**.

---

# Les 4 briques du pipeline

<div class="columns">
<div>

**1. `code/load_data`**
Job cron horaire : recherche Bluesky → classification LLM → écriture en base.

**2. `terraform/db.tf`**
Base PostgreSQL Serverless, seule source de vérité.

</div>
<div>

**3. `code/function`**
Function serverless, seule à parler à la base, expose une API JSON déjà agrégée.

**4. `code/dashboard`**
Container Streamlit, consomme l'API et affiche les graphiques.

</div>
</div>

---

# 1 · Collecte & classification

`code/load_data/main.py` — exécuté comme **Job Scaleway**, cron `0 * * * *` (toutes les heures)

- Connexion à Bluesky (`atproto`) avec un compte applicatif dédié.
- Recherche jusqu'à **500 posts récents** contenant *"iphone"* (dernière heure).
- Chaque texte est envoyé à un **LLM** (`groq/openai/gpt-oss-20b`, endpoint compatible OpenAI) avec 10 catégories candidates : rumeur produit, publicité, plainte, anecdote, humour, comparatif, bug technique, neutre, hors-sujet…
- Le post (auteur, texte, catégorie, date) est stocké en PostgreSQL via **Peewee**.
- Une erreur de classification sur un post n'interrompt pas les suivants.

---

# 2 · Stockage

`terraform/db.tf` — **Scaleway Serverless SQL Database** (PostgreSQL)

- Autoscaling **0 → 8 CPU** : rien ne tourne (donc ne coûte rien) en dehors des accès.
- Un compte IAM applicatif dédié (`db_app`) avec une policy `ServerlessSQLDatabaseReadWrite`.
- Sa clé API sert à construire l'URL de connexion, réutilisée :
  - par la **Function**, pour la lecture,
  - par le **Job**, pour l'écriture (injectée comme secret Scaleway).
- Une seule table : `Post(id, author_handle, text, category, posted_at)`.

---

# 3 · API d'agrégation

`code/function/function/handler.py` — **Scaleway Serverless Function**, seule à détenir l'accès à la base

| Route | Rôle |
|---|---|
| `GET /` | healthcheck |
| `GET /stats/bounds` | dates min/max des posts en base |
| `GET /stats?since&until` | comptage par catégorie, répartition par longueur, top emojis |

Tout le calcul lourd (parcours des lignes, comptage, regex emojis) se fait **côté serveur** : le dashboard ne reçoit jamais les posts bruts, seulement du JSON déjà agrégé.

---

# 4 · Dashboard

`code/dashboard/app.py` — **Streamlit**, déployé comme **Scaleway Container** (scale 0 → 1)

- Slider de période (`/stats/bounds`) puis appel `/stats` (cache 60 s).
- Camembert des catégories, histogramme empilé par longueur, emojis préférés — 8 catégories gardent une couleur fixe, le reste est replié sous *"autre"*.

![full w:580](assets/dashboard_mock.png)

---

# Infrastructure as Code

Tout le déploiement est décrit dans `terraform/`, provider officiel `scaleway/scaleway` :

| Fichier | Rôle |
|---|---|
| `db.tf` | Provider, base PostgreSQL, IAM de connexion |
| `registry.tf` | Registre de containers privé (images Job + Dashboard) |
| `function.tf` | Build des dépendances Python, zip, déploiement Function |
| `dashboard.tf` | Build & push image Docker, déploiement Container |
| `job.tf` | Build & push image Docker, Job + cron horaire + secrets |
| `secrets.tf` | Secrets Scaleway référencés par le Job |
| `outputs.tf` | URL Function, URL Dashboard, connection string |

---

# Auto-rebuild à chaque changement

- Chaque brique buildable (Function, Job, Dashboard) calcule un **hash SHA-256** du contenu de son dossier de code.
- Ce hash sert de `trigger` à un `null_resource` (ou d'input à `archive_file` pour la Function).
- Résultat : modifier un fichier source suffit — un simple **`terraform apply`** reconstruit et republie l'image ou le zip concerné.
- Pas de pipeline CI/CD externe nécessaire pour un projet de cette taille.

---

# Développement local

- **Function** : `code/function/local_server.py` — serveur HTTP stdlib qui simule les events Scaleway, pour tester `handler.py` sans déployer.
- **Function (packaging manuel)** : `code/function/package.sh` — reconstruit `function.zip` avec les dépendances compilées dans l'image Docker officielle du runtime, déploie via `scw function deploy`.
- **Dashboard / Job** : chacun a son `Dockerfile`, buildable indépendamment (`docker build code/dashboard`, `docker build code/load_data`).

---

# Stack technique

<div class="columns">
<div>

**Infra & compute**
- Terraform (`scaleway/scaleway`)
- Scaleway Serverless Functions
- Scaleway Containers
- Scaleway Serverless Jobs (cron)

**Données**
- Scaleway Serverless SQL Database (PostgreSQL)
- ORM Peewee

</div>
<div>

**Intelligence**
- LLM via API compatible OpenAI (SDK `openai`)

**Source & visualisation**
- API Bluesky (`atproto`)
- Streamlit + Plotly

</div>
</div>

---

<!-- _class: lead -->

# Merci

Code, Terraform et README complet : dépôt `proj-terraform`
