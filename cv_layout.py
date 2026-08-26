"""Profession-specific CV templates: detect the job family, parse content, render PDF/HTML."""

from __future__ import annotations

import html
import re
import unicodedata
from dataclasses import dataclass, field, replace
from typing import Any

from fpdf import FPDF

# ---------------------------------------------------------------------------
# Latin-1 helpers for fpdf2 core fonts
# ---------------------------------------------------------------------------

_PDF_CHAR_REPLACEMENTS = {
    "\u2014": "-",
    "\u2013": "-",
    "\u2212": "-",
    "\u00b7": "-",
    "\u2022": "-",
    "\u2026": "...",
    "\u2019": "'",
    "\u2018": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\u00a0": " ",
    "\u202f": " ",
    "\u200b": "",
    "\u00ad": "",
    "\u2192": "->",
    "\u2190": "<-",
    "\u0152": "OE",
    "\u0153": "oe",
}


def pdf_safe_text(value: Any, default: str = "") -> str:
    """Make text safe for Helvetica/Times core fonts (Latin-1)."""
    text = str(value).strip() if value is not None else ""
    if not text:
        return default
    for src, dst in _PDF_CHAR_REPLACEMENTS.items():
        text = text.replace(src, dst)
    text = unicodedata.normalize("NFKC", text)
    return text.encode("latin-1", errors="replace").decode("latin-1")


def _fold(value: str) -> str:
    nfkd = unicodedata.normalize("NFKD", value or "")
    return "".join(ch for ch in nfkd if not unicodedata.combining(ch)).lower()


def _slug_filename(value: str, fallback: str = "document") -> str:
    folded = _fold(value)
    cleaned = re.sub(r"[^a-z0-9]+", "_", folded).strip("_")
    return (cleaned[:48] or fallback)


# ---------------------------------------------------------------------------
# Template catalogue
# ---------------------------------------------------------------------------

Rgb = tuple[int, int, int]


@dataclass(frozen=True)
class CvTemplate:
    """Visual + editorial recipe for one professional family."""

    family: str
    label_fr: str
    label_en: str
    layout: str  # banner | classic | academic
    font: str  # Helvetica | Times
    primary: Rgb
    accent: Rgb
    ink: Rgb
    muted: Rgb
    paper: Rgb
    header_text: Rgb
    chip_bg: Rgb
    chip_text: Rgb
    section_order: tuple[str, ...]
    section_titles: dict[str, str]
    llm_sections: str
    extra_section_keys: tuple[str, ...] = ()


_TEMPLATES: dict[str, CvTemplate] = {}


def _register(tpl: CvTemplate) -> CvTemplate:
    _TEMPLATES[tpl.family] = tpl
    return tpl


TPL_IT = _register(CvTemplate(
    family="it",
    label_fr="Informatique / Digital",
    label_en="IT / Digital",
    layout="banner",
    font="Helvetica",
    primary=(15, 32, 67),
    accent=(14, 165, 164),
    ink=(22, 32, 48),
    muted=(90, 104, 122),
    paper=(247, 250, 252),
    header_text=(255, 255, 255),
    chip_bg=(224, 247, 246),
    chip_text=(12, 92, 91),
    section_order=("profile", "skills", "projects", "experience", "education", "languages", "certifications"),
    section_titles={
        "profile": "PROFIL TECHNIQUE",
        "skills": "STACK & COMPÉTENCES",
        "projects": "PROJETS",
        "experience": "EXPÉRIENCES",
        "education": "FORMATION",
        "languages": "LANGUES",
        "certifications": "CERTIFICATIONS",
    },
    extra_section_keys=("projects", "certifications"),
    llm_sections=(
        "Structure CV INFORMATIQUE / DIGITAL :\n"
        "## PROFIL\n(3-4 lignes : stack, domaine, impact)\n"
        "## COMPETENCES\nlangages | frameworks | cloud | methodes (separes par | )\n"
        "## PROJETS\n- projet : role, techno, resultat\n"
        "## EXPERIENCE\nPOSTE: ...\nENTREPRISE: ...\nPERIODE: ...\nLIEU: ...\n- mission orientee produit / tech\n"
        "## FORMATION\nDIPLOME: ...\nETABLISSEMENT: ...\nPERIODE: ...\n"
        "## CERTIFICATIONS\n- AWS, Azure, Scrum... seulement si presentes dans le CV\n"
        "## LANGUES\n"
    ),
))

TPL_HEALTHCARE = _register(CvTemplate(
    family="healthcare",
    label_fr="Santé / Médical",
    label_en="Healthcare",
    layout="classic",
    font="Times",
    primary=(0, 109, 119),
    accent=(131, 197, 190),
    ink=(30, 42, 40),
    muted=(92, 110, 108),
    paper=(250, 252, 252),
    header_text=(255, 255, 255),
    chip_bg=(226, 245, 242),
    chip_text=(0, 90, 98),
    section_order=("profile", "education", "licenses", "experience", "skills", "languages"),
    section_titles={
        "profile": "PROFIL CLINIQUE",
        "education": "DIPLOMES & FORMATION",
        "licenses": "AUTORISATIONS & STAGES",
        "experience": "EXPÉRIENCES DE SOINS",
        "skills": "COMPÉTENCES CLINIQUES",
        "languages": "LANGUES",
    },
    extra_section_keys=("licenses",),
    llm_sections=(
        "Structure CV SANTE / MEDICAL :\n"
        "## PROFIL\n(discipline, patients, environnement de soins)\n"
        "## FORMATION\nDIPLOME: ...\nETABLISSEMENT: ...\nPERIODE: ...\n"
        "## AUTORISATIONS\n- numero RPPS / ADELI, ordre, stages, internat — seulement si presents\n"
        "## EXPERIENCE\nPOSTE: ...\nENTREPRISE: ... (service / hopital)\nPERIODE: ...\nLIEU: ...\n- responsabilites cliniques concretes\n"
        "## COMPETENCES\ngestes | specialites | logiciels metier\n"
        "## LANGUES\n"
    ),
))

TPL_FINANCE = _register(CvTemplate(
    family="finance",
    label_fr="Finance / Banque / Audit",
    label_en="Finance / Banking",
    layout="classic",
    font="Times",
    primary=(27, 42, 74),
    accent=(184, 148, 79),
    ink=(28, 32, 40),
    muted=(100, 104, 112),
    paper=(252, 251, 247),
    header_text=(255, 255, 255),
    chip_bg=(245, 236, 214),
    chip_text=(92, 68, 22),
    section_order=("profile", "skills", "experience", "education", "certifications", "languages"),
    section_titles={
        "profile": "PROFIL",
        "skills": "COMPETENCES",
        "experience": "EXPÉRIENCES",
        "education": "FORMATION",
        "certifications": "CERTIFICATIONS",
        "languages": "LANGUES",
    },
    extra_section_keys=("certifications",),
    llm_sections=(
        "Structure CV FINANCE / BANQUE / AUDIT :\n"
        "## PROFIL\n(perimetre, encours, normes, secteurs)\n"
        "## COMPETENCES\nIFRS | consolidation | modelisation | outils (separes par | )\n"
        "## EXPERIENCE\nPOSTE: ...\nENTREPRISE: ...\nPERIODE: ...\n- missions avec chiffres (montants, effectifs) si presents dans le CV\n"
        "## FORMATION\nDIPLOME: ...\nETABLISSEMENT: ...\nPERIODE: ...\n"
        "## CERTIFICATIONS\n- DSCG, CFA, ACCA... seulement si presentes\n"
        "## LANGUES\n"
    ),
))

TPL_LEGAL = _register(CvTemplate(
    family="legal",
    label_fr="Juridique / Droit",
    label_en="Legal",
    layout="classic",
    font="Times",
    primary=(74, 28, 40),
    accent=(140, 74, 74),
    ink=(36, 28, 28),
    muted=(110, 96, 96),
    paper=(252, 250, 248),
    header_text=(255, 255, 255),
    chip_bg=(244, 230, 230),
    chip_text=(92, 32, 40),
    section_order=("profile", "education", "experience", "skills", "languages"),
    section_titles={
        "profile": "PROFIL",
        "education": "FORMATION",
        "experience": "EXPÉRIENCES",
        "skills": "COMPÉTENCES JURIDIQUES",
        "languages": "LANGUES",
    },
    llm_sections=(
        "Structure CV JURIDIQUE :\n"
        "## PROFIL\n(branches du droit, contentieux / conseil)\n"
        "## FORMATION\nDIPLOME: CRFPA, master... \nETABLISSEMENT: ...\nPERIODE: ...\n"
        "## EXPERIENCE\nPOSTE: ...\nENTREPRISE: cabinet / direction juridique\nPERIODE: ...\n- dossiers, branches du droit, volumes si connus\n"
        "## COMPETENCES\nDroit des societes | social | contrats | ...\n"
        "## LANGUES\n"
    ),
))

TPL_EDUCATION = _register(CvTemplate(
    family="education",
    label_fr="Enseignement / Formation",
    label_en="Education / Training",
    layout="academic",
    font="Times",
    primary=(46, 89, 74),
    accent=(196, 149, 74),
    ink=(32, 40, 36),
    muted=(96, 108, 100),
    paper=(250, 251, 247),
    header_text=(255, 255, 255),
    chip_bg=(232, 240, 232),
    chip_text=(36, 74, 58),
    section_order=("profile", "education", "experience", "skills", "publications", "languages"),
    section_titles={
        "profile": "PROFIL PEDAGOGIQUE",
        "education": "DIPLOMES & CONCOURS",
        "experience": "EXPÉRIENCES D'ENSEIGNEMENT",
        "skills": "COMPETENCES",
        "publications": "PUBLICATIONS & TRAVAUX",
        "languages": "LANGUES",
    },
    extra_section_keys=("publications",),
    llm_sections=(
        "Structure CV ENSEIGNEMENT / FORMATION :\n"
        "## PROFIL\n(niveaux, disciplines, pedagogie)\n"
        "## FORMATION\nDIPLOME: CAPES, agreg, master MEEF...\nETABLISSEMENT: ...\nPERIODE: ...\n"
        "## EXPERIENCE\nPOSTE: ...\nENTREPRISE: etablissement\nPERIODE: ...\n- publics, programmes, responsabilites\n"
        "## COMPETENCES\ndisciplines | outils numeriques | pedagogie\n"
        "## PUBLICATIONS\n- seulement si presentes dans le CV\n"
        "## LANGUES\n"
    ),
))

TPL_MARKETING = _register(CvTemplate(
    family="marketing",
    label_fr="Marketing / Communication / Design",
    label_en="Marketing / Communication",
    layout="banner",
    font="Helvetica",
    primary=(122, 28, 74),
    accent=(232, 93, 74),
    ink=(36, 24, 32),
    muted=(112, 88, 96),
    paper=(253, 248, 250),
    header_text=(255, 255, 255),
    chip_bg=(255, 232, 228),
    chip_text=(122, 36, 40),
    section_order=("profile", "skills", "projects", "experience", "education", "languages"),
    section_titles={
        "profile": "PROFIL",
        "skills": "COMPETENCES",
        "projects": "REALISATIONS",
        "experience": "EXPÉRIENCES",
        "education": "FORMATION",
        "languages": "LANGUES",
    },
    extra_section_keys=("projects",),
    llm_sections=(
        "Structure CV MARKETING / COMMUNICATION / DESIGN :\n"
        "## PROFIL\n(canaux, univers de marque, resultats)\n"
        "## COMPETENCES\nSEO | paid | brand | outils creatifs (separes par | )\n"
        "## PROJETS\n- campagne / identite : objectif, levier, resultat\n"
        "## EXPERIENCE\nPOSTE: ...\nENTREPRISE: ...\nPERIODE: ...\n- realisations mesurees si le CV les contient\n"
        "## FORMATION\nDIPLOME: ...\nETABLISSEMENT: ...\nPERIODE: ...\n"
        "## LANGUES\n"
    ),
))

