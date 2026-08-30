# DowsonBost

Plateforme de recherche d'emploi et matching CV par intelligence artificielle.

## Fonctionnalités

- Connexion / inscription avec profil de recherche
- Analyse de CV (PDF) et matching ATS avec les offres
- Tableau de bord candidatures et historique
- Recherche automatique planifiée (cron)
- API REST (`api/main.py`)
- Espace administrateur (`/dashboard`) : comptes, tokens IA, graphiques d'activité

## Lancer l'application

```bash
pip install -r requirements.txt
streamlit run app.py
```

## API REST

```bash
pip install -r requirements.txt
python scripts/run_api.py
```

Documentation : http://localhost:8000/docs

## Espace administrateur

URL Streamlit Cloud : `https://dowsonbost.streamlit.app/dashboard`

Ajoutez **l'e-mail et le mot de passe admin** dans les secrets Streamlit Cloud (Settings → Secrets). Seuls ces identifiants ouvrent le dashboard :

```toml
ADMIN_EMAIL = "vous@votre-domaine.com"
ADMIN_PASSWORD = "choisissez-un-mot-de-passe-fort"
```

Plusieurs administrateurs :

```toml
ADMIN_EMAILS = ["vous@domaine.com", "autre@domaine.com"]
ADMIN_PASSWORDS = ["mot-de-passe-1", "mot-de-passe-2"]
```

Ce mot de passe admin est indépendant des comptes candidats. Après modification des secrets, faites un **Reboot** de l'application.

Depuis ce tableau de bord vous pouvez consulter tous les comptes inscrits, voir les tokens consommés par utilisateur, suivre l'activité (inscriptions, analyses, consommation IA) et supprimer un compte. Le panneau **Configuration & tests** est aussi réservé à cet espace.

Si vous lancez l'API (`python scripts/run_api.py`), le même espace est servi sur `http://localhost:8000/dashboard`.

## Tests

```bash
python -m pytest tests/
```

## Héberger à Paris (Union européenne)

Vous vivez à Paris : **l'appli et la base tournent à Paris**, pas à Londres (hors UE) ni aux États-Unis (Streamlit Cloud).

| Élément | Aujourd'hui | Cible Paris |
| --- | --- | --- |
| Application | Streamlit Cloud (souvent USA) | Fly.io **Paris CDG** (`cdg`) |
| Base Postgres | Supabase **Londres** (`eu-west-2`) | Nouveau projet Supabase **Paris** (`eu-west-3`) |

Les appels IA (Groq, Gemini, OpenAI) et Adzuna/Jooble restent chez ces fournisseurs — on ne peut pas les déplacer. Comptes, CV, analyses et pages sont servis depuis Paris.

### 1. Recréer la base à Paris

Supabase ne permet pas de changer la région d'un projet. Il faut un **nouveau** projet :

1. [supabase.com](https://supabase.com) → New project → région **West EU (Paris)** / `eu-west-3`
2. Connect → **Session pooler** (port **5432**)
3. Exportez l'ancien projet (SQL Editor ou `pg_dump`) et importez-le dans le nouveau
4. Mettez à jour `DATABASE_URL` / `DATABASE_PASSWORD`

### 2. Lancer l'appli à Paris — Fly.io `cdg`

1. Installez le CLI : https://fly.io/docs/flyctl/install/
2. `fly auth login`
3. Dans ce dépôt : `fly launch --copy-config --no-deploy`  
   Si le nom `dowsonbost` est pris, changez `app` dans `fly.toml`.
4. Recopiez **les mêmes secrets** que Streamlit Cloud, avec la **nouvelle** URL Paris :

```bash
fly secrets set \
  DATABASE_URL="postgresql://postgres.xxxxx@aws-0-eu-west-3.pooler.supabase.com:5432/postgres" \
  DATABASE_PASSWORD="..." \
  APP_BASE_URL="https://dowsonbost.fly.dev" \
  GROQ_API_KEY="..." \
  GEMINI_API_KEY="..." \
  ADZUNA_APP_ID="..." \
  ADZUNA_APP_KEY="..." \
  ADMIN_EMAIL="..." \
  ADMIN_PASSWORD="..."
```

`DATABASE_POOL_MODE=session` est déjà dans `fly.toml` : même si vous collez encore l'URL en `:6543`, l'app passe toute seule sur le port **5432**.

5. `fly deploy`
6. Ouvrez l'URL Fly, testez connexion + une page du tableau de bord.
7. Quand c'est bon : mettez `APP_BASE_URL` et `CAREERJET_REFERER` à la nouvelle URL. Streamlit Cloud peut rester en secours jusqu'au basculement.

La machine **ne s'arrête pas** (`auto_stop_machines = "off"`, `min_machines_running = 1`) pour éviter le réveil de plusieurs secondes.

Le cron GitHub Actions tourne sur des serveurs GitHub (souvent hors UE). Pour rester à Paris, désactivez-le et lancez `python scripts/run_scheduled_search.py` une fois par jour sur la machine Paris.

### 3. Alternative — VPS OVH en France (Docker)

Fly `cdg` est à Paris. Un VPS OVH (Gravelines / Roubaix / Strasbourg) reste en France si vous préférez un hébergeur français.

```bash
# Créez un fichier .env avec les mêmes KEY=value que les secrets Streamlit
docker compose up -d --build
```

L'analyse CV et les appels Adzuna / Jooble / IA restent limités par ces APIs : changer d'hébergeur accélère surtout **la navigation** (chargement des pages, clics, tableau de bord).


## Configuration

Copiez `.streamlit/secrets.toml.example` vers `.streamlit/secrets.toml` et renseignez vos clés (base de données, IA, moteurs d'emploi, e-mail).
