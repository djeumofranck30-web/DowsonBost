"""UI internationalization — French (default) and English."""

from __future__ import annotations

from typing import Any

DEFAULT_LOCALE = "fr"
SUPPORTED_LOCALES = ("fr", "en")
LOCALE_LABELS = {"fr": "Français", "en": "English"}

_MESSAGES: dict[str, dict[str, str]] = {
    "fr": {
        "language.label": "Langue",
        "nav.analysis": "Analyse CV",
        "nav.dashboard": "Tableau de bord",
        "nav.history": "Historique",
        "nav.profile": "Mon profil",
        "common.email": "E-mail",
        "common.password": "Mot de passe",
        "common.full_name": "Nom complet",
        "common.save": "Enregistrer",
        "common.cancel": "Annuler",
        "common.user": "Utilisateur",
        "auth.greeting.morning": "Bonjour !",
        "auth.greeting.morning_sub": "Bonne matinée",
        "auth.greeting.afternoon_sub": "Bon après-midi",
        "auth.greeting.evening": "Bonsoir !",
        "auth.greeting.evening_sub": "Bonne soirée",
        "auth.greeting.night_sub": "Bonne nuit",
        "auth.left.title": "Connectez-vous pour accéder à\nl'expérience complète {app_name}",
        "auth.left.tip": "Astuce : complétez votre profil pour un matching d'offres plus précis.",
        "auth.login.title": "Connectez-vous à votre compte",
        "auth.login.submit": "Se connecter",
        "auth.login.forgot": "Mot de passe oublié ?",
        "auth.login.success": "Connexion réussie.",
        "auth.login.invalid": "E-mail ou mot de passe incorrect.",
        "auth.login.required": "E-mail et mot de passe requis.",
        "auth.register.welcome": "Bienvenue !",
        "auth.register.subtitle": "Créer un compte",
        "auth.register.step1": "Étape 1 — Quel poste visez-vous ?",
        "auth.register.step2": "Étape 2 — Votre profil de recherche",
        "auth.register.location": "Localisation",
        "auth.register.job_title": "Intitulé du poste visé",
        "auth.register.job_title_ph": "Ex. Développeur Python, Technicien réseau…",
        "auth.register.job_title_help": "L'IA utilisera ce titre pour rechercher des offres correspondantes.",
        "auth.register.prefs": "Préférences de recherche d'emploi",
        "auth.register.contract": "Type de contrat recherché",
        "auth.register.geo_mode": "Périmètre géographique",
        "auth.register.radius": "Rayon (km)",
        "auth.register.experience": "Niveau d'expérience recherché",
        "auth.register.sectors": "Secteurs d'activité ciblés (optionnel)",
        "auth.register.publication": "Rechercher les offres publiées depuis :",
        "auth.register.publication_help": "Seules les offres publiées dans cette période seront recherchées.",
        "auth.register.submit": "Créer mon compte",
        "auth.register.password_confirm": "Confirmer le mot de passe",
        "auth.register.password_mismatch": "Les mots de passe ne correspondent pas.",
        "auth.register.success": "Compte créé avec succès. Vous pouvez vous connecter.",
        "auth.register.email_exists": "Un compte existe déjà avec cet e-mail.",
        "auth.footer.create": "Créer un compte",
        "auth.footer.back_login": "← Retour à la connexion",
        "auth.reset.title": "Réinitialisation",
        "auth.reset.subtitle": "Nouveau mot de passe",
        "auth.reset.form_title": "E-mail et nom complet identiques à l'inscription",
        "auth.reset.new_password": "Nouveau mot de passe",
        "auth.reset.confirm": "Confirmer le nouveau mot de passe",
        "auth.reset.submit": "Réinitialiser le mot de passe",
        "auth.reset.success": "Mot de passe réinitialisé. Vous pouvez vous connecter.",
        "auth.reset.not_found": "Aucun compte trouvé avec cet e-mail.",
        "auth.reset.name_mismatch": "Le nom complet ne correspond pas à ce compte.",
        "auth.password.min": "Le mot de passe doit contenir au moins {min} caractères.",
        "auth.password.same": "Le nouveau mot de passe doit être différent de l'actuel.",
        "auth.password.changed": "Mot de passe modifié avec succès.",
        "auth.password.current_wrong": "Mot de passe actuel incorrect.",
        "auth.name.min": "Le nom doit contenir au moins 2 caractères.",
        "auth.email.invalid": "Adresse e-mail invalide.",
        "auth.profile.updated": "Profil mis à jour.",
        "auth.profile.not_found": "Utilisateur introuvable.",
        "auth.account.deleted": "Votre compte a été supprimé définitivement.",
        "auth.validation.job_title": "Indiquez l'intitulé du poste visé (au moins 2 caractères).",
        "auth.validation.home_city": "La ville de domicile doit contenir au moins 2 caractères.",
        "auth.validation.postal": "Code postal invalide (4 ou 5 chiffres).",
        "auth.validation.region_fr": "Sélectionnez au moins une région (France).",
        "auth.validation.dept_fr": "Sélectionnez au moins un département (France).",
        "auth.validation.city_fr": "Sélectionnez au moins une ville ou cochez « Toutes les villes ».",
        "auth.validation.contract": "Type de contrat invalide.",
        "auth.validation.geo_mode": "Mode géographique invalide.",
        "auth.validation.radius": "Le rayon doit être entre 5 et 200 km.",
        "auth.validation.experience": "Niveau d'expérience invalide.",
        "auth.validation.sectors": "Secteur(s) invalide(s) : {sectors}.",
        "geo.select_countries": "Sélectionnez au moins un pays.",
        "geo.select_region": "{country} : sélectionnez au moins une région.",
        "geo.select_department": "{country} : sélectionnez au moins un département.",
        "geo.select_city": "{country} : sélectionnez une ville ou « Toutes les villes ».",
        "geo.select_zone_or_city": "{country} : sélectionnez au moins un(e) {zone} ou une ville.",
        "geo.select_city_only": "{country} : sélectionnez au moins une ville.",
        "geo.select_zone": "{country} : sélectionnez au moins un(e) {zone}.",
        "app.logout": "Se déconnecter",
        "app.job_provider": "Moteur(s) de recherche d'emploi",
        "app.analysis_depth": "Profondeur d'analyse",
        "app.config_tests": "Configuration & tests",
        "app.version": "Version",
        "app.clear_cache": "Vider le cache",
        "app.cache_cleared": "Cache vidé.",
        "hero.analysis.title": "Analyse CV",
        "hero.analysis.subtitle": "Bienvenue {name} — déposez votre CV : l'IA recherche les offres puis analyse votre profil en mode ATS.",
        "hero.analysis.badge": "Matching IA",
        "hero.dashboard.title": "Tableau de bord",
        "hero.dashboard.subtitle": "Suivez vos candidatures, filtrez par statut et générez lettres / CV adaptés.",
        "hero.dashboard.badge": "Suivi",
        "hero.history.title": "Historique",
        "hero.history.subtitle": "Consultez vos analyses passées et rechargez un rapport complet.",
        "hero.history.badge": "Archives",
        "hero.profile.title": "Mon profil",
        "hero.profile.subtitle": "Gérez votre identité, vos critères de recherche, la sécurité du compte et les alertes.",
        "hero.profile.badge": "Compte",
        "profile.member_since": "Membre depuis {date}",
        "profile.search_section": "Profil de recherche",
        "profile.search_hint": "Ces réglages sont utilisés pour filtrer les offres et lancer vos analyses CV.",
        "profile.countries": "Pays de recherche",
        "profile.countries_help": "Sélectionnez un ou plusieurs pays (ISO 3166-1). Seules les offres dans ces pays seront proposées.",
        "profile.geo_by_country": "Périmètre géographique par pays",
        "profile.target_job": "Poste visé",
        "profile.target_job_help": "Utilisé en priorité pour la recherche d'offres.",
        "profile.contract": "Type de contrat",
        "profile.experience": "Niveau d'expérience",
        "profile.geo_mode": "Périmètre géographique",
        "profile.sectors": "Secteurs ciblés",
        "profile.sectors_help": "Laisser vide pour utiliser les secteurs détectés dans le CV.",
        "profile.radius": "Rayon (km)",
        "profile.publication": "Période de publication",
        "profile.save": "Enregistrer le profil",
        "profile.password_section": "Mot de passe",
        "profile.current_password": "Mot de passe actuel",
        "profile.new_password": "Nouveau mot de passe",
        "profile.confirm_password": "Confirmer",
        "profile.change_password": "Modifier le mot de passe",
        "profile.password_mismatch": "Les nouveaux mots de passe ne correspondent pas.",
        "geo_mode.ville": "Villes sélectionnées",
        "geo_mode.departement": "Régions, départements & villes",
        "geo_mode.rayon": "Zones + rayon autour d'une ville",
        "geo_mode.register.ville": "Villes sélectionnées uniquement",
        "geo_mode.register.departement": "Pays, régions, départements et villes sélectionnés",
        "geo_mode.register.rayon": "Zones sélectionnées + rayon autour de la première ville",
        "depth.rapide": "Rapide — 15 offres (~2× plus vite)",
        "depth.standard": "Standard — 30 offres (recommandé)",
        "depth.complet": "Complet — 45 offres analysées (plus lent)",
        "matching.profile_incomplete": "Complétez le poste visé, vos pays et zones géographiques et votre type de contrat dans Mon profil.",
        "matching.missing_job_title": "Indiquez le poste visé dans Mon profil.",
        "matching.missing_contract": "Sélectionnez votre type de contrat dans Mon profil.",
        "matching.missing_countries": "Sélectionnez au moins un pays dans Mon profil.",
        "experience.junior": "Junior",
        "experience.confirme": "Confirmé",
        "experience.senior": "Senior",
        "experience.tous": "Tous niveaux",
        "job_age.1": "24 dernières heures",
        "job_age.3": "3 derniers jours",
        "job_age.7": "7 derniers jours",
        "job_age.30": "30 derniers jours",
        "placeholder.email": "vous@exemple.com",
        "placeholder.password": "••••••••",
        "placeholder.name": "Jean Dupont",
        "placeholder.password_min": "8 caractères minimum",
    },
    "en": {
        "language.label": "Language",
        "nav.analysis": "CV Analysis",
        "nav.dashboard": "Dashboard",
        "nav.history": "History",
        "nav.profile": "My profile",
        "common.email": "Email",
        "common.password": "Password",
        "common.full_name": "Full name",
        "common.save": "Save",
        "common.cancel": "Cancel",
        "common.user": "User",
        "auth.greeting.morning": "Good morning!",
        "auth.greeting.morning_sub": "Have a great morning",
        "auth.greeting.afternoon_sub": "Good afternoon",
        "auth.greeting.evening": "Good evening!",
        "auth.greeting.evening_sub": "Have a nice evening",
        "auth.greeting.night_sub": "Good night",
        "auth.left.title": "Sign in to access the full\n{app_name} experience",
        "auth.left.tip": "Tip: complete your profile for more accurate job matching.",
        "auth.login.title": "Sign in to your account",
        "auth.login.submit": "Sign in",
        "auth.login.forgot": "Forgot password?",
        "auth.login.success": "Signed in successfully.",
        "auth.login.invalid": "Incorrect email or password.",
        "auth.login.required": "Email and password are required.",
        "auth.register.welcome": "Welcome!",
        "auth.register.subtitle": "Create an account",
        "auth.register.step1": "Step 1 — What role are you targeting?",
        "auth.register.step2": "Step 2 — Your search profile",
        "auth.register.location": "Location",
        "auth.register.job_title": "Target job title",
        "auth.register.job_title_ph": "e.g. Python Developer, Network Technician…",
        "auth.register.job_title_help": "The AI will use this title to search for matching jobs.",
        "auth.register.prefs": "Job search preferences",
        "auth.register.contract": "Contract type sought",
        "auth.register.geo_mode": "Geographic scope",
        "auth.register.radius": "Radius (km)",
        "auth.register.experience": "Experience level sought",
        "auth.register.sectors": "Target sectors (optional)",
        "auth.register.publication": "Search jobs published within:",
        "auth.register.publication_help": "Only jobs published in this period will be searched.",
        "auth.register.submit": "Create my account",
        "auth.register.password_confirm": "Confirm password",
        "auth.register.password_mismatch": "Passwords do not match.",
        "auth.register.success": "Account created. You can sign in now.",
        "auth.register.email_exists": "An account already exists with this email.",
        "auth.footer.create": "Create an account",
        "auth.footer.back_login": "← Back to sign in",
        "auth.reset.title": "Reset password",
        "auth.reset.subtitle": "New password",
        "auth.reset.form_title": "Same email and full name as registration",
        "auth.reset.new_password": "New password",
        "auth.reset.confirm": "Confirm new password",
        "auth.reset.submit": "Reset password",
        "auth.reset.success": "Password reset. You can sign in now.",
        "auth.reset.not_found": "No account found with this email.",
        "auth.reset.name_mismatch": "Full name does not match this account.",
        "auth.password.min": "Password must be at least {min} characters.",
        "auth.password.same": "New password must differ from the current one.",
        "auth.password.changed": "Password changed successfully.",
        "auth.password.current_wrong": "Current password is incorrect.",
        "auth.name.min": "Name must be at least 2 characters.",
        "auth.email.invalid": "Invalid email address.",
        "auth.profile.updated": "Profile updated.",
        "auth.profile.not_found": "User not found.",
        "auth.account.deleted": "Your account has been permanently deleted.",
        "auth.validation.job_title": "Enter a target job title (at least 2 characters).",
        "auth.validation.home_city": "Home city must be at least 2 characters.",
        "auth.validation.postal": "Invalid postal code (4 or 5 digits).",
        "auth.validation.region_fr": "Select at least one region (France).",
        "auth.validation.dept_fr": "Select at least one department (France).",
        "auth.validation.city_fr": "Select at least one city or check « All cities ».",
        "auth.validation.contract": "Invalid contract type.",
        "auth.validation.geo_mode": "Invalid geographic mode.",
        "auth.validation.radius": "Radius must be between 5 and 200 km.",
        "auth.validation.experience": "Invalid experience level.",
        "auth.validation.sectors": "Invalid sector(s): {sectors}.",
        "geo.select_countries": "Select at least one country.",
        "geo.select_region": "{country}: select at least one region.",
        "geo.select_department": "{country}: select at least one department.",
        "geo.select_city": "{country}: select a city or « All cities ».",
        "geo.select_zone_or_city": "{country}: select at least one {zone} or a city.",
        "geo.select_city_only": "{country}: select at least one city.",
        "geo.select_zone": "{country}: select at least one {zone}.",
        "app.logout": "Sign out",
        "app.job_provider": "Job search engine(s)",
        "app.analysis_depth": "Analysis depth",
        "app.config_tests": "Settings & tests",
        "app.version": "Version",
        "app.clear_cache": "Clear cache",
        "app.cache_cleared": "Cache cleared.",
        "hero.analysis.title": "CV Analysis",
        "hero.analysis.subtitle": "Welcome {name} — upload your CV: the AI searches jobs then analyzes your profile in ATS mode.",
        "hero.analysis.badge": "AI Matching",
        "hero.dashboard.title": "Dashboard",
        "hero.dashboard.subtitle": "Track applications, filter by status, and generate cover letters / tailored CVs.",
        "hero.dashboard.badge": "Tracking",
        "hero.history.title": "History",
        "hero.history.subtitle": "Browse past analyses and reload a full report.",
        "hero.history.badge": "Archives",
        "hero.profile.title": "My profile",
        "hero.profile.subtitle": "Manage identity, search criteria, account security, and alerts.",
        "hero.profile.badge": "Account",
        "profile.member_since": "Member since {date}",
        "profile.search_section": "Search profile",
        "profile.search_hint": "These settings filter jobs and power your CV analyses.",
        "profile.countries": "Search countries",
        "profile.countries_help": "Select one or more countries (ISO 3166-1). Only jobs in these countries will be shown.",
        "profile.geo_by_country": "Geographic scope by country",
        "profile.target_job": "Target role",
        "profile.target_job_help": "Used first for job search.",
        "profile.contract": "Contract type",
        "profile.experience": "Experience level",
        "profile.geo_mode": "Geographic scope",
        "profile.sectors": "Target sectors",
        "profile.sectors_help": "Leave empty to use sectors detected in your CV.",
        "profile.radius": "Radius (km)",
        "profile.publication": "Publication period",
        "profile.save": "Save profile",
        "profile.password_section": "Password",
        "profile.current_password": "Current password",
        "profile.new_password": "New password",
        "profile.confirm_password": "Confirm",
        "profile.change_password": "Change password",
        "profile.password_mismatch": "New passwords do not match.",
        "geo_mode.ville": "Selected cities only",
        "geo_mode.departement": "Regions, departments & cities",
        "geo_mode.rayon": "Zones + radius around a city",
        "geo_mode.register.ville": "Selected cities only",
        "geo_mode.register.departement": "Selected countries, regions, departments and cities",
        "geo_mode.register.rayon": "Selected zones + radius around the first city",
        "depth.rapide": "Fast — 15 jobs (~2× faster)",
        "depth.standard": "Standard — 30 jobs (recommended)",
        "depth.complet": "Full — 45 jobs analyzed (slower)",
        "matching.profile_incomplete": "Complete your target role, countries/zones, and contract type in My profile.",
        "matching.missing_job_title": "Enter your target role in My profile.",
        "matching.missing_contract": "Select your contract type in My profile.",
        "matching.missing_countries": "Select at least one country in My profile.",
        "experience.junior": "Junior",
        "experience.confirme": "Mid-level",
        "experience.senior": "Senior",
        "experience.tous": "All levels",
        "job_age.1": "Last 24 hours",
        "job_age.3": "Last 3 days",
        "job_age.7": "Last 7 days",
        "job_age.30": "Last 30 days",
        "placeholder.email": "you@example.com",
        "placeholder.password": "••••••••",
        "placeholder.name": "John Doe",
        "placeholder.password_min": "8 characters minimum",
    },
}