TPL_SALES = _register(CvTemplate(
    family="sales",
    label_fr="Commercial / Vente / Magasin",
    label_en="Sales / Retail",
    layout="banner",
    font="Helvetica",
    primary=(20, 52, 89),
    accent=(232, 125, 32),
    ink=(24, 32, 40),
    muted=(100, 108, 116),
    paper=(255, 250, 244),
    header_text=(255, 255, 255),
    chip_bg=(255, 236, 214),
    chip_text=(140, 68, 8),
    section_order=("profile", "projects", "experience", "skills", "education", "languages"),
    section_titles={
        "profile": "PROFIL COMMERCIAL",
        "projects": "RESULTATS CLES",
        "experience": "EXPÉRIENCES",
        "skills": "COMPETENCES",
        "education": "FORMATION",
        "languages": "LANGUES",
    },
    extra_section_keys=("projects",),
    llm_sections=(
        "Structure CV COMMERCIAL / VENDEUR / MAGASIN :\n"
        "## PROFIL\n(vente, conseil client, magasin ou BtoB)\n"
        "## PROJETS\n- objectifs, CA, taux de conversion — seulement si presents dans le CV\n"
        "## EXPERIENCE\nPOSTE: ...\nENTREPRISE: ...\nPERIODE: ...\n- resultats commerciaux concrets\n"
        "## COMPETENCES\nprospection | negociation | CRM | ...\n"
        "## FORMATION\nDIPLOME: ...\nETABLISSEMENT: ...\nPERIODE: ...\n"
        "## LANGUES\n"
    ),
))

TPL_ENGINEERING = _register(CvTemplate(
    family="engineering",
    label_fr="Ingénierie / Industrie",
    label_en="Engineering / Industry",
    layout="banner",
    font="Helvetica",
    primary=(36, 52, 74),
    accent=(214, 106, 36),
    ink=(28, 32, 40),
    muted=(100, 108, 116),
    paper=(248, 249, 251),
    header_text=(255, 255, 255),
    chip_bg=(255, 232, 214),
    chip_text=(122, 56, 12),
    section_order=("profile", "skills", "projects", "experience", "education", "languages"),
    section_titles={
        "profile": "PROFIL INGÉNIEUR",
        "skills": "COMPÉTENCES TECHNIQUES",
        "projects": "PROJETS",
        "experience": "EXPÉRIENCES",
        "education": "FORMATION",
        "languages": "LANGUES",
    },
    extra_section_keys=("projects",),
    llm_sections=(
        "Structure CV INGENIERIE / INDUSTRIE :\n"
        "## PROFIL\n(domaine, normes, environnements industriels)\n"
        "## COMPETENCES\nCAO | normes | methodes | logiciels\n"
        "## PROJETS\n- projet : perimetre, contrainte, livrable\n"
        "## EXPERIENCE\nPOSTE: ...\nENTREPRISE: ...\nPERIODE: ...\n"
        "## FORMATION\nDIPLOME: ...\nETABLISSEMENT: ...\nPERIODE: ...\n"
        "## LANGUES\n"
    ),
))

TPL_HOSPITALITY = _register(CvTemplate(
    family="hospitality",
    label_fr="Hôtellerie / Restauration / Tourisme",
    label_en="Hospitality / Tourism",
    layout="banner",
    font="Helvetica",
    primary=(92, 52, 28),
    accent=(201, 148, 74),
    ink=(40, 28, 20),
    muted=(120, 100, 84),
    paper=(253, 249, 243),
    header_text=(255, 255, 255),
    chip_bg=(245, 232, 208),
    chip_text=(92, 56, 20),
    section_order=("profile", "languages", "experience", "skills", "education"),
    section_titles={
        "profile": "PROFIL",
        "languages": "LANGUES",
        "experience": "EXPÉRIENCES",
        "skills": "COMPÉTENCES DE SERVICE",
        "education": "FORMATION",
    },
    llm_sections=(
        "Structure CV HOTELLERIE / RESTAURATION / TOURISME :\n"
        "## PROFIL\n(type d'etablissement, service, langues)\n"
        "## LANGUES\nFrancais (natif) | Anglais (...) — section prioritaire\n"
        "## EXPERIENCE\nPOSTE: ...\nENTREPRISE: hotel / restaurant / agence\nPERIODE: ...\n"
        "## COMPETENCES\naccueil | encaissement | logiciels PMS | ...\n"
        "## FORMATION\nDIPLOME: ...\nETABLISSEMENT: ...\nPERIODE: ...\n"
    ),
))

TPL_HR = _register(CvTemplate(
    family="hr",
    label_fr="Ressources humaines",
    label_en="Human resources",
    layout="banner",
    font="Helvetica",
    primary=(52, 40, 89),
    accent=(122, 148, 196),
    ink=(32, 28, 48),
    muted=(104, 100, 120),
    paper=(248, 247, 252),
    header_text=(255, 255, 255),
    chip_bg=(232, 232, 248),
    chip_text=(52, 40, 110),
    section_order=("profile", "skills", "experience", "education", "languages"),
    section_titles={
        "profile": "PROFIL RH",
        "skills": "COMPÉTENCES RH",
        "experience": "EXPÉRIENCES",
        "education": "FORMATION",
        "languages": "LANGUES",
    },
    llm_sections=(
        "Structure CV RESSOURCES HUMAINES :\n"
        "## PROFIL\n(perimetre : recrutement, paie, formation, relations sociales)\n"
        "## COMPETENCES\nSIRH | droit social | recrutement | ...\n"
        "## EXPERIENCE\nPOSTE: ...\nENTREPRISE: ...\nPERIODE: ...\n"
        "## FORMATION\nDIPLOME: ...\nETABLISSEMENT: ...\nPERIODE: ...\n"
        "## LANGUES\n"
    ),
))

TPL_CONSTRUCTION = _register(CvTemplate(
    family="construction",
    label_fr="BTP / Artisanat",
    label_en="Construction / Trades",
    layout="banner",
    font="Helvetica",
    primary=(89, 52, 28),
    accent=(201, 106, 36),
    ink=(40, 28, 20),
    muted=(116, 96, 80),
    paper=(252, 248, 242),
    header_text=(255, 255, 255),
    chip_bg=(255, 232, 208),
    chip_text=(110, 52, 12),
    section_order=("profile", "licenses", "experience", "skills", "education"),
    section_titles={
        "profile": "PROFIL",
        "licenses": "HABILITATIONS",
        "experience": "CHANTIERS & EXPÉRIENCES",
        "skills": "COMPETENCES",
        "education": "FORMATION",
    },
    extra_section_keys=("licenses",),
    llm_sections=(
        "Structure CV BTP / ARTISANAT :\n"
        "## PROFIL\n(corps de metier, types de chantiers)\n"
        "## AUTORISATIONS\n- habilitations (CACES, elec, amiante...) seulement si presentes\n"
        "## EXPERIENCE\nPOSTE: ...\nENTREPRISE: ...\nPERIODE: ...\n"
        "## COMPETENCES\ntechniques | lecture de plans | ...\n"
        "## FORMATION\nDIPLOME: CAP, BEP, BP...\nETABLISSEMENT: ...\nPERIODE: ...\n"
    ),
))

TPL_LOGISTICS = _register(CvTemplate(
    family="logistics",
    label_fr="Logistique / Transport / Supply chain",
    label_en="Logistics / Supply chain",
    layout="banner",
    font="Helvetica",
    primary=(20, 74, 52),
    accent=(52, 148, 106),
    ink=(24, 40, 32),
    muted=(88, 108, 96),
    paper=(246, 250, 247),
    header_text=(255, 255, 255),
    chip_bg=(220, 240, 228),
    chip_text=(16, 84, 52),
    section_order=("profile", "skills", "experience", "licenses", "education", "languages"),
    section_titles={
        "profile": "PROFIL",
        "skills": "COMPETENCES",
        "experience": "EXPÉRIENCES",
        "licenses": "PERMIS & HABILITATIONS",
        "education": "FORMATION",
        "languages": "LANGUES",
    },
    extra_section_keys=("licenses",),
    llm_sections=(
        "Structure CV LOGISTIQUE / TRANSPORT :\n"
        "## PROFIL\n(flux, entrepot, transport, WMS)\n"
        "## COMPETENCES\nWMS | ERP | ordonnancement | ...\n"
        "## EXPERIENCE\nPOSTE: ...\nENTREPRISE: ...\nPERIODE: ...\n"
        "## AUTORISATIONS\n- permis, CACES, ADR... seulement si presents\n"
        "## FORMATION\nDIPLOME: ...\nETABLISSEMENT: ...\nPERIODE: ...\n"
        "## LANGUES\n"
    ),
))

TPL_PUBLIC = _register(CvTemplate(
    family="public",
    label_fr="Fonction publique / Administration",
    label_en="Public sector",
    layout="classic",
    font="Times",
    primary=(0, 61, 112),
    accent=(227, 28, 36),
    ink=(24, 32, 48),
    muted=(96, 104, 116),
    paper=(247, 249, 252),
    header_text=(255, 255, 255),
    chip_bg=(228, 236, 248),
    chip_text=(0, 48, 92),
    section_order=("profile", "experience", "skills", "education", "languages"),
    section_titles={
        "profile": "PROFIL",
        "experience": "PARCOURS",
        "skills": "COMPETENCES",
        "education": "FORMATION & CONCOURS",
        "languages": "LANGUES",
    },
    llm_sections=(
        "Structure CV FONCTION PUBLIQUE / ADMINISTRATION :\n"
        "## PROFIL\n(filiere, grade, missions de service public)\n"
        "## EXPERIENCE\nPOSTE: ...\nENTREPRISE: administration / collectivite\nPERIODE: ...\n"
        "## COMPETENCES\nprocedures | accueil usagers | outils metier\n"
        "## FORMATION\nDIPLOME: concours, IRA, INET...\nETABLISSEMENT: ...\nPERIODE: ...\n"
        "## LANGUES\n"
    ),
))

TPL_RESEARCH = _register(CvTemplate(
    family="research",
    label_fr="Recherche / Sciences",
    label_en="Research / Science",
    layout="academic",
    font="Times",
    primary=(58, 36, 89),
    accent=(140, 106, 181),
    ink=(32, 28, 44),
    muted=(108, 100, 120),
    paper=(250, 248, 252),
    header_text=(255, 255, 255),
    chip_bg=(236, 228, 248),
    chip_text=(68, 40, 110),
    section_order=("profile", "education", "publications", "experience", "skills", "languages"),
    section_titles={
        "profile": "PROFIL SCIENTIFIQUE",
        "education": "FORMATION",
        "publications": "PUBLICATIONS",
        "experience": "EXPÉRIENCES & LABORATOIRES",
        "skills": "COMPETENCES",
        "languages": "LANGUES",
    },
    extra_section_keys=("publications",),
    llm_sections=(
        "Structure CV RECHERCHE / SCIENCES :\n"
        "## PROFIL\n(discipline, methodes, laboratoire)\n"
        "## FORMATION\nDIPLOME: these, master...\nETABLISSEMENT: ...\nPERIODE: ...\n"
        "## PUBLICATIONS\n- references si presentes dans le CV\n"
        "## EXPERIENCE\nPOSTE: ...\nENTREPRISE: labo / universite\nPERIODE: ...\n"
        "## COMPETENCES\nmethodes | instruments | logiciels\n"
        "## LANGUES\n"
    ),
))

