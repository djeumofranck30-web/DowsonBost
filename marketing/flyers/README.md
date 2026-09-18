# Flyers DowsonBost

Dix flyers A4 (210 × 297 mm) pour imprimer, afficher ou poster.

Identité reprise de l’app : teal `#0E7490`, or `#E8B923`, crème `#F4F1EA`, marine `#0B1220`.
URL et QR : [dowsonbost.streamlit.app](https://dowsonbost.streamlit.app).

## Fichiers à imprimer

| Fichier | Usage |
| --- | --- |
| `png/01-hero.png` | Accroche générale — « Trouvez le poste qui vous ressemble » |
| `png/02-ats.png` | Argument ATS / score de compatibilité |
| `png/03-lifestyle.png` | Photo café — usage quotidien |
| `png/04-cv-sur-mesure.png` | CV une page + lettre |
| `png/05-reconversion.png` | Mobilité et reconversion |
| `png/06-fonctions.png` | Six fonctions de la plateforme |
| `png/07-cent-offres.png` | Profondeur 25 / 60 / 100 |
| `png/08-paris.png` | Hébergement Paris / UE |
| `png/09-parcours.png` | Parcours en 4 étapes |
| `png/10-affiche-qr.png` | Affiche A4 à scanner (gros QR) |

Les PDF du même nom sont dans `pdf/` (A4, 300 dpi environ).

Les sources HTML sont dans `html/` : changez un texte, puis :

```bash
python3 marketing/flyers/render.py
```

Chrome headless est requis (`google-chrome`).

Police **Inter** (SIL Open Font License) incluse dans `assets/fonts/`.
