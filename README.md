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

Ajoutez votre e-mail dans les secrets :

```toml
ADMIN_EMAILS = ["vous@votre-domaine.com"]
```

Depuis ce tableau de bord vous pouvez consulter tous les comptes inscrits, voir les tokens consommés par utilisateur, suivre l'activité (inscriptions, analyses, consommation IA) et supprimer un compte.

Si vous lancez l'API (`python scripts/run_api.py`), le même espace est servi sur `http://localhost:8000/dashboard`.

## Tests

## Tests

```bash
python -m pytest tests/
```

## Configuration

Copiez `.streamlit/secrets.toml.example` vers `.streamlit/secrets.toml` et renseignez vos clés (base de données, IA, moteurs d'emploi, e-mail).