TPL_MANAGEMENT = _register(CvTemplate(
    family="management",
    label_fr="Direction / Management",
    label_en="Management / Executive",
    layout="classic",
    font="Times",
    primary=(28, 32, 40),
    accent=(184, 148, 79),
    ink=(24, 24, 28),
    muted=(108, 108, 116),
    paper=(250, 250, 248),
    header_text=(255, 255, 255),
    chip_bg=(240, 236, 224),
    chip_text=(80, 64, 28),
    section_order=("profile", "skills", "experience", "education", "languages"),
    section_titles={
        "profile": "PROFIL DIRIGEANT",
        "skills": "COMPÉTENCES MANAGÉRIALES",
        "experience": "EXPÉRIENCES",
        "education": "FORMATION",
        "languages": "LANGUES",
    },
    llm_sections=(
        "Structure CV DIRECTION / MANAGEMENT :\n"
        "## PROFIL\n(perimetre P&L, equipes, transformation)\n"
        "## COMPETENCES\npilotage | leadership | strategie | ...\n"
        "## EXPERIENCE\nPOSTE: ...\nENTREPRISE: ...\nPERIODE: ...\n- effectifs, budget, resultats si presents dans le CV\n"
        "## FORMATION\nDIPLOME: ...\nETABLISSEMENT: ...\nPERIODE: ...\n"
        "## LANGUES\n"
    ),
))

TPL_CUSTOMER = _register(CvTemplate(
    family="customer",
    label_fr="Relation client / Support",
    label_en="Customer service",
    layout="banner",
    font="Helvetica",
    primary=(12, 84, 122),
    accent=(36, 164, 196),
    ink=(24, 40, 52),
    muted=(92, 112, 124),
    paper=(245, 250, 252),
    header_text=(255, 255, 255),
    chip_bg=(220, 240, 248),
    chip_text=(8, 84, 110),
    section_order=("profile", "languages", "skills", "experience", "education"),
    section_titles={
        "profile": "PROFIL",
        "languages": "LANGUES",
        "skills": "COMPETENCES",
        "experience": "EXPÉRIENCES",
        "education": "FORMATION",
    },
    llm_sections=(
        "Structure CV RELATION CLIENT / SUPPORT :\n"
        "## PROFIL\n(canaux, typologie de clients, outils)\n"
        "## LANGUES\nsection prioritaire\n"
        "## COMPETENCES\naccueil | CRM | recouvrement | ...\n"
        "## EXPERIENCE\nPOSTE: ...\nENTREPRISE: ...\nPERIODE: ...\n"
        "## FORMATION\nDIPLOME: ...\nETABLISSEMENT: ...\nPERIODE: ...\n"
    ),
))


TPL_OFFICE = _register(CvTemplate(
    family="office",
    label_fr="Assistant / Administratif / Secrétariat",
    label_en="Office / Administration",
    layout="classic",
    font="Helvetica",
    primary=(40, 64, 96),
    accent=(96, 140, 168),
    ink=(28, 36, 48),
    muted=(100, 108, 120),
    paper=(248, 250, 252),
    header_text=(255, 255, 255),
    chip_bg=(228, 236, 244),
    chip_text=(40, 64, 96),
    section_order=("profile", "skills", "experience", "education", "languages"),
    section_titles={
        "profile": "PROFIL",
        "skills": "COMPÉTENCES ADMINISTRATIVES",
        "experience": "EXPÉRIENCES",
        "education": "FORMATION",
        "languages": "LANGUES",
    },
    llm_sections=(
        "Structure CV ASSISTANT / EMPLOYE ADMINISTRATIF / SECRETARIAT :\n"
        "## PROFIL\n(accueil, organisation, outils bureautiques)\n"
        "## COMPETENCES\nPack Office | accueil | planning | ...\n"
        "## EXPERIENCE\nPOSTE: ...\nENTREPRISE: ...\nPERIODE: ...\n"
        "## FORMATION\nDIPLOME: ...\nETABLISSEMENT: ...\nPERIODE: ...\n"
        "## LANGUES\n"
    ),
))

TPL_SECURITY = _register(CvTemplate(
    family="security",
    label_fr="Sécurité / Surveillance",
    label_en="Security",
    layout="banner",
    font="Helvetica",
    primary=(32, 36, 40),
    accent=(196, 148, 52),
    ink=(28, 28, 32),
    muted=(108, 108, 112),
    paper=(248, 248, 246),
    header_text=(255, 255, 255),
    chip_bg=(240, 232, 214),
    chip_text=(80, 60, 20),
    section_order=("profile", "licenses", "experience", "skills", "education"),
    section_titles={
        "profile": "PROFIL",
        "licenses": "HABILITATIONS",
        "experience": "EXPÉRIENCES",
        "skills": "COMPÉTENCES",
        "education": "FORMATION",
    },
    extra_section_keys=("licenses",),
    llm_sections=(
        "Structure CV SECURITE / SURVEILLANCE :\n"
        "## PROFIL\n(sites, horaires, public)\n"
        "## AUTORISATIONS\n- carte professionnelle CNAPS, SST, SSIAP — seulement si presentes\n"
        "## EXPERIENCE\nPOSTE: ...\nENTREPRISE: ...\nPERIODE: ...\n"
        "## COMPETENCES\nrondes | surete | incendie | ...\n"
        "## FORMATION\nDIPLOME: ...\nETABLISSEMENT: ...\nPERIODE: ...\n"
    ),
))

TPL_BEAUTY = _register(CvTemplate(
    family="beauty",
    label_fr="Beauté / Coiffure / Esthétique",
    label_en="Beauty / Hair / Aesthetics",
    layout="banner",
    font="Helvetica",
    primary=(122, 48, 80),
    accent=(214, 132, 156),
    ink=(48, 28, 36),
    muted=(120, 92, 100),
    paper=(253, 246, 248),
    header_text=(255, 255, 255),
    chip_bg=(248, 228, 236),
    chip_text=(122, 40, 72),
    section_order=("profile", "skills", "experience", "education", "languages"),
    section_titles={
        "profile": "PROFIL",
        "skills": "TECHNIQUES & SOINS",
        "experience": "EXPÉRIENCES",
        "education": "FORMATION",
        "languages": "LANGUES",
    },
    llm_sections=(
        "Structure CV BEAUTE / COIFFURE / ESTHETIQUE :\n"
        "## PROFIL\n(type de salon, clientele, specialites)\n"
        "## COMPETENCES\ncoloration | soins | accueil | ...\n"
        "## EXPERIENCE\nPOSTE: ...\nENTREPRISE: ...\nPERIODE: ...\n"
        "## FORMATION\nDIPLOME: CAP, BP...\nETABLISSEMENT: ...\nPERIODE: ...\n"
        "## LANGUES\n"
    ),
))

TPL_REALESTATE = _register(CvTemplate(
    family="realestate",
    label_fr="Immobilier",
    label_en="Real estate",
    layout="banner",
    font="Helvetica",
    primary=(36, 64, 74),
    accent=(184, 140, 74),
    ink=(28, 36, 40),
    muted=(104, 108, 112),
    paper=(250, 248, 242),
    header_text=(255, 255, 255),
    chip_bg=(240, 232, 214),
    chip_text=(92, 64, 24),
    section_order=("profile", "projects", "experience", "skills", "education", "languages"),
    section_titles={
        "profile": "PROFIL",
        "projects": "RESULTATS",
        "experience": "EXPÉRIENCES",
        "skills": "COMPÉTENCES",
        "education": "FORMATION",
        "languages": "LANGUES",
    },
    extra_section_keys=("projects",),
    llm_sections=(
        "Structure CV IMMOBILIER :\n"
        "## PROFIL\n(transaction, location, gestion, secteur geo)\n"
        "## PROJETS\n- volume, mandats — seulement si presents dans le CV\n"
        "## EXPERIENCE\nPOSTE: ...\nENTREPRISE: ...\nPERIODE: ...\n"
        "## COMPETENCES\nnegociation | visites | loi ALUR | ...\n"
        "## FORMATION\nDIPLOME: ...\nETABLISSEMENT: ...\nPERIODE: ...\n"
        "## LANGUES\n"
    ),
))

TPL_SOCIAL = _register(CvTemplate(
    family="social",
    label_fr="Social / Médico-social",
    label_en="Social work",
    layout="academic",
    font="Times",
    primary=(64, 72, 52),
    accent=(148, 124, 74),
    ink=(36, 40, 32),
    muted=(104, 108, 96),
    paper=(250, 250, 246),
    header_text=(255, 255, 255),
    chip_bg=(236, 236, 220),
    chip_text=(64, 72, 40),
    section_order=("profile", "education", "experience", "skills", "languages"),
    section_titles={
        "profile": "PROFIL",
        "education": "DIPLÔMES",
        "experience": "EXPÉRIENCES",
        "skills": "COMPÉTENCES",
        "languages": "LANGUES",
    },
    llm_sections=(
        "Structure CV SOCIAL / MEDICO-SOCIAL :\n"
        "## PROFIL\n(publics, structures, accompagnement)\n"
        "## FORMATION\nDIPLOME: DEES, DEASS, DEME...\nETABLISSEMENT: ...\nPERIODE: ...\n"
        "## EXPERIENCE\nPOSTE: ...\nENTREPRISE: ...\nPERIODE: ...\n"
        "## COMPETENCES\nentretien | projet personnalise | ...\n"
        "## LANGUES\n"
    ),
))

TPL_FACILITIES = _register(CvTemplate(
    family="facilities",
    label_fr="Propreté / Entretien / Espaces verts",
    label_en="Cleaning / Facilities",
    layout="banner",
    font="Helvetica",
    primary=(52, 72, 56),
    accent=(120, 148, 84),
    ink=(32, 40, 32),
    muted=(100, 108, 96),
    paper=(248, 250, 246),
    header_text=(255, 255, 255),
    chip_bg=(228, 236, 220),
    chip_text=(44, 72, 40),
    section_order=("profile", "licenses", "experience", "skills", "education"),
    section_titles={
        "profile": "PROFIL",
        "licenses": "HABILITATIONS",
        "experience": "EXPÉRIENCES",
        "skills": "COMPÉTENCES",
        "education": "FORMATION",
    },
    extra_section_keys=("licenses",),
    llm_sections=(
        "Structure CV PROPRETE / ENTRETIEN :\n"
        "## PROFIL\n(sites, horaires, type de locaux)\n"
        "## AUTORISATIONS\n- CACES, produits, SST — seulement si presentes\n"
        "## EXPERIENCE\nPOSTE: ...\nENTREPRISE: ...\nPERIODE: ...\n"
        "## COMPETENCES\nnettoyage | espaces verts | ...\n"
        "## FORMATION\nDIPLOME: ...\nETABLISSEMENT: ...\nPERIODE: ...\n"
    ),
))

