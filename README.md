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

## Configuration

Copiez `.streamlit/secrets.toml.example` vers `.streamlit/secrets.toml` et renseignez vos clés (base de données, IA, moteurs d'emploi, e-mail).
