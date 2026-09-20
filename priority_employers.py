"""Priority French employers: search first, and always try hard to find an apply e-mail.

When analysis finds an opening at one of these companies, recruiter-email lookup
uses the mapped mailbox domain, career-site pages, Hunter.io, then generic HR
inboxes (recrutement@, jobs@, …) verified through Hunter.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any, NamedTuple

PRIORITY_EMPLOYER_RANK_BONUS = 80

_GENERIC_HR_LOCAL_PARTS = (
    "recrutement",
    "recruitment",
    "candidature",
    "candidatures",
    "jobs",
    "rh",
    "talent",
    "careers",
)


class PriorityEmployer(NamedTuple):
    name: str
    aliases: tuple[str, ...]
    domain: str
    career_hosts: tuple[str, ...] = ()
    greenhouse: str = ""
    lever: str = ""
    smartrecruiters: str = ""


# name, extra aliases (name is always an alias), mailbox domain, career hosts,
# optional Greenhouse / Lever / SmartRecruiters tokens.
_ROWS: tuple[tuple[object, ...], ...] = (
    ("SNCF", "sncf voyageurs|sncf connect|sncf reseau", "sncf.fr", "emplois.sncf.com|jobs.sncf.com", "", "", ""),
    ("RATP", "ratp group", "ratp.fr", "carrieres.ratp.fr|emploi.ratp.fr", "", "", ""),
    ("Orange", "orange sa|orange france", "orange.com", "orange.jobs|jobs.orange.com", "", "", ""),
    ("Capgemini", "capgemini france|capgemini invent", "capgemini.com", "jobs.capgemini.com|careers.capgemini.com", "", "", ""),
    ("Sopra Steria", "soprasteria|sopra", "soprasteria.com", "careers.soprasteria.com|jobs.soprasteria.com", "", "", ""),
    ("Atos", "atos france", "atos.net", "jobs.atos.net|careers.atos.net", "", "", ""),
    ("Eviden", "eviden france", "eviden.com", "careers.eviden.com|jobs.eviden.com", "", "", ""),
    ("Inetum", "inetum france", "inetum.com", "jobs.inetum.com|careers.inetum.com", "", "", ""),
    ("Bouygues Telecom", "bouyguestelecom", "bouyguestelecom.fr", "jobs.bouyguestelecom.fr|carrieres.bouyguestelecom.fr", "", "", ""),
    ("SFR", "altice france|sfr business", "sfr.fr", "jobs.sfr.fr|recrutement.sfr.fr", "", "", ""),
    ("La Poste", "groupe la poste|laposte", "laposte.fr", "laposterecrute.fr", "", "", ""),
    ("DocaPoste", "docaposte", "docaposte.com", "carrieres.docaposte.com|jobs.docaposte.com", "", "", ""),
    ("Crédit Agricole", "credit agricole|ca-cib|ca cib|groupe credit agricole", "credit-agricole.com", "jobs.credit-agricole.com|groupecreditagricole.jobs", "", "", ""),
    ("BNP Paribas", "bnpparibas|bnp", "bnpparibas.com", "group.bnpparibas.com|careers.bnpparibas", "", "", ""),
    ("Société Générale", "societe generale|socgen", "societegenerale.com", "careers.societegenerale.com|emplois.societegenerale.com", "", "", ""),
    ("Airbus", "airbus group", "airbus.com", "careers.airbus.com", "", "", ""),
    ("Thales", "thales group|thalesgroup", "thalesgroup.com", "careers.thalesgroup.com|jobs.thalesgroup.com|emploi.thalesgroup.com", "", "", "thales"),
    ("Safran", "safran group", "safran-group.com", "jobs.safran-group.com|careers.safran-group.com", "", "", ""),
    ("Amazon France", "amazon|amazon.fr", "amazon.com", "amazon.jobs", "", "", ""),
    ("Carrefour", "carrefour france|groupe carrefour", "carrefour.com", "jobs.carrefour.com|recrutement.carrefour.fr", "", "", ""),
    ("Lidl France", "lidl", "lidl.fr", "recrutement.lidl.fr|jobs.lidl.fr", "", "", ""),
    ("Decathlon", "decathlon france", "decathlon.com", "jobs.decathlon.fr|decathlon.jobs", "", "", ""),
    ("OVHcloud", "ovh cloud|ovh", "ovhcloud.com", "careers.ovhcloud.com", "", "", ""),
    ("Dassault Systèmes", "dassault systemes|3ds|3ds.com", "3ds.com", "careers.3ds.com", "", "", ""),
    ("IBM France", "ibm", "ibm.com", "careers.ibm.com", "", "", ""),
    ("CGI France", "cgi", "cgi.com", "jobs.cgi.com", "", "", ""),
    ("Accenture France", "accenture", "accenture.com", "careers.accenture.com", "", "", ""),
    ("DXC Technology", "dxc", "dxc.com", "careers.dxc.com", "", "", ""),
    ("Orange Cyberdefense", "orange cyber defense", "orangecyberdefense.com", "orangecyberdefense.com", "", "", ""),
    ("Thales Cybersecurity", "thales cyber|thales cyber solutions", "thalesgroup.com", "careers.thalesgroup.com", "", "", "thales"),
    ("Airbus Cybersecurity", "airbus cyber", "airbus.com", "careers.airbus.com", "", "", ""),
    ("Sopra Steria Cyber", "sopra steria cybersecurity|soprasteria cyber", "soprasteria.com", "careers.soprasteria.com", "", "", ""),
    ("Capgemini Cybersecurity", "capgemini cyber|capgemini security", "capgemini.com", "jobs.capgemini.com", "", "", ""),
    ("Stormshield", "", "stormshield.com", "jobs.stormshield.com|careers.stormshield.com", "", "", ""),
    ("Sekoia.io", "sekoia", "sekoia.io", "sekoia.io", "sekoia", "", ""),
    ("I-Trust", "itrust|i trust", "i-trust.fr", "i-trust.fr", "", "", ""),
    ("Wavestone Cyber", "wavestone", "wavestone.com", "careers.wavestone.com", "", "", ""),
    ("CyberProtect", "cyber protect", "cyberprotect.fr", "cyberprotect.fr", "", "", ""),
    ("RandoriSec", "randori sec", "randorisec.fr", "randorisec.fr", "", "", ""),
    ("Digital Security", "digital.security", "orangecyberdefense.com", "orangecyberdefense.com", "", "", ""),
    ("ANSSI", "agence nationale de la securite des systemes d'information", "ssi.gouv.fr", "ssi.gouv.fr|cyber.gouv.fr", "", "", ""),
    ("Amossys", "", "amossys.fr", "amossys.fr", "", "", ""),
    ("BPCE", "groupe bpce", "bpce.fr", "groupebpce.com|jobs.bpce.fr", "", "", ""),
    ("AXA", "axa france", "axa.com", "careers.axa.com", "", "", ""),
    ("Groupama", "groupama france", "groupama.com", "jobs.groupama.fr|groupama.com", "", "", ""),
    ("Allianz France", "allianz", "allianz.fr", "careers.allianz.com|allianz.fr", "", "", ""),
    ("MAIF", "", "maif.fr", "maif.fr", "", "", ""),
    ("MACIF", "", "macif.fr", "macif.fr", "", "", ""),
    ("Caisse d'Épargne", "caisse d epargne|caisses d epargne", "caisse-epargne.fr", "recrutement.caisse-epargne.fr", "", "", ""),
    ("Dassault Aviation", "", "dassault-aviation.com", "dassault-aviation.com", "", "", ""),
    ("Naval Group", "navalgroup", "naval-group.com", "jobs.naval-group.com|naval-group.com", "", "", ""),
    ("ArianeGroup", "ariane group", "arianegroup.com", "arianegroup.com", "", "", ""),
    ("Schneider Electric", "schneider", "se.com", "careers.se.com|jobs.se.com", "", "", ""),
    ("Alstom", "alstom france", "alstom.com", "jobs.alstom.com|careers.alstom.com", "", "", ""),
    ("Renault Group", "renault", "renault.com", "renaultgroup.com|jobs.renaultgroup.com", "", "", ""),
    ("Stellantis", "", "stellantis.com", "careers.stellantis.com", "", "", ""),
    ("Auchan", "auchan retail", "auchan.fr", "jobs.auchan.fr|auchan-retail.com", "", "", ""),
    ("Leclerc", "e.leclerc|e leclerc", "leclerc.fr", "recrutement.leclerc", "", "", ""),
    ("Cdiscount", "", "cdiscount.com", "jobs.cdiscount.com", "cdiscount", "", ""),
    ("Fnac Darty", "fnac|darty", "fnacdarty.com", "fnacdarty.com", "", "", ""),
    ("Leroy Merlin", "leroymerlin", "leroymerlin.fr", "recrutement.leroymerlin.fr", "", "", ""),
    ("Doctolib", "", "doctolib.fr", "careers.doctolib.com", "doctolib", "", ""),
    ("Back Market", "backmarket", "backmarket.com", "jobs.backmarket.com", "backmarket", "", ""),
    ("Qonto", "", "qonto.com", "jobs.qonto.com", "", "qonto", ""),
    ("Alan", "alan insurance", "alan.com", "alan.com/jobs", "alan", "", ""),
    ("PayFit", "payfit france", "payfit.com", "jobs.payfit.com", "payfit", "", ""),
    ("Swile", "", "swile.co", "jobs.swile.co", "swile", "", ""),
    ("Lydia", "lydia solutions", "lydia-app.com", "lydia-app.com", "lydia", "", ""),
    ("ManoMano", "manomano", "manomano.com", "jobs.manomano.com", "manomano", "", ""),
    ("Malt", "", "malt.fr", "malt.com", "malt", "", ""),
    ("Mirakl", "", "mirakl.com", "jobs.mirakl.com", "mirakl", "", ""),
    ("Veolia", "veolia france", "veolia.com", "jobs.veolia.com", "", "", ""),
    ("Engie", "engie france", "engie.com", "jobs.engie.com", "", "", ""),
    ("EDF", "edf france", "edf.fr", "recrute.edf.fr", "", "", ""),
    ("TotalEnergies", "total energies|total", "totalenergies.com", "jobs.totalenergies.com", "", "", ""),
    ("Vinci", "vinci group|vinci energies", "vinci.com", "jobs.vinci.com", "", "", ""),
    ("Bouygues", "bouygues sa|bouygues construction", "bouygues.com", "jobs.bouygues.com", "", "", ""),
    ("Saint-Gobain", "saint gobain", "saint-gobain.com", "careers.saint-gobain.com", "", "", ""),
    ("Michelin", "michelin france", "michelin.com", "jobs.michelin.com", "", "", ""),
    ("Sanofi", "sanofi france", "sanofi.com", "careers.sanofi.com", "", "", ""),
    ("Servier", "servier france", "servier.com", "jobs.servier.com", "", "", ""),
    ("Pierre Fabre", "pierre-fabre", "pierre-fabre.com", "careers.pierre-fabre.com", "", "", ""),
    ("BioMérieux", "biomerieux", "biomerieux.com", "careers.biomerieux.com", "", "", ""),
    ("Korian", "clariane", "korian.com", "jobs.korian.com", "", "", ""),
    ("Elior Group", "elior", "eliorgroup.com", "jobs.eliorgroup.com", "", "", ""),
    ("Sodexo", "sodexo france", "sodexo.com", "careers.sodexo.com", "", "", ""),
    ("KPMG France", "kpmg", "kpmg.fr", "careers.kpmg.fr", "", "", ""),
    ("EY France", "ernst young|ey", "ey.com", "careers.ey.com", "", "", ""),
    ("PwC France", "pwc|pricewaterhousecoopers", "pwc.fr", "jobs.pwc.fr", "", "", ""),
    ("Deloitte France", "deloitte", "deloitte.fr", "careers.deloitte.fr", "", "", ""),
    ("Havas Group", "havas", "havas.com", "jobs.havas.com", "", "", ""),
    ("Publicis Groupe", "publicis", "publicisgroupe.com", "careers.publicisgroupe.com", "", "", ""),
    ("TF1", "groupe tf1", "tf1.fr", "groupe-tf1.fr", "", "", ""),
    ("France Télévisions", "france tv|francetelevisions", "francetelevisions.fr", "francetelevisions.fr", "", "", ""),
    ("Canal+", "canal plus|canalplus", "canalplus.com", "jobs.canalplus.com", "", "", ""),
    ("Free", "free mobile", "free.fr", "jobs.free.fr", "", "", ""),
    ("Iliad", "groupe iliad", "iliad.fr", "iliad.fr", "", "", ""),
    ("Ubisoft", "ubisoft france", "ubisoft.com", "jobs.ubisoft.com", "", "", ""),
    ("Gameloft", "", "gameloft.com", "jobs.gameloft.com", "", "", ""),
    ("Arkema", "", "arkema.com", "careers.arkema.com", "", "", ""),
    ("Air Liquide", "airliquide", "airliquide.com", "careers.airliquide.com", "", "", ""),
    ("Vallourec", "", "vallourec.com", "careers.vallourec.com", "", "", ""),
    ("Imerys", "", "imerys.com", "careers.imerys.com", "", "", ""),
    ("Eramet", "", "eramet.com", "careers.eramet.com", "", "", ""),
    ("Vicat", "", "vicat.com", "vicat.com", "", "", ""),
    ("LafargeHolcim France", "lafargeholcim|holcim france|holcim|lafarge", "holcim.com", "careers.holcim.com", "", "", ""),
    ("Ciments Calcia", "calcia|heidelberg materials france", "ciments-calcia.fr", "ciments-calcia.fr", "", "", ""),
    ("Knauf France", "knauf", "knauf.fr", "jobs.knauf.fr", "", "", ""),
    ("Rockwool France", "rockwool", "rockwool.com", "careers.rockwool.com", "", "", ""),
    ("Saint-Gobain PAM", "saint gobain pam|pam saint-gobain", "pamline.fr", "pamline.fr", "", "", ""),
    ("Saint-Gobain Sekurit", "saint gobain sekurit|sekurit", "saint-gobain-sekurit.com", "saint-gobain-sekurit.com", "", "", ""),
    ("Saint-Gobain Isover", "saint gobain isover|isover", "isover.fr", "isover.fr", "", "", ""),
    ("Saint-Gobain Weber", "saint gobain weber|weber saint-gobain", "weber.fr", "weber.fr", "", "", ""),
    ("Saint-Gobain Placo", "saint gobain placo|placo", "placo.fr", "placo.fr", "", "", ""),
    ("ArcelorMittal France", "arcelormittal|arcelor mittal", "arcelormittal.com", "jobs.arcelormittal.com", "", "", ""),
    ("Ugitech", "", "ugitech.com", "ugitech.com", "", "", ""),
    ("Aubert & Duval", "aubert et duval|aubert duval", "aubertduval.com", "aubertduval.com", "", "", ""),
    ("Fives Group", "fives", "fivesgroup.com", "careers.fivesgroup.com", "", "", ""),
    ("Daher", "daher group", "daher.com", "careers.daher.com", "", "", ""),
    ("Mecachrome", "", "mecachrome.com", "mecachrome.com", "", "", ""),
    ("Hutchinson", "hutchinson france", "hutchinson.com", "careers.hutchinson.com", "", "", ""),
    ("Hutchinson Aerospace", "hutchinson aero", "hutchinson.com", "careers.hutchinson.com", "", "", ""),
    ("Zodiac Aerospace", "zodiac aerospace safran|zodiac", "safran-group.com", "jobs.safran-group.com", "", "", ""),
    ("Nexans", "nexans france", "nexans.com", "careers.nexans.com", "", "", ""),
    ("Prysmian Group France", "prysmian|prysmian group", "prysmiangroup.com", "careers.prysmiangroup.com", "", "", ""),
    ("Sagemcom", "", "sagemcom.com", "sagemcom.com", "", "", ""),
    ("Somfy", "somfy france", "somfy.com", "jobs.somfy.com", "", "", ""),
    ("Legrand Data Center Solutions", "legrand dcs|legrand datacenter|legrand", "legrand.com", "careers.legrand.com", "", "", ""),
    ("Schneider Digital", "schneider electric digital", "se.com", "careers.se.com", "", "", ""),
    ("Rexel France", "rexel", "rexel.fr", "jobs.rexel.fr", "", "", ""),
    ("Rexel Data Solutions", "rexel data", "rexel.com", "jobs.rexel.com", "", "", ""),
    ("Sonepar France", "sonepar", "sonepar.com", "careers.sonepar.com", "", "", ""),
    ("Würth France", "wurth|wurth france", "wurth.fr", "jobs.wurth.fr", "", "", ""),
    ("Manitou Group", "manitou", "manitou.com", "careers.manitou.com", "", "", ""),
    ("Haulotte Group", "haulotte", "haulotte.com", "jobs.haulotte.com", "", "", ""),
    ("Poclain Hydraulics", "poclain", "poclain-hydraulics.com", "poclain-hydraulics.com", "", "", ""),
    ("Liebherr France", "liebherr", "liebherr.com", "liebherr.com", "", "", ""),
    ("Caterpillar France", "caterpillar|cat france", "caterpillar.com", "careers.caterpillar.com", "", "", ""),
    ("Komatsu France", "komatsu", "komatsu.eu", "komatsu.eu", "", "", ""),
    ("CNH Industrial France", "cnh industrial|cnh", "cnhindustrial.com", "careers.cnhindustrial.com", "", "", ""),
    ("John Deere France", "john deere|deere", "deere.com", "jobs.deere.com", "", "", ""),
    ("Kubota France", "kubota", "kubota.fr", "kubota.fr", "", "", ""),
    ("Claas France", "claas", "claas.com", "jobs.claas.com", "", "", ""),
    ("Massey Ferguson France", "massey ferguson", "masseyferguson.com", "masseyferguson.com", "", "", ""),
    ("Yanmar France", "yanmar", "yanmar.com", "yanmar.com", "", "", ""),
    ("Bobcat France", "bobcat", "bobcat.com", "careers.bobcat.com", "", "", ""),
    ("JCB France", "jcb", "jcb.com", "jcb.com", "", "", ""),
    ("Hilti France", "hilti", "hilti.fr", "careers.hilti.com", "", "", ""),
    ("Stanley Black & Decker France", "stanley black and decker|stanley black & decker|black et decker", "stanleyblackanddecker.com", "careers.stanleyblackanddecker.com", "", "", ""),
    ("Facom", "", "facom.com", "facom.com", "", "", ""),
    ("Bosch Rexroth France", "bosch rexroth", "boschrexroth.com", "careers.boschrexroth.com", "", "", ""),
    ("Siemens Mobility France", "siemens mobility", "siemens.com", "jobs.siemens.com", "", "", ""),
    ("Siemens Healthineers France", "siemens healthineers", "siemens-healthineers.com", "jobs.siemens-healthineers.com", "", "", ""),
    ("Philips France", "philips", "philips.fr", "careers.philips.com", "", "", ""),
    ("GE Healthcare France", "ge healthcare|ge health care", "gehealthcare.com", "jobs.gehealthcare.com", "", "", ""),
    ("Medtronic France", "medtronic", "medtronic.com", "jobs.medtronic.com", "", "", ""),
    ("B. Braun France", "b braun|bbraun", "bbraun.fr", "careers.bbraun.com", "", "", ""),
    ("Fresenius Kabi France", "fresenius kabi", "fresenius-kabi.com", "careers.fresenius-kabi.com", "", "", ""),
    ("Fresenius Medical Care France", "fresenius medical care|fmc france", "freseniusmedicalcare.com", "jobs.freseniusmedicalcare.com", "", "", ""),
    ("Baxter France", "baxter", "baxter.fr", "jobs.baxter.com", "", "", ""),
    ("Abbott France", "abbott", "abbott.fr", "abbott.jobs", "", "", ""),
    ("Johnson & Johnson France", "johnson and johnson|jnj|j&j", "jnj.com", "jobs.jnj.com", "", "", ""),
    ("Janssen France", "janssen cilag|janssen", "janssen.com", "jobs.janssen.com", "", "", ""),
    ("Pfizer France", "pfizer", "pfizer.fr", "pfizer.com", "", "", ""),
    ("Moderna France", "moderna", "modernatx.com", "modernatx.com", "", "", ""),
    ("GSK France", "glaxosmithkline|gsk", "gsk.com", "jobs.gsk.com", "", "", ""),
    ("Merck France", "merck group|merck", "merckgroup.com", "jobs.merckgroup.com", "", "", ""),
    ("Roche France", "roche", "roche.fr", "careers.roche.com", "", "", ""),
    ("Novartis France", "novartis", "novartis.com", "novartis.com", "", "", ""),
    ("Bayer France", "bayer", "bayer.fr", "career.bayer.com", "", "", ""),
    ("Boiron", "", "boiron.fr", "boiron.fr", "", "", ""),
    ("Arkopharma", "", "arkopharma.com", "arkopharma.com", "", "", ""),
    ("Urgo", "urgo medical|laboratoires urgo", "urgo.com", "urgo.com", "", "", ""),
    ("Vetoquinol", "", "vetoquinol.com", "vetoquinol.com", "", "", ""),
    ("Ceva Santé Animale", "ceva sante animale|ceva", "ceva.com", "ceva.com", "", "", ""),
    ("Virbac", "", "virbac.com", "virbac.com", "", "", ""),
    ("Sanofi Genzyme", "genzyme", "sanofi.com", "careers.sanofi.com", "", "", ""),
    ("Sanofi Consumer Healthcare", "sanofi consumer|opella", "sanofi.com", "careers.sanofi.com", "", "", ""),
    ("Pierre Fabre Dermo-Cosmétique", "pierre fabre dermo cosmetique|dermo-cosmetique pierre fabre", "pierre-fabre.com", "careers.pierre-fabre.com", "", "", ""),
    ("Pierre Fabre Médicament", "pierre fabre medicament", "pierre-fabre.com", "careers.pierre-fabre.com", "", "", ""),
    ("Pierre Fabre Oncology", "pierre fabre oncologie", "pierre-fabre.com", "careers.pierre-fabre.com", "", "", ""),
    ("Guerbet Radiology", "guerbet", "guerbet.com", "guerbet.com", "", "", ""),
    ("Bio-Rad France", "bio-rad|biorad", "bio-rad.com", "careers.bio-rad.com", "", "", ""),
    ("Thermo Fisher France", "thermo fisher|thermofisher", "thermofisher.com", "jobs.thermofisher.com", "", "", ""),
    ("Eurofins France", "eurofins", "eurofins.com", "careers.eurofins.com", "", "", ""),
    ("Biomérieux Diagnostics", "biomerieux diagnostics", "biomerieux.com", "careers.biomerieux.com", "", "", ""),
    ("Cerba Healthcare", "cerba", "cerbahealthcare.com", "cerbahealthcare.com", "", "", ""),
    ("Unilabs France", "unilabs", "unilabs.com", "careers.unilabs.com", "", "", ""),
    ("Kapa Santé", "kapa sante|kapasante", "kapasante.fr", "kapasante.fr", "", "", ""),
    ("Ramsay Générale de Santé", "ramsay gds|ramsay sante|ramsay générale de sante", "ramsaygds.fr", "jobs.ramsaygds.fr", "", "", ""),
    ("Elsan Clinique", "elsan", "elsan.fr", "elsan.care|jobs.elsan.fr", "", "", ""),
    ("Clinique du Parc", "", "elsan.fr", "elsan.fr", "", "", ""),
    ("Clinique du Millénaire", "clinique du millenaire", "elsan.fr", "elsan.fr", "", "", ""),
    ("Clinique Pasteur", "clinique pasteur toulouse", "clinique-pasteur.com", "clinique-pasteur.com", "", "", ""),
    ("Clinique Saint-Jean", "clinique saint jean", "elsan.fr", "elsan.fr", "", "", ""),
    ("Clinique Saint-Augustin", "clinique saint augustin", "clinique-saint-augustin.fr", "clinique-saint-augustin.fr", "", "", ""),
    ("Clinique Belledonne", "", "clinique-belledonne.fr", "clinique-belledonne.fr", "", "", ""),
    ("Clinique du Pré", "clinique du pre", "elsan.fr", "elsan.fr", "", "", ""),
    ("Clinique du Val d’Ouest", "clinique du val d ouest|clinique val d'ouest", "val-ouest.com", "val-ouest.com", "", "", ""),
    ("Clinique de l’Union", "clinique de l union", "elsan.fr", "elsan.fr", "", "", ""),
    ("Clinique de la Sauvegarde", "clinique sauvegarde", "elsan.fr", "elsan.fr", "", "", ""),
    ("Clinique de la Plaine", "", "elsan.fr", "elsan.fr", "", "", ""),
    ("Clinique de la Côte d’Azur", "clinique de la cote d azur", "elsan.fr", "elsan.fr", "", "", ""),
    ("Clinique de l’Atlantique", "clinique de l atlantique", "elsan.fr", "elsan.fr", "", "", ""),
    ("Clinique de la Baie", "", "elsan.fr", "elsan.fr", "", "", ""),
    ("Clinique de la Montagne", "", "elsan.fr", "elsan.fr", "", "", ""),
    ("Clinique de la Providence", "", "elsan.fr", "elsan.fr", "", "", ""),
)

_PARC_CITIES: tuple[str, ...] = (
    "Lyon",
    "Toulouse",
    "Marseille",
    "Bordeaux",
    "Nantes",
    "Lille",
    "Strasbourg",
    "Nice",
    "Montpellier",
    "Rennes",
    "Tours",
    "Orléans",
    "Dijon",
    "Grenoble",
    "Clermont-Ferrand",
    "Limoges",
    "Poitiers",
    "Metz",
    "Nancy",
    "Reims",
    "Amiens",
    "Rouen",
    "Caen",
    "Brest",
    "Angers",
    "Le Mans",
    "Saint-Étienne",
    "Toulon",
    "Avignon",
    "Perpignan",
    "Pau",
    "Bayonne",
    "La Rochelle",
    "Annecy",
    "Chambéry",
    "Valence",
    "Béziers",
    "Albi",
    "Tarbes",
    "Agen",
    "Brive",
    "Chalon-sur-Saône",
    "Saint-Malo",
    "Saint-Brieuc",
)


def fold_employer_key(value: str) -> str:
    text = unicodedata.normalize("NFD", str(value or "").lower())
    text = "".join(char for char in text if unicodedata.category(char) != "Mn")
    text = text.replace("’", "'").replace("`", "'")
    text = re.sub(r"[^a-z0-9+]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _split_pipe(raw: object) -> tuple[str, ...]:
    text = str(raw or "").strip()
    if not text:
        return ()
    return tuple(part.strip() for part in text.split("|") if part.strip())


def _clean_career_host(host: str) -> str:
    name = str(host or "").strip().lower()
    if name.startswith("www."):
        name = name[4:]
    return name.split("/", 1)[0]


def _parc_clinic_rows() -> tuple[tuple[object, ...], ...]:
    rows: list[tuple[object, ...]] = []
    for city in _PARC_CITIES:
        name = f"Clinique du Parc {city}"
        rows.append((name, "", "elsan.fr", "elsan.fr", "", "", ""))
    return tuple(rows)


def _build_employers() -> tuple[PriorityEmployer, ...]:
    built: list[PriorityEmployer] = []
    for row in (*_ROWS, *_parc_clinic_rows()):
        name = str(row[0]).strip()
        aliases = tuple(
            dict.fromkeys(
                [name, *(_split_pipe(row[1]))],
            )
        )
        hosts = tuple(
            cleaned
            for host in _split_pipe(row[3])
            for cleaned in [_clean_career_host(host)]
            if cleaned and "." in cleaned
        )
        built.append(
            PriorityEmployer(
                name=name,
                aliases=aliases,
                domain=str(row[2]).strip(),
                career_hosts=hosts,
                greenhouse=str(row[4] or "").strip(),
                lever=str(row[5] or "").strip(),
                smartrecruiters=str(row[6] or "").strip(),
            )
        )
    return tuple(built)


PRIORITY_EMPLOYERS: tuple[PriorityEmployer, ...] = _build_employers()


def _alias_index() -> list[tuple[str, int, PriorityEmployer]]:
    rows: list[tuple[str, int, PriorityEmployer]] = []
    for employer in PRIORITY_EMPLOYERS:
        for alias in employer.aliases:
            key = fold_employer_key(alias)
            if len(key) < 2:
                continue
            rows.append((key, len(key), employer))
    rows.sort(key=lambda item: item[1], reverse=True)
    return rows


_ALIAS_INDEX = _alias_index()
_ALIAS_EXACT = {key: emp for key, _length, emp in reversed(_ALIAS_INDEX)}


def generic_hr_local_parts() -> tuple[str, ...]:
    return _GENERIC_HR_LOCAL_PARTS


def employer_mail_domains() -> dict[str, str]:
    mapping: dict[str, str] = {}
    for employer in PRIORITY_EMPLOYERS:
        for alias in employer.aliases:
            key = fold_employer_key(alias)
            if key:
                mapping[key] = employer.domain
    return mapping


def career_host_mail_domains() -> dict[str, str]:
    mapping: dict[str, str] = {}
    for employer in PRIORITY_EMPLOYERS:
        for host in employer.career_hosts:
            name = host.lower().split("/", 1)[0]
            if name and "." in name and name not in mapping:
                mapping[name] = employer.domain
    return mapping


def career_hosts() -> tuple[str, ...]:
    """Career/jobs hosts worth targeting with Google site: queries."""
    hosts: list[str] = []
    for employer in PRIORITY_EMPLOYERS:
        for host in employer.career_hosts:
            name = _clean_career_host(host)
            if not name or "." not in name:
                continue
            lowered = name.lower()
            careerish = any(
                token in lowered
                for token in ("career", "job", "emploi", "recrut", "talent")
            )
            if careerish or lowered.count(".") >= 2:
                hosts.append(name)
    return tuple(dict.fromkeys(hosts))


def career_company_names() -> dict[str, str]:
    mapping: dict[str, str] = {}
    for employer in PRIORITY_EMPLOYERS:
        for host in employer.career_hosts:
            name = _clean_career_host(host)
            if name and "." in name and name not in mapping:
                mapping[name] = employer.name
    return mapping


def employer_google_terms() -> tuple[str, ...]:
    terms: list[str] = []
    seen: set[str] = set()
    for employer in PRIORITY_EMPLOYERS:
        label = employer.name.strip()
        folded = fold_employer_key(label)
        if not folded or folded in seen:
            continue
        if folded.startswith("clinique du parc "):
            continue
        seen.add(folded)
        if " " in label or "'" in label or "’" in label or "+" in label:
            terms.append(f'"{label}"')
        else:
            terms.append(label)
    return tuple(terms)


def greenhouse_tokens() -> tuple[tuple[str, str], ...]:
    return tuple(
        (item.greenhouse, item.name)
        for item in PRIORITY_EMPLOYERS
        if item.greenhouse
    )


def lever_slugs() -> tuple[tuple[str, str], ...]:
    return tuple((item.lever, item.name) for item in PRIORITY_EMPLOYERS if item.lever)


def smartrecruiters_companies() -> tuple[tuple[str, str], ...]:
    return tuple(
        (item.smartrecruiters, item.name)
        for item in PRIORITY_EMPLOYERS
        if item.smartrecruiters
    )


def _alias_in_text(folded_text: str, alias: str) -> bool:
    if not alias:
        return False
    if alias == folded_text:
        return True
    pattern = r"(^|[^a-z0-9])" + re.escape(alias) + r"([^a-z0-9]|$)"
    return re.search(pattern, folded_text) is not None


def match_priority_employer(
    job: dict[str, Any] | None = None,
    *,
    company: str = "",
    url: str = "",
) -> PriorityEmployer | None:
    """Return the priority employer for a job / company name / URL, if any."""
    payload = job or {}
    company_text = " ".join(
        str(part or "")
        for part in (
            company,
            payload.get("company"),
            payload.get("company_name"),
        )
    )
    url_text = " ".join(
        str(part or "")
        for part in (
            url,
            payload.get("url"),
            payload.get("apply_url"),
            payload.get("company_url"),
        )
    )
    folded_company = fold_employer_key(company_text)
    folded_url = fold_employer_key(url_text)

    if folded_company:
        exact = _ALIAS_EXACT.get(folded_company)
        if exact:
            return exact
        for alias, _length, employer in _ALIAS_INDEX:
            if _alias_in_text(folded_company, alias):
                return employer

    lowered_url = url_text.lower()
    for employer in PRIORITY_EMPLOYERS:
        for host in employer.career_hosts:
            needle = host.lower().split("/", 1)[0]
            if needle and needle in lowered_url:
                return employer
        if employer.domain and employer.domain in lowered_url:
            return employer

    if folded_url:
        for alias, _length, employer in _ALIAS_INDEX:
            if len(alias) >= 5 and _alias_in_text(folded_url, alias):
                return employer
    return None


def is_priority_employer(job: dict[str, Any] | None = None, *, company: str = "") -> bool:
    return match_priority_employer(job, company=company) is not None


def mailbox_domain_for_company(company: str, job: dict[str, Any] | None = None) -> str:
    matched = match_priority_employer(job, company=company)
    return matched.domain if matched else ""


def extra_career_page_urls(job: dict[str, Any]) -> list[str]:
    """Public career URLs to scrape when the listing itself has no mailto."""
    matched = match_priority_employer(job)
    if not matched:
        return []
    urls: list[str] = []
    for host in matched.career_hosts[:3]:
        name = host.lower().split("/", 1)[0]
        if not name or "." not in name:
            continue
        urls.append(f"https://{name}")
    return urls


def matching_priority_key(job: dict[str, Any]) -> int:
    """Tie-break so equal ATS scores keep priority employers first."""
    return 1 if is_priority_employer(job) else 0