TPL_AGRICULTURE = _register(CvTemplate(
    family="agriculture",
    label_fr="Agriculture / Agroalimentaire",
    label_en="Agriculture / Food",
    layout="banner",
    font="Helvetica",
    primary=(64, 84, 36),
    accent=(168, 132, 52),
    ink=(36, 40, 28),
    muted=(108, 108, 92),
    paper=(250, 248, 240),
    header_text=(255, 255, 255),
    chip_bg=(236, 232, 208),
    chip_text=(72, 64, 24),
    section_order=("profile", "skills", "experience", "education", "licenses"),
    section_titles={
        "profile": "PROFIL",
        "skills": "COMPÉTENCES",
        "experience": "EXPÉRIENCES",
        "education": "FORMATION",
        "licenses": "PERMIS & HABILITATIONS",
    },
    extra_section_keys=("licenses",),
    llm_sections=(
        "Structure CV AGRICULTURE / AGROALIMENTAIRE :\n"
        "## PROFIL\n(cultures, elevage, atelier, saisonnier)\n"
        "## COMPETENCES\ntracteur | traite | hygiene | ...\n"
        "## EXPERIENCE\nPOSTE: ...\nENTREPRISE: exploitation / usine\nPERIODE: ...\n"
        "## FORMATION\nDIPLOME: Bac pro, BPREA...\nETABLISSEMENT: ...\nPERIODE: ...\n"
        "## AUTORISATIONS\n- permis, Certiphyto — seulement si presents\n"
    ),
))

TPL_SPORTS = _register(CvTemplate(
    family="sports",
    label_fr="Sport / Animation / Loisirs",
    label_en="Sports / Recreation",
    layout="banner",
    font="Helvetica",
    primary=(16, 92, 84),
    accent=(232, 148, 36),
    ink=(24, 40, 36),
    muted=(96, 112, 108),
    paper=(245, 250, 248),
    header_text=(255, 255, 255),
    chip_bg=(220, 240, 232),
    chip_text=(12, 84, 72),
    section_order=("profile", "licenses", "experience", "skills", "education", "languages"),
    section_titles={
        "profile": "PROFIL",
        "licenses": "DIPLÔMES SPORTIFS",
        "experience": "EXPÉRIENCES",
        "skills": "COMPÉTENCES",
        "education": "FORMATION",
        "languages": "LANGUES",
    },
    extra_section_keys=("licenses",),
    llm_sections=(
        "Structure CV SPORT / ANIMATION / LOISIRS :\n"
        "## PROFIL\n(publics, disciplines, structures)\n"
        "## AUTORISATIONS\n- BPJEPS, BAFA, BNSSA — seulement si presents\n"
        "## EXPERIENCE\nPOSTE: ...\nENTREPRISE: ...\nPERIODE: ...\n"
        "## COMPETENCES\nanimation | coaching | securite | ...\n"
        "## FORMATION\nDIPLOME: ...\nETABLISSEMENT: ...\nPERIODE: ...\n"
        "## LANGUES\n"
    ),
))

TPL_GENERIC = _register(CvTemplate(
    family="generic",
    label_fr="Professionnel",
    label_en="Professional",
    layout="banner",
    font="Helvetica",
    primary=(27, 54, 93),
    accent=(74, 140, 181),
    ink=(28, 36, 48),
    muted=(100, 108, 120),
    paper=(248, 250, 252),
    header_text=(255, 255, 255),
    chip_bg=(228, 238, 248),
    chip_text=(27, 54, 93),
    section_order=("profile", "skills", "experience", "education", "languages"),
    section_titles={
        "profile": "PROFIL PROFESSIONNEL",
        "skills": "COMPÉTENCES CLÉS",
        "experience": "EXPÉRIENCES PROFESSIONNELLES",
        "education": "FORMATION",
        "languages": "LANGUES",
    },
    llm_sections=(
        "Structure CV PROFESSIONNEL :\n"
        "## PROFIL\n(3-5 lignes alignees sur l'offre)\n"
        "## COMPETENCES\ncompetences separees par | \n"
        "## EXPERIENCE\nPOSTE: ...\nENTREPRISE: ...\nPERIODE: ...\nLIEU: ...\n- missions reformulees pour l'offre\n"
        "## FORMATION\nDIPLOME: ...\nETABLISSEMENT: ...\nPERIODE: ...\n"
        "## LANGUES\n"
    ),
))


FAMILY_DETECTION_ORDER = (
    "healthcare",
    "legal",
    "it",
    "finance",
    "research",
    "beauty",
    "realestate",
    "security",
    "agriculture",
    "sports",
    "social",
    "education",
    "construction",
    "engineering",
    "logistics",
    "hospitality",
    "hr",
    "marketing",
    "sales",
    "office",
    "public",
    "management",
    "customer",
    "facilities",
)

_FAMILY_KEYWORDS: dict[str, tuple[tuple[str, int], ...]] = {
    "healthcare": (
        ("medecin", 5), ("infirmier", 5), ("infirmiere", 5), ("hopital", 4),
        ("clinique", 3), ("pharmacien", 5), ("preparateur en pharmacie", 5),
        ("sage-femme", 5), ("sage femme", 5), ("kinesitherapeute", 5),
        ("dentiste", 5), ("chirurgien", 5), ("aide-soignant", 5),
        ("aide soignant", 5), ("cadre de sante", 5), ("soins infirmiers", 4),
        ("medical", 3), ("nurse", 4), ("healthcare", 4), ("hospital", 3),
        ("interne des hopitaux", 5), ("iade", 4), ("ibode", 4),
        ("radiologue", 5), ("anesthesiste", 5), ("puericultrice", 5),
        ("orthophoniste", 5), ("ergotherapeute", 5), ("psychologue clinicien", 4),
        ("laboratoire d'analyses", 3), ("rpps", 4), ("adeli", 4),
        ("ambulancier", 5), ("auxiliaire de puericulture", 5),
        ("opticien", 5), ("audioprothesiste", 5), ("veterinaire", 5),
    ),
    "legal": (
        ("avocat", 5), ("juriste", 5), ("notaire", 5), ("clerc de notaire", 5),
        ("droit des societes", 4), ("droit social", 4), ("droit public", 4),
        ("legal counsel", 5), ("magistrat", 5), ("huissier", 5),
        ("contentieux", 3), ("cabinet d'avocats", 4), ("direction juridique", 4),
        ("compliance officer", 3), ("barreau", 4), ("crfpa", 4),
        ("assistant juridique", 5), ("paralegal", 4),
    ),
    "it": (
        ("developpeur", 5), ("developer", 5), ("devops", 5), ("data scientist", 5),
        ("data engineer", 5), ("software", 4), ("fullstack", 5), ("full stack", 5),
        ("backend", 4), ("frontend", 4), ("informaticien", 5),
        ("informatique", 4), ("cybersecurite", 5), ("sysadmin", 4),
        ("administrateur systeme", 4), ("product owner", 3), ("scrum master", 3),
        ("architecte logiciel", 5), ("machine learning", 4),
        ("ingenieur logiciel", 5), ("software engineer", 5),
        ("qa engineer", 4), ("testeur logiciel", 4),
        ("administrateur reseau", 4), ("technicien informatique", 5),
        ("technicien helpdesk", 4), ("administrateur bases de donnees", 4),
    ),
    "finance": (
        ("comptable", 5), ("aide comptable", 5), ("expert-comptable", 5),
        ("controleur de gestion", 5), ("analyste financier", 5), ("banquier", 4),
        ("conseiller bancaire", 5), ("charge de clientele banque", 5),
        ("commissaire aux comptes", 5), ("tresorerie", 4), ("ifrs", 4),
        ("dscg", 4), ("actuaire", 5), ("credit manager", 4),
        ("gestionnaire de paie", 4), ("tresorier", 4), ("assureur", 4),
        ("conseiller assurance", 5), ("courtier", 3),
    ),
    "research": (
        ("chercheur", 5), ("doctorant", 5), ("post-doc", 5), ("postdoc", 5),
        ("recherche scientifique", 5), ("maitre de conferences", 4),
        ("charge de recherche", 5), ("cnrs", 4), ("inserm", 4),
        ("biologiste", 3), ("laborantin", 4),
    ),
    "beauty": (
        ("coiffeur", 5), ("coiffeuse", 5), ("estheticienne", 5),
        ("estheticien", 5), ("barbier", 5), ("prothesiste ongulaire", 5),
        ("spa practicien", 4), ("spa praticien", 4), ("maquilleur", 5),
        ("maquilleuse", 5), ("salon de coiffure", 4), ("beaute", 3),
    ),
    "realestate": (
        ("agent immobilier", 5), ("conseiller immobilier", 5),
        ("negociateur immobilier", 5), ("gestionnaire locatif", 5),
        ("syndic", 4), ("immobilier", 4), ("mandataire immobilier", 5),
    ),
    "security": (
        ("agent de securite", 5), ("agent de surveillance", 5),
        ("vigile", 5), ("ssi ap", 3), ("ssiap", 5), ("cnaps", 4),
        ("maitre chien", 4), ("agent de prevention", 4),
        ("surete aeroportuaire", 5), ("incendie ssiap", 4),
    ),
    "agriculture": (
        ("agriculteur", 5), ("viticulteur", 5), ("eleveur", 5),
        ("ouvrier agricole", 5), ("saisonier agricole", 5),
        ("conducteur d'engins agricoles", 5), ("agroalimentaire", 4),
        ("operateur de production agro", 4), ("maraicher", 5),
        ("horticulteur", 5), ("paysan", 4),
    ),
    "sports": (
        ("educateur sportif", 5), ("coach sportif", 5), ("moniteur de sport", 5),
        ("animateur sportif", 5), ("bpjeps", 5), ("bafa", 4),
        ("maitre nageur", 5), ("bnssa", 5), ("animateur periscolaire", 4),
        ("animateur ba fa", 3), ("professeur de fitness", 5),
        ("personal trainer", 4),
    ),
    "social": (
        ("educateur specialise", 5), ("assistant de service social", 5),
        ("moniteur educateur", 5), ("accompagnant educatif", 5),
        ("aes", 3), ("avs", 3), ("aide a domicile", 5),
        ("auxiliaire de vie", 5), ("amp ", 3), ("cesf", 4),
        ("mediateur social", 5), ("conseiller insertion", 5),
        ("travailleur social", 5), ("medico-social", 4),
    ),
    "education": (
        ("enseignant", 5), ("professeur des ecoles", 5), ("professeur", 4),
        ("instituteur", 5), ("formateur", 4), ("education nationale", 5),
        ("capes", 5), ("agregation", 4), ("atsem", 5), ("aes h", 3),
        ("aesn", 4), ("vie scolaire", 4), ("surveillant scolaire", 5),
        ("assistant d'education", 5), ("teacher", 4),
    ),
    "construction": (
        ("macon", 5), ("charpentier", 5), ("electricien", 5),
        ("plombier", 5), ("conducteur de travaux", 5), ("chef de chantier", 5),
        ("btp", 4), ("couvreur", 5), ("menuisier", 5), ("peintre en batiment", 5),
        ("carreleur", 5), ("chauffagiste", 5), ("serrurier", 5),
        ("facadier", 4), ("coffreur", 5), ("bancheur", 4),
        ("manoeuvre batiment", 5), ("ouvrier du batiment", 5),
        ("technicien de maintenance batiment", 4),
    ),
    "engineering": (
        ("ingenieur", 4), ("bureau d'etudes", 4), ("genie civil", 5),
        ("genie mecanique", 5), ("technicien de maintenance", 5),
        ("electrotechnicien", 4), ("mecanicien", 4), ("automaticien", 5),
        ("qualiticien", 4), ("technicien methodes", 5),
        ("operateur de production", 4), ("ajusteur", 5), ("soudeur", 5),
        ("chaudronnier", 5), ("usinage", 3),
    ),
    "logistics": (
        ("logisticien", 5), ("supply chain", 5), ("magasinier", 5),
        ("cariste", 5), ("chauffeur poids lourd", 5), ("chauffeur spl", 5),
        ("chauffeur livreur", 5), ("coursier", 4), ("transporteur", 4),
        ("preparateur de commandes", 5), ("affreteur", 5),
        ("exploitant transport", 5), ("agent de quai", 5),
        ("responsable d'entrepot", 5), ("manutentionnaire", 5),
    ),
    "hospitality": (
        ("hotellerie", 5), ("restaurateur", 4), ("chef de rang", 5),
        ("maitre d'hotel", 5), ("cuisinier", 5), ("commis de cuisine", 5),
        ("chef de cuisine", 5), ("plongeur", 4), ("receptionniste", 5),
        ("gouvernante", 5), ("femme de chambre", 5), ("valet de chambre", 5),
        ("sommelier", 5), ("tourisme", 4), ("guide touristique", 5),
        ("agent de voyage", 5), ("barman", 4), ("serveuse", 5), ("serveur", 5),
        ("equipier polyvalent restauration", 5), ("mcdo", 3), ("equipier mcdonald", 5),
        ("employe de restauration", 5),
    ),
    "hr": (
        ("ressources humaines", 5), ("responsable rh", 5),
        ("charge de recrutement", 5), ("talent acquisition", 5),
        ("gestionnaire paie", 5), ("recruteur", 4), ("hrbp", 5),
        ("assistant rh", 5),
    ),
    "marketing": (
        ("marketing", 4), ("community manager", 5), ("charge de communication", 5),
        ("graphiste", 5), ("directeur artistique", 5), ("brand manager", 5),
        ("social media", 4), ("ux designer", 4), ("ui designer", 4),
        ("charge de communication", 5), ("journaliste", 4), ("redacteur web", 4),
    ),
    "sales": (
        ("vendeur", 5), ("vendeuse", 5), ("commercial", 5), ("commerciale", 5),
        ("business developer", 5), ("account manager", 5),
        ("ingenieur d'affaires", 5), ("responsable des ventes", 5),
        ("directeur commercial", 5), ("conseiller de vente", 5),
        ("conseiller commercial", 5), ("vendeur conseil", 5),
        ("vendeur automobile", 5), ("vendeur pret a porter", 5),
        ("caissier", 5), ("caissiere", 5), ("hote de caisse", 5),
        ("hotesse de caisse", 5), ("employe de rayon", 5),
        ("employe commercial", 5), ("employe de libre service", 5),
        ("employe de magasin", 5), ("employe polyvalent magasin", 5),
        ("employe polyvalent", 4), ("vendeur en magasin", 5), ("teleprospecteur", 5),
        ("technicien commercial", 5), ("itinerant", 3),
        ("adv ", 4), ("assistant commercial", 5), ("inside sales", 4),
        ("responsable de magasin", 5), ("directeur de magasin", 5),
        ("chef de rayon", 5), ("category manager", 4),
        ("negoce", 3), ("force de vente", 5),
    ),
    "office": (
        ("secretaire", 5), ("assistant de direction", 5),
        ("assistante de direction", 5), ("assistant administratif", 5),
        ("employe administratif", 5), ("employe de bureau", 5),
        ("office manager", 5), ("gestionnaire administratif", 5),
        ("assistant polyvalent", 4), ("charge d'accueil", 4),
        ("standardiste", 4), ("greffier", 3),
        ("technicien des services administratifs", 5),
        ("secretaire medicale", 5), ("secretaire medical", 5),
    ),
    "public": (
        ("fonctionnaire", 5), ("fonction publique", 5),
        ("agent administratif territorial", 5), ("secretaire administratif", 5),
        ("attache territorial", 5), ("redacteur territorial", 5),
        ("adjoint administratif", 5), ("prefecture", 4),
        ("collectivite territoriale", 4),
    ),
    "management": (
        ("directeur general", 5), ("directrice generale", 5), ("ceo", 4),
        ("directeur d'usine", 5), ("directeur des operations", 5),
        ("chef d'entreprise", 4), ("directeur de site", 5),
    ),
    "customer": (
        ("relation client", 5), ("service client", 5),
        ("conseiller clientele", 5), ("conseiller client", 5),
        ("hotline", 4), ("support client", 5), ("customer success", 4),
        ("helpdesk", 3), ("teleconseiller", 5), ("teleconseillere", 5),
        ("charge de clientele", 4),
    ),
    "facilities": (
        ("agent d'entretien", 5), ("agent de proprete", 5),
        ("agent de nettoyage", 5), ("technicien de surface", 5),
        ("femme de menage", 4), ("agent d'entretien des locaux", 5),
        ("espaces verts", 4), ("jardinier", 5), ("paysagiste", 4),
        ("gardien d'immeuble", 5), ("concierge d'immeuble", 4),
        ("agent de maintenance immeuble", 4),
    ),
}


