# DowsonBost

Plateforme de recherche d'emploi et matching CV par intelligence artificielle.

## Fonctionnalités

- Connexion / inscription avec profil de recherche
- Analyse de CV (PDF) et matching ATS avec les offres
- Tableau de bord candidatures et historique
- Recherche automatique planifiée (cron)
- API REST (`api/main.py`)

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

## Tests

```bash
python -m pytest tests/
```

## Configuration

Copiez `.streamlit/secrets.toml.example` vers `.streamlit/secrets.toml` et renseignez vos clés (base de données, IA, moteurs d'emploi, e-mail).