def normalize_locale(value: str | None) -> str:
    code = (value or DEFAULT_LOCALE).strip().lower()
    if code.startswith("en"):
        return "en"
    if code in SUPPORTED_LOCALES:
        return code
    return DEFAULT_LOCALE


def get_locale() -> str:
    try:
        import streamlit as st

        stored = st.session_state.get("locale")
        if stored:
            return normalize_locale(stored)
        user = st.session_state.get("user")
        if isinstance(user, dict) and user.get("preferred_language"):
            return normalize_locale(str(user["preferred_language"]))
        query_lang = st.query_params.get("lang")
        if isinstance(query_lang, list):
            query_lang = query_lang[0] if query_lang else ""
        if query_lang:
            return normalize_locale(str(query_lang))
    except Exception:
        pass
    return DEFAULT_LOCALE


def set_locale(locale: str) -> str:
    locale = normalize_locale(locale)
    try:
        import streamlit as st

        st.session_state.locale = locale
        st.query_params["lang"] = locale
    except Exception:
        pass
    return locale


def init_locale() -> str:
    locale = get_locale()
    try:
        import streamlit as st

        st.session_state.locale = locale
    except Exception:
        pass
    return locale


def t(key: str, *, locale: str | None = None, **kwargs: Any) -> str:
    lang = normalize_locale(locale or get_locale())
    template = _MESSAGES.get(lang, {}).get(key) or _MESSAGES[DEFAULT_LOCALE].get(key, key)
    if kwargs:
        try:
            return template.format(**kwargs)
        except KeyError:
            return template
    return template


def nav_label(page_key: str) -> str:
    return t(f"nav.{page_key}")


def geo_mode_label(mode: str, *, register: bool = False) -> str:
    prefix = "geo_mode.register." if register else "geo_mode."
    return t(f"{prefix}{mode}")


def experience_label(level: str) -> str:
    return t(f"experience.{level}")


def job_age_label(days: int) -> str:
    return t(f"job_age.{days}")