def _padded_text(value: str) -> str:
    folded = (
        _fold(value)
        .replace("-", " ")
        .replace("/", " ")
        .replace("'", " ")
        .replace("\u2019", " ")
    )
    folded = re.sub(r"\s+", " ", folded).strip()
    return f" {folded} "


def _score_keywords(padded: str, keywords: tuple[tuple[str, int], ...]) -> int:
    total = 0
    for term, weight in keywords:
        needle = _fold(term).replace("-", " ").replace("'", " ").strip()
        if len(needle) < 3:
            continue
        if f" {needle} " in padded:
            total += weight
    return total


def _rank_families(scores: dict[str, int]) -> str:
    ranked = sorted(
        scores.items(),
        key=lambda item: (
            -item[1],
            FAMILY_DETECTION_ORDER.index(item[0])
            if item[0] in FAMILY_DETECTION_ORDER
            else 99,
        ),
    )
    return ranked[0][0]


def list_cv_templates() -> list[CvTemplate]:
    return [_TEMPLATES[key] for key in (*FAMILY_DETECTION_ORDER, "generic")]


def template_for(family: str) -> CvTemplate:
    return _TEMPLATES.get(family, TPL_GENERIC)


def detect_job_family(
    job: dict[str, Any] | None = None,
    match: dict[str, Any] | None = None,
    extra_text: str = "",
) -> str:
    """Pick the CV template family from the offer (title first, then description)."""
    job = job or {}
    match = match or {}
    title_blob = " ".join(
        str(part or "")
        for part in (job.get("title"), match.get("titre_cv_recommande"))
    )
    full_blob = " ".join(
        str(part or "")
        for part in (
            title_blob,
            job.get("company"),
            job.get("description"),
            extra_text,
        )
    )
    title_pad = _padded_text(title_blob)
    full_pad = _padded_text(full_blob)
    title_scores: dict[str, int] = {}
    full_scores: dict[str, int] = {}
    for family, keywords in _FAMILY_KEYWORDS.items():
        tscore = _score_keywords(title_pad, keywords)
        fscore = _score_keywords(full_pad, keywords)
        if tscore:
            title_scores[family] = tscore
        if fscore:
            full_scores[family] = fscore
    if title_scores and max(title_scores.values()) >= 3:
        return _rank_families(title_scores)
    if not full_scores:
        return "generic"
    if max(full_scores.values()) < 3:
        return "generic"
    return _rank_families(full_scores)


def template_label(family: str, locale: str = "fr") -> str:
    tpl = template_for(family)
    return tpl.label_fr if (locale or "fr").startswith("fr") else tpl.label_en


# ---------------------------------------------------------------------------
# Structured CV model + parser
# ---------------------------------------------------------------------------

@dataclass
class ExperienceEntry:
    title: str = ""
    company: str = ""
    period: str = ""
    location: str = ""
    bullets: list[str] = field(default_factory=list)


@dataclass
class EducationEntry:
    diploma: str = ""
    school: str = ""
    period: str = ""
    details: str = ""


@dataclass
class StructuredCV:
    name: str = ""
    title: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    linkedin: str = ""
    website: str = ""
    profile: str = ""
    skills: list[str] = field(default_factory=list)
    experiences: list[ExperienceEntry] = field(default_factory=list)
    education: list[EducationEntry] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)
    extras: dict[str, list[str]] = field(default_factory=dict)
    modifications: list[str] = field(default_factory=list)
    family: str = "generic"
    raw_body: str = ""


_HEADER_FIELD_RE = re.compile(
    r"^(nom|name|titre|title|email|e-mail|mail|telephone|téléphone|tel|phone|"
    r"ville|city|lieu|location|linkedin|site|website|portfolio)\s*[:：]\s*(.+)$",
    re.IGNORECASE,
)
_LABELED_JOB_RE = re.compile(
    r"^(poste|title|entreprise|company|periode|période|dates|lieu|location|ville)\s*[:：]\s*(.+)$",
    re.IGNORECASE,
)
_LABELED_EDU_RE = re.compile(
    r"^(diplome|diplôme|degree|etablissement|établissement|school|universite|"
    r"université|periode|période|dates)\s*[:：]\s*(.+)$",
    re.IGNORECASE,
)
_EMAIL_RE = re.compile(r"[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}", re.I)
_PHONE_RE = re.compile(r"(?:\+?\d[\d .\-]{7,}\d)")
_SECTION_RE = re.compile(
    r"^#{1,3}\s+(.+)$|^(?:[-*=]{3,}\s*)?([A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ /'’&]{4,})(?:\s*[-*=]{3,})?$"
)


_MODS_HEADING_RE = re.compile(
    r"(?:^|\n)\s*(?:#{1,3}\s*)?(?:[-*=_]{3,}\s*)?"
    r"MODIFICATIONS?\s+"
    r"(?:APPLIQU[ÉE]ES?|APPORT[ÉE]ES?|(?:À|A)\s+APPORTER(?:\s+AU\s+CV)?)\b",
    re.IGNORECASE,
)


def split_modifications(text: str) -> tuple[str, list[str]]:
    """Return CV body without the internal « modifications apportées » appendix."""
    if not text:
        return "", []
    match = _MODS_HEADING_RE.search(text)
    if not match:
        return text.strip(), []
    body = text[: match.start()].strip()
    tail = text[match.end() :]
    items = [
        re.sub(r"^\s*(?:[-•*]|\d+[.)])\s*", "", line).strip()
        for line in tail.splitlines()
        if line.strip() and not re.match(r"^[-*=_]{3,}$", line.strip())
    ]
    return body, [item for item in items if item]


def cv_text_for_candidate(text: str) -> str:
    """Candidate-facing CV text: never includes the modifications appendix."""
    body, _mods = split_modifications(text)
    return body


def _is_bullet(line: str) -> bool:
    return bool(re.match(r"^\s*(?:[-•*–—]|·|\d+[.)])\s+", line))


def _strip_bullet(line: str) -> str:
    return re.sub(r"^\s*(?:[-•*–—]|·|\d+[.)])\s+", "", line).strip()


def _split_skills(block: str) -> list[str]:
    items: list[str] = []
    for raw in re.split(r"[\n|;,/]+", block):
        piece = _strip_bullet(raw).strip(" -")
        if 1 < len(piece) <= 48:
            items.append(piece)
        elif len(piece) > 48 and "," in piece:
            items.extend(p.strip() for p in piece.split(",") if 1 < len(p.strip()) <= 48)
    seen: set[str] = set()
    unique: list[str] = []
    for item in items:
        key = _fold(item)
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique[:24]


def _classify_section(title: str) -> str:
    key = _fold(title)
    key = re.sub(r"[^a-z]+", " ", key).strip()
    mapping = (
        (("modification",), "modifications"),
        (("profil", "a propos", "about", "summary", "resume professionnel", "accroche"), "profile"),
        (("stack", "competence", "skill", "techno", "outils", "software"), "skills"),
        (("experience", "parcours", "emploi", "poste occupe"), "experience"),
        (("formation", "diplome", "education", "cursus", "etude", "concours"), "education"),
        (("langue", "language"), "languages"),
        (("projet", "realisation", "campagne", "portfolio", "resultat"), "projects"),
        (("publication", "article", "ouvrage"), "publications"),
        (
            ("certification", "habilitation", "autorisation", "permis", "stage", "internat", "adeli", "rpps"),
            "licenses",
        ),
        (("centre d interet", "interet", "hobby", "loisirs"), "interests"),
    )
    for needles, name in mapping:
        if any(needle in key for needle in needles):
            return name
    return "other"


def _parse_experience_header(line: str) -> ExperienceEntry | None:
    cleaned = line.strip().strip("-").strip()
    if not cleaned or _is_bullet(cleaned):
        return None
    if _HEADER_FIELD_RE.match(cleaned) or _LABELED_EDU_RE.match(cleaned):
        return None
    period = ""
    period_match = re.search(
        r"\(([^)]*\d{4}[^)]*)\)|\b(\d{4}\s*[-–/àa]+\s*(?:\d{4}|present|aujourd.?hui|en cours))\b",
        cleaned,
        flags=re.I,
    )
    if period_match:
        period = next(g for g in period_match.groups() if g)
        cleaned = cleaned[: period_match.start()].strip(" -|,")
    company = ""
    location = ""
    if " | " in cleaned:
        left, right = cleaned.split(" | ", 1)
        cleaned = left.strip()
        if re.search(r"\d{4}", right):
            period = period or right.strip()
        else:
            location = right.strip()
    if " — " in cleaned or " – " in cleaned or " - " in cleaned:
        parts = re.split(r"\s+[—–-]\s+", cleaned, maxsplit=1)
        title = parts[0].strip()
        company = parts[1].strip() if len(parts) > 1 else ""
    else:
        title = cleaned
    if len(title) < 3 or len(title) > 90:
        return None
    return ExperienceEntry(title=title, company=company, period=period, location=location)


def parse_adapted_cv(text: str) -> StructuredCV:
    """Parse LLM (or legacy) adapted CV text into a structured document."""
    body, modifications = split_modifications(text or "")
    cv = StructuredCV(modifications=modifications)
    if not body:
        return cv

    lines = [line.rstrip() for line in body.replace("\r\n", "\n").split("\n")]
    header_lines: list[str] = []
    i = 0
    while i < min(len(lines), 12):
        raw = lines[i].strip().strip("-")
        if not raw:
            i += 1
            if header_lines:
                break
            continue
        if _SECTION_RE.match(raw) and _classify_section(raw.lstrip("# ").strip()) != "other":
            break
        field = _HEADER_FIELD_RE.match(raw)
        if field:
            label, value = field.group(1).lower(), field.group(2).strip()
            folded_label = _fold(label)
            if folded_label in {"nom", "name"}:
                cv.name = value
            elif folded_label in {"titre", "title"}:
                cv.title = value
            elif "mail" in folded_label:
                cv.email = value
            elif folded_label in {"telephone", "tel", "phone"}:
                cv.phone = value
            elif folded_label in {"ville", "city", "lieu", "location"}:
                cv.location = value
            elif "linkedin" in folded_label:
                cv.linkedin = value
            else:
                cv.website = value
            i += 1
            continue
        header_lines.append(raw)
        i += 1

    if not cv.name and header_lines:
        cv.name = header_lines[0]
    if not cv.title and len(header_lines) > 1:
        cv.title = header_lines[1]
    contact_blob = " ".join(header_lines[2:] if len(header_lines) > 2 else header_lines)
    if not cv.email:
        found = _EMAIL_RE.search(contact_blob) or _EMAIL_RE.search(body[:800])
        if found:
            cv.email = found.group(0)
    if not cv.phone:
        found = _PHONE_RE.search(contact_blob)
        if found:
            cv.phone = found.group(0).strip()

    remaining = lines[i:]
    current = "profile"
    buffers: dict[str, list[str]] = {current: []}
    for raw in remaining:
        stripped = raw.strip().strip("-")
        section_match = _SECTION_RE.match(stripped) if stripped else None
        if section_match:
            title = (section_match.group(1) or section_match.group(2) or "").strip()
            classified = _classify_section(title)
            if classified != "other":
                current = classified
                buffers.setdefault(current, [])
                continue
        buffers.setdefault(current, []).append(raw)

    cv.profile = "\n".join(
        line.strip() for line in buffers.get("profile", []) if line.strip()
    ).strip()
    cv.skills = _split_skills("\n".join(buffers.get("skills", [])))
    cv.languages = _split_skills("\n".join(buffers.get("languages", [])))
    cv.experiences = _parse_experiences(buffers.get("experience", []))
    cv.education = _parse_education(buffers.get("education", []))

    for extra_key in ("projects", "publications", "licenses", "certifications", "interests", "other"):
        block_lines = [line.strip() for line in buffers.get(extra_key, []) if line.strip()]
        if not block_lines:
            continue
        items = [_strip_bullet(line) for line in block_lines if line]
        cv.extras[extra_key if extra_key != "other" else "autres"] = [
            item for item in items if item
        ]

    if not cv.experiences and not cv.education and not cv.profile:
        cv.raw_body = body
    return cv


def _parse_experiences(lines: list[str]) -> list[ExperienceEntry]:
    jobs: list[ExperienceEntry] = []
    current: ExperienceEntry | None = None

    def flush() -> None:
        nonlocal current
        if current and (current.title or current.bullets):
            jobs.append(current)
        current = None

    for raw in lines:
        stripped = raw.strip()
        if not stripped:
            continue
        labeled = _LABELED_JOB_RE.match(stripped)
        if labeled:
            field, value = _fold(labeled.group(1)), labeled.group(2).strip()
            if field in {"poste", "title"}:
                flush()
                current = ExperienceEntry(title=value)
            else:
                if current is None:
                    current = ExperienceEntry()
                if field in {"entreprise", "company"}:
                    current.company = value
                elif field in {"periode", "dates"}:
                    current.period = value
                elif field in {"lieu", "location", "ville"}:
                    current.location = value
            continue
        if _is_bullet(stripped):
            if current is None:
                current = ExperienceEntry()
            current.bullets.append(_strip_bullet(stripped))
            continue
        parsed = _parse_experience_header(stripped)
        if parsed:
            flush()
            current = parsed
        elif current is not None:
            current.bullets.append(stripped)
        else:
            current = ExperienceEntry(title=stripped)
    flush()
    return jobs[:12]


def _parse_education(lines: list[str]) -> list[EducationEntry]:
    items: list[EducationEntry] = []
    current: EducationEntry | None = None

    def flush() -> None:
        nonlocal current
        if current and (current.diploma or current.school):
            items.append(current)
        current = None

    for raw in lines:
        stripped = raw.strip()
        if not stripped:
            continue
        labeled = _LABELED_EDU_RE.match(stripped)
        if labeled:
            field, value = _fold(labeled.group(1)), labeled.group(2).strip()
            if field in {"diplome", "degree"}:
                flush()
                current = EducationEntry(diploma=value)
            else:
                if current is None:
                    current = EducationEntry()
                if field in {"etablissement", "school", "universite"}:
                    current.school = value
                elif field in {"periode", "dates"}:
                    current.period = value
            continue
        if _is_bullet(stripped):
            if current is None:
                current = EducationEntry()
            current.details = _strip_bullet(stripped)
            continue
        parsed = _parse_experience_header(stripped)
        if parsed:
            flush()
            current = EducationEntry(
                diploma=parsed.title,
                school=parsed.company,
                period=parsed.period,
                details=parsed.location,
            )
        elif current is None:
            current = EducationEntry(diploma=stripped)
        else:
            current.details = stripped
    flush()
    return items[:8]


def enrich_structured_cv(
    cv: StructuredCV,
    *,
    job: dict[str, Any] | None = None,
    match: dict[str, Any] | None = None,
    user_profile: dict[str, Any] | None = None,
    original_cv: str = "",
    family: str | None = None,
) -> StructuredCV:
    """Fill missing header fields from the candidate profile / original CV."""
    job = job or {}
    match = match or {}
    user_profile = user_profile or {}
    detected = family or detect_job_family(job, match, extra_text=cv.title or cv.profile)
    updates: dict[str, Any] = {"family": detected}

    original_head = "\n".join((original_cv or "").splitlines()[:20])
    if not cv.name:
        updates["name"] = (
            str(user_profile.get("full_name") or "").strip()
            or (original_head.splitlines()[0].strip() if original_head.strip() else "")
            or "Candidat"
        )
    if not cv.title:
        updates["title"] = (
            str(match.get("titre_cv_recommande") or "").strip()
            or str(user_profile.get("target_job_title") or "").strip()
            or str(job.get("title") or "").strip()
        )
    if not cv.email:
        found = _EMAIL_RE.search(original_head)
        updates["email"] = str(user_profile.get("email") or "").strip() or (
            found.group(0) if found else ""
        )
    if not cv.phone:
        found = _PHONE_RE.search(original_head)
        updates["phone"] = str(user_profile.get("phone") or "").strip() or (
            found.group(0).strip() if found else ""
        )
    if not cv.location:
        updates["location"] = str(user_profile.get("city") or user_profile.get("location") or "").strip()
    return replace(cv, **updates)


def public_cv_text(cv: StructuredCV) -> str:
    """Plain-text CV without the internal modifications appendix (clipboard / ATS)."""
    lines: list[str] = []
    if cv.name:
        lines.append(cv.name)
    if cv.title:
        lines.append(cv.title)
    contact = " · ".join(p for p in (cv.email, cv.phone, cv.location, cv.linkedin) if p)
    if contact:
        lines.append(contact)
    tpl = template_for(cv.family)
    for key in tpl.section_order:
        title = tpl.section_titles.get(key, key.upper())
        if key == "profile" and cv.profile:
            lines.extend(["", title, cv.profile])
        elif key == "skills" and cv.skills:
            lines.extend(["", title, " · ".join(cv.skills)])
        elif key == "languages" and cv.languages:
            lines.extend(["", title, " · ".join(cv.languages)])
        elif key == "experience" and cv.experiences:
            lines.extend(["", title])
            for job in cv.experiences:
                head = " — ".join(p for p in (job.title, job.company) if p)
                meta = " | ".join(p for p in (job.period, job.location) if p)
                lines.append(f"{head} {('· ' + meta) if meta else ''}".strip())
                lines.extend(f"• {bullet}" for bullet in job.bullets)
        elif key == "education" and cv.education:
            lines.extend(["", title])
            for item in cv.education:
                head = " — ".join(p for p in (item.diploma, item.school) if p)
                lines.append(f"{head} {('· ' + item.period) if item.period else ''}".strip())
                if item.details:
                    lines.append(item.details)
        elif key in cv.extras and cv.extras[key]:
            lines.extend(["", title])
            lines.extend(f"• {item}" for item in cv.extras[key])
    if cv.raw_body and len(lines) < 6:
        lines.extend(["", cv.raw_body])
    return "\n".join(lines).strip()


def prepare_structured_cv(
    adapted_text: str,
    *,
    job: dict[str, Any] | None = None,
    match: dict[str, Any] | None = None,
    user_profile: dict[str, Any] | None = None,
    original_cv: str = "",
) -> StructuredCV:
    parsed = parse_adapted_cv(adapted_text)
    return enrich_structured_cv(
        parsed,
        job=job,
        match=match,
        user_profile=user_profile,
        original_cv=original_cv,
    )


# ---------------------------------------------------------------------------
# PDF renderer
# ---------------------------------------------------------------------------

class ProfessionCvPdf(FPDF):
    def __init__(self, template: CvTemplate, name: str, title: str):
        super().__init__(format="A4", unit="mm")
        self.template = template
        self.doc_name = name
        self.doc_title = title
        self.set_auto_page_break(auto=True, margin=18)
        self.alias_nb_pages()

    def header(self) -> None:  # noqa: D401 — fpdf hook
        if self.page_no() == 1:
            return
        tpl = self.template
        self.set_fill_color(*tpl.primary)
        self.rect(0, 0, 210, 9, "F")
        self.set_text_color(*tpl.header_text)
        self.set_font(tpl.font, "B", 8)
        label = pdf_safe_text(f"{self.doc_name}  |  {self.doc_title}")
        self.set_xy(14, 2.2)
        self.cell(182, 5, label, align="L")
        self.set_y(14)

    def footer(self) -> None:
        tpl = self.template
        self.set_y(-14)
        self.set_draw_color(*tpl.accent)
        self.set_line_width(0.4)
        self.line(14, self.get_y(), 196, self.get_y())
        self.set_y(-12)
        self.set_font(tpl.font, "", 7)
        self.set_text_color(*tpl.muted)
        self.cell(
            0,
            8,
            pdf_safe_text(f"{self.doc_name}  ·  {tpl.label_fr}  ·  {self.page_no()}/{{nb}}"),
            align="C",
        )


def _set_fill(pdf: FPDF, rgb: Rgb) -> None:
    pdf.set_fill_color(*rgb)


def _set_text(pdf: FPDF, rgb: Rgb) -> None:
    pdf.set_text_color(*rgb)


def _draw_banner_header(pdf: ProfessionCvPdf, cv: StructuredCV, height: float) -> None:
    tpl = pdf.template
    _set_fill(pdf, tpl.primary)
    pdf.rect(0, 0, 210, height, "F")
    _set_fill(pdf, tpl.accent)
    pdf.rect(0, height - 3.2, 210, 3.2, "F")
    _set_text(pdf, tpl.header_text)
    pdf.set_xy(14, 12)
    pdf.set_font(tpl.font, "B", 22)
    pdf.cell(182, 10, pdf_safe_text(cv.name or "Candidat"), align="L")
    pdf.set_xy(14, 24)
    pdf.set_font(tpl.font, "", 12)
    _set_text(pdf, tpl.accent)
    pdf.set_text_color(
        min(255, tpl.accent[0] + 40),
        min(255, tpl.accent[1] + 40),
        min(255, tpl.accent[2] + 40),
    )
    if tpl.layout == "banner":
        pdf.set_text_color(220, 236, 240)
    pdf.cell(182, 7, pdf_safe_text(cv.title), align="L")
    contact = "   ·   ".join(
        p for p in (cv.email, cv.phone, cv.location, cv.linkedin or cv.website) if p
    )
    if contact:
        pdf.set_xy(14, 33)
        pdf.set_font(tpl.font, "", 9)
        _set_text(pdf, tpl.header_text)
        pdf.cell(182, 5, pdf_safe_text(contact), align="L")
    pdf.set_y(height + 8)


def _draw_classic_header(pdf: ProfessionCvPdf, cv: StructuredCV) -> None:
    tpl = pdf.template
    _set_fill(pdf, tpl.primary)
    pdf.rect(0, 0, 210, 8, "F")
    _set_fill(pdf, tpl.accent)
    pdf.rect(0, 8, 210, 1.6, "F")
    pdf.set_y(16)
    _set_text(pdf, tpl.primary)
    pdf.set_font(tpl.font, "B", 20)
    pdf.cell(0, 9, pdf_safe_text(cv.name or "Candidat"), align="C")
    pdf.ln(8)
    pdf.set_font(tpl.font, "I", 12)
    _set_text(pdf, tpl.accent)
    pdf.cell(0, 7, pdf_safe_text(cv.title), align="C")
    pdf.ln(7)
    contact = "  ·  ".join(
        p for p in (cv.email, cv.phone, cv.location, cv.linkedin or cv.website) if p
    )
    if contact:
        pdf.set_font(tpl.font, "", 9)
        _set_text(pdf, tpl.muted)
        pdf.cell(0, 5, pdf_safe_text(contact), align="C")
        pdf.ln(5)
    pdf.set_draw_color(*tpl.primary)
    pdf.set_line_width(0.3)
    y = pdf.get_y() + 2
    pdf.line(50, y, 160, y)
    pdf.set_y(y + 6)


def _draw_academic_header(pdf: ProfessionCvPdf, cv: StructuredCV) -> None:
    tpl = pdf.template
    _set_fill(pdf, tpl.primary)
    pdf.rect(0, 0, 8, 297, "F")
    _set_fill(pdf, tpl.accent)
    pdf.rect(8, 0, 2.2, 297, "F")
    pdf.set_xy(18, 14)
    _set_text(pdf, tpl.primary)
    pdf.set_font(tpl.font, "B", 20)
    pdf.cell(178, 9, pdf_safe_text(cv.name or "Candidat"), align="L")
    pdf.set_xy(18, 24)
    pdf.set_font(tpl.font, "I", 12)
    _set_text(pdf, tpl.accent)
    pdf.cell(178, 7, pdf_safe_text(cv.title), align="L")
    contact = "  ·  ".join(
        p for p in (cv.email, cv.phone, cv.location, cv.linkedin or cv.website) if p
    )
    if contact:
        pdf.set_xy(18, 33)
        pdf.set_font(tpl.font, "", 9)
        _set_text(pdf, tpl.muted)
        pdf.cell(178, 5, pdf_safe_text(contact), align="L")
    pdf.set_y(44)


def _section_title(pdf: ProfessionCvPdf, label: str) -> None:
    tpl = pdf.template
    pdf.ln(2)
    if pdf.get_y() > 262:
        pdf.add_page()
    _set_text(pdf, tpl.primary)
    pdf.set_font(tpl.font, "B", 10)
    pdf.cell(0, 6, pdf_safe_text(label), align="L")
    pdf.ln(6)
    y = pdf.get_y()
    pdf.set_draw_color(*tpl.accent)
    pdf.set_line_width(0.7)
    left = 18 if tpl.layout == "academic" else 14
    pdf.line(left, y, left + 46, y)
    pdf.ln(3)


def _write_paragraph(pdf: ProfessionCvPdf, text: str) -> None:
    tpl = pdf.template
    _set_text(pdf, tpl.ink)
    pdf.set_font(tpl.font, "", 10)
    pdf.multi_cell(0, 5, pdf_safe_text(text))
    pdf.ln(1)


def _draw_chips(pdf: ProfessionCvPdf, items: list[str]) -> None:
    tpl = pdf.template
    left = pdf.l_margin
    right = 210 - pdf.r_margin
    x = left
    y = pdf.get_y()
    pdf.set_font(tpl.font, "", 8)
    for item in items:
        label = pdf_safe_text(item)
        width = pdf.get_string_width(label) + 6
        if x + width > right:
            x = left
            y += 7
        if y > 270:
            pdf.add_page()
            y = pdf.get_y()
            x = left
        _set_fill(pdf, tpl.chip_bg)
        try:
            pdf.rounded_rect(x, y, width, 6, 1.4, "F")
        except Exception:
            pdf.rect(x, y, width, 6, "F")
        _set_text(pdf, tpl.chip_text)
        pdf.set_xy(x, y + 0.6)
        pdf.cell(width, 5, label, align="C")
        x += width + 2.2
    pdf.set_y(y + 9)


def _draw_bullets(pdf: ProfessionCvPdf, items: list[str]) -> None:
    tpl = pdf.template
    pdf.set_font(tpl.font, "", 9.5)
    _set_text(pdf, tpl.ink)
    bullet_x = pdf.l_margin
    text_x = pdf.l_margin + 4
    width = 210 - pdf.r_margin - text_x
    for item in items:
        if pdf.get_y() > 272:
            pdf.add_page()
        y = pdf.get_y()
        _set_fill(pdf, tpl.accent)
        pdf.ellipse(bullet_x + 0.6, y + 1.6, 1.5, 1.5, "F")
        pdf.set_xy(text_x, y)
        pdf.multi_cell(width, 4.6, pdf_safe_text(item))
        pdf.ln(0.4)


def _draw_experience(pdf: ProfessionCvPdf, job: ExperienceEntry) -> None:
    tpl = pdf.template
    if pdf.get_y() > 258:
        pdf.add_page()
    _set_text(pdf, tpl.ink)
    pdf.set_font(tpl.font, "B", 11)
    title = pdf_safe_text(job.title or "Poste")
    period = pdf_safe_text(job.period)
    pdf.cell(128, 6, title, align="L")
    if period:
        pdf.set_font(tpl.font, "", 9)
        _set_text(pdf, tpl.muted)
        pdf.cell(0, 6, period, align="R")
    pdf.ln(6)
    meta = "  ·  ".join(p for p in (job.company, job.location) if p)
    if meta:
        pdf.set_font(tpl.font, "I", 9.5)
        _set_text(pdf, tpl.accent)
        pdf.cell(0, 5, pdf_safe_text(meta), align="L")
        pdf.ln(5)
    if job.bullets:
        _draw_bullets(pdf, job.bullets)
    pdf.ln(1.5)


def _draw_education(pdf: ProfessionCvPdf, item: EducationEntry) -> None:
    tpl = pdf.template
    _set_text(pdf, tpl.ink)
    pdf.set_font(tpl.font, "B", 10.5)
    pdf.cell(128, 5.5, pdf_safe_text(item.diploma or item.school), align="L")
    if item.period:
        pdf.set_font(tpl.font, "", 9)
        _set_text(pdf, tpl.muted)
        pdf.cell(0, 5.5, pdf_safe_text(item.period), align="R")
    pdf.ln(5.5)
    if item.school and item.diploma:
        pdf.set_font(tpl.font, "I", 9.5)
        _set_text(pdf, tpl.accent)
        pdf.cell(0, 5, pdf_safe_text(item.school), align="L")
        pdf.ln(5)
    if item.details:
        pdf.set_font(tpl.font, "", 9)
        _set_text(pdf, tpl.ink)
        pdf.multi_cell(0, 4.5, pdf_safe_text(item.details))
    pdf.ln(1)


def render_cv_pdf(cv: StructuredCV) -> bytes:
    """Render a structured CV with the profession template."""
    tpl = template_for(cv.family)
    pdf = ProfessionCvPdf(tpl, cv.name or "Candidat", cv.title or tpl.label_fr)
    if tpl.layout == "academic":
        pdf.set_left_margin(18)
        pdf.set_right_margin(14)
    else:
        pdf.set_left_margin(14)
        pdf.set_right_margin(14)
    pdf.add_page()
    pdf.set_fill_color(*tpl.paper)

    if tpl.layout == "classic":
        _draw_classic_header(pdf, cv)
    elif tpl.layout == "academic":
        _draw_academic_header(pdf, cv)
    else:
        _draw_banner_header(pdf, cv, 42)

    extras_alias = {
        "projects": cv.extras.get("projects") or cv.extras.get("autres") or [],
        "publications": cv.extras.get("publications") or [],
        "licenses": cv.extras.get("licenses") or cv.extras.get("certifications") or [],
        "certifications": cv.extras.get("certifications") or cv.extras.get("licenses") or [],
        "interests": cv.extras.get("interests") or [],
    }

    for key in tpl.section_order:
        title = tpl.section_titles.get(key, key.upper())
        if key == "profile" and cv.profile:
            _section_title(pdf, title)
            _write_paragraph(pdf, cv.profile)
        elif key == "skills" and cv.skills:
            _section_title(pdf, title)
            _draw_chips(pdf, cv.skills)
        elif key == "languages" and cv.languages:
            _section_title(pdf, title)
            _draw_chips(pdf, cv.languages)
        elif key == "experience" and cv.experiences:
            _section_title(pdf, title)
            for job in cv.experiences:
                _draw_experience(pdf, job)
        elif key == "education" and cv.education:
            _section_title(pdf, title)
            for item in cv.education:
                _draw_education(pdf, item)
        elif key in extras_alias and extras_alias[key]:
            _section_title(pdf, title)
            _draw_bullets(pdf, extras_alias[key])

    if cv.raw_body and not (cv.profile or cv.experiences):
        _section_title(pdf, tpl.section_titles.get("profile", "PARCOURS"))
        _write_paragraph(pdf, cv.raw_body)

    return bytes(pdf.output())


def render_cover_letter_pdf(
    letter: str,
    *,
    job: dict[str, Any] | None = None,
    match: dict[str, Any] | None = None,
    user_profile: dict[str, Any] | None = None,
    family: str | None = None,
) -> bytes:
    """One-page professional letter using the same profession colors as the CV."""
    job = job or {}
    match = match or {}
    user_profile = user_profile or {}
    detected = family or detect_job_family(job, match)
    tpl = template_for(detected)
    name = str(user_profile.get("full_name") or "").strip() or "Candidat"
    title = str(match.get("titre_cv_recommande") or job.get("title") or tpl.label_fr)
    pdf = ProfessionCvPdf(tpl, name, title)
    pdf.set_left_margin(18)
    pdf.set_right_margin(18)
    pdf.add_page()
    _set_fill(pdf, tpl.primary)
    pdf.rect(0, 0, 210, 28, "F")
    _set_fill(pdf, tpl.accent)
    pdf.rect(0, 28, 210, 2.4, "F")
    _set_text(pdf, tpl.header_text)
    pdf.set_xy(18, 8)
    pdf.set_font(tpl.font, "B", 16)
    pdf.cell(0, 8, pdf_safe_text(name), align="L")
    pdf.set_xy(18, 16)
    pdf.set_font(tpl.font, "", 10)
    contact = "  ·  ".join(
        p
        for p in (
            str(user_profile.get("email") or "").strip(),
            str(user_profile.get("phone") or "").strip(),
        )
        if p
    )
    pdf.cell(0, 6, pdf_safe_text(contact or title), align="L")
    pdf.set_y(40)
    _set_text(pdf, tpl.muted)
    pdf.set_font(tpl.font, "I", 10)
    dest = "  ·  ".join(p for p in (str(job.get("company") or "").strip(), str(job.get("title") or "").strip()) if p)
    if dest:
        pdf.cell(0, 6, pdf_safe_text(f"Objet : candidature — {dest}"), align="L")
        pdf.ln(10)
    _set_text(pdf, tpl.ink)
    pdf.set_font(tpl.font, "", 11)
    body = (letter or "").strip() or "Lettre de motivation."
    pdf.multi_cell(0, 6, pdf_safe_text(body))
    return bytes(pdf.output())


def render_adapted_cv_pdf(
    adapted_text: str,
    *,
    job: dict[str, Any] | None = None,
    match: dict[str, Any] | None = None,
    user_profile: dict[str, Any] | None = None,
    original_cv: str = "",
) -> bytes:
    cv = prepare_structured_cv(
        adapted_text,
        job=job,
        match=match,
        user_profile=user_profile,
        original_cv=original_cv,
    )
    return render_cv_pdf(cv)


def render_cv_html(cv: StructuredCV) -> str:
    """HTML preview that mirrors the profession template (Streamlit)."""
    tpl = template_for(cv.family)
    esc = html.escape

    def chips(items: list[str]) -> str:
        if not items:
            return ""
        bits = "".join(
            f'<span style="display:inline-block;background:rgb{tpl.chip_bg};color:rgb{tpl.chip_text};'
            f'padding:3px 10px;border-radius:999px;margin:2px 4px 2px 0;font-size:12px;">{esc(item)}</span>'
            for item in items
        )
        return f"<div style='margin:6px 0 10px 0;'>{bits}</div>"

    def bullets(items: list[str]) -> str:
        if not items:
            return ""
        lis = "".join(f"<li style='margin:2px 0;'>{esc(item)}</li>" for item in items)
        return f"<ul style='margin:4px 0 10px 18px;padding:0;color:rgb{tpl.ink};font-size:13px;'>{lis}</ul>"

    blocks: list[str] = []
    contact = " · ".join(p for p in (cv.email, cv.phone, cv.location, cv.linkedin or cv.website) if p)
    if tpl.layout == "classic":
        header = (
            f"<div style='border-top:8px solid rgb{tpl.primary};border-bottom:3px solid rgb{tpl.accent};"
            f"padding:16px 18px 14px;text-align:center;background:#fff;'>"
            f"<div style='font-size:22px;font-weight:700;color:rgb{tpl.primary};letter-spacing:.04em;'>"
            f"{esc(cv.name or 'Candidat')}</div>"
            f"<div style='font-size:14px;font-style:italic;color:rgb{tpl.accent};margin-top:4px;'>"
            f"{esc(cv.title)}</div>"
            f"<div style='font-size:12px;color:rgb{tpl.muted};margin-top:6px;'>{esc(contact)}</div></div>"
        )
    elif tpl.layout == "academic":
        header = (
            f"<div style='border-left:10px solid rgb{tpl.primary};padding:14px 18px;background:#fff;'>"
            f"<div style='font-size:22px;font-weight:700;color:rgb{tpl.primary};'>{esc(cv.name or 'Candidat')}</div>"
            f"<div style='font-size:14px;font-style:italic;color:rgb{tpl.accent};'>{esc(cv.title)}</div>"
            f"<div style='font-size:12px;color:rgb{tpl.muted};margin-top:4px;'>{esc(contact)}</div></div>"
        )
    else:
        header = (
            f"<div style='background:rgb{tpl.primary};color:rgb{tpl.header_text};padding:18px 20px 16px;"
            f"border-bottom:4px solid rgb{tpl.accent};'>"
            f"<div style='font-size:22px;font-weight:700;letter-spacing:.03em;'>{esc(cv.name or 'Candidat')}</div>"
            f"<div style='font-size:14px;opacity:.92;margin-top:4px;'>{esc(cv.title)}</div>"
            f"<div style='font-size:12px;opacity:.85;margin-top:8px;'>{esc(contact)}</div></div>"
        )
    blocks.append(header)

    extras_alias = {
        "projects": cv.extras.get("projects") or [],
        "publications": cv.extras.get("publications") or [],
        "licenses": cv.extras.get("licenses") or cv.extras.get("certifications") or [],
        "certifications": cv.extras.get("certifications") or [],
        "interests": cv.extras.get("interests") or [],
    }
    body_parts: list[str] = []
    for key in tpl.section_order:
        title = tpl.section_titles.get(key, key.upper())
        section_html = ""
        if key == "profile" and cv.profile:
            section_html = f"<p style='margin:6px 0 10px;font-size:13px;line-height:1.45;color:rgb{tpl.ink};'>{esc(cv.profile)}</p>"
        elif key == "skills" and cv.skills:
            section_html = chips(cv.skills)
        elif key == "languages" and cv.languages:
            section_html = chips(cv.languages)
        elif key == "experience" and cv.experiences:
            bits = []
            for job in cv.experiences:
                meta = " · ".join(p for p in (job.company, job.location, job.period) if p)
                bits.append(
                    f"<div style='margin:8px 0 12px;'><div style='font-weight:700;color:rgb{tpl.ink};'>"
                    f"{esc(job.title)}</div><div style='font-size:12px;color:rgb{tpl.accent};'>{esc(meta)}</div>"
                    f"{bullets(job.bullets)}</div>"
                )
            section_html = "".join(bits)
        elif key == "education" and cv.education:
            bits = []
            for item in cv.education:
                meta = " · ".join(p for p in (item.school, item.period) if p)
                bits.append(
                    f"<div style='margin:6px 0;'><strong>{esc(item.diploma)}</strong>"
                    f"<div style='font-size:12px;color:rgb{tpl.accent};'>{esc(meta)}</div></div>"
                )
            section_html = "".join(bits)
        elif key in extras_alias and extras_alias[key]:
            section_html = bullets(extras_alias[key])
        if not section_html:
            continue
        body_parts.append(
            f"<div style='margin-top:14px;'><div style='font-size:11px;font-weight:700;letter-spacing:.08em;"
            f"color:rgb{tpl.primary};'>{esc(title)}</div>"
            f"<div style='width:52px;height:3px;background:rgb{tpl.accent};margin:4px 0 8px;'></div>"
            f"{section_html}</div>"
        )
    if cv.raw_body and not body_parts:
        body_parts.append(
            f"<p style='white-space:pre-wrap;font-size:13px;color:rgb{tpl.ink};'>{esc(cv.raw_body)}</p>"
        )
    inner = "".join(body_parts)
    return (
        f"<div style='font-family:Georgia,Times,serif;background:rgb{tpl.paper};border:1px solid #e5e7eb;"
        f"border-radius:10px;overflow:hidden;margin:4px 0 12px;'>{''.join(blocks)}"
        f"<div style='padding:8px 20px 20px;'>{inner}</div></div>"
    )


def build_cv_system_addon(family: str) -> str:
    """Extra instructions injected into the adapted-CV LLM prompt."""
    tpl = template_for(family)
    return (
        f"\nTemplate metier impose : {tpl.label_fr} ({tpl.family}).\n"
        "Respecte EXACTEMENT les titres de sections ci-dessous (markdown ##).\n"
        "Commence par les champs :\n"
        "NOM: ...\nTITRE: ...\nEMAIL: ...\nTELEPHONE: ...\nVILLE: ...\n"
        f"{tpl.llm_sections}\n"
        "Ne change pas les faits du CV original. Pas de JSON."
    )


def cv_pdf_filename(job: dict[str, Any] | None = None, family: str = "generic") -> str:
    title = _slug_filename(str((job or {}).get("title") or family), fallback="cv")
    return f"cv_{family}_{title}.pdf"


def letter_pdf_filename(job: dict[str, Any] | None = None) -> str:
    title = _slug_filename(str((job or {}).get("title") or "offre"), fallback="lettre")
    return f"lettre_{title}.pdf"


def application_document_attachments(
    letter: str,
    adapted: str,
    *,
    job: dict[str, Any] | None = None,
    match: dict[str, Any] | None = None,
    user_profile: dict[str, Any] | None = None,
    original_cv: str = "",
) -> list[tuple[str, bytes, str]]:
    """PDF attachments for recruiter / candidate e-mails."""
    job = job or {}
    match = match or {}
    user_profile = user_profile or {}
    family = detect_job_family(job, match)
    clean_cv = cv_text_for_candidate(adapted)
    cv_pdf = render_adapted_cv_pdf(
        clean_cv,
        job=job,
        match=match,
        user_profile=user_profile,
        original_cv=original_cv,
    )
    letter_pdf = render_cover_letter_pdf(
        letter,
        job=job,
        match=match,
        user_profile=user_profile,
        family=family,
    )
    return [
        (cv_pdf_filename(job, family), cv_pdf, "application/pdf"),
        (letter_pdf_filename(job), letter_pdf, "application/pdf"),
    ]
