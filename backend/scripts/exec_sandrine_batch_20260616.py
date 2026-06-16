"""Exécution batch des correctifs validés par Sandrine (16/06/2026).

20 opérations Sheet :
- 6 ajouts NS sur installations existantes (Catégorie A)
- 1 nouvelle installation pour pionnier existant (Catégorie B — CLEMENT 2e G30)
- 12 créations de pionniers + installations (Catégorie C)
- 1 archivage de pionnier (Catégorie D — LACOMBE)

Suspendus pour clarification Sandrine ultérieure :
- FRENEHART (conflit NS HR88C23GFR0299 avec PIO-1059 MALTRET)
- RAFFARD Maxime PIO-1152 (conflit NS HR88C23LFR1131 vs HR88C23JFR0705)

Idempotence : chaque opération vérifie l'état actuel avant d'écrire.
"""
from __future__ import annotations
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / '.env')

from services.sheets_service import get_sheets_service
from services.counter_service import increment_counter

svc = get_sheets_service()

NOW_ISO = datetime.now(timezone.utc).isoformat()
TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")
SOURCE_TAG = "import_sandrine_2026-06-16"

# Cache en mémoire pour réduire les appels API
_pio_cache: list = []
_inst_cache: list = []

def refresh_cache():
    global _pio_cache, _inst_cache
    _pio_cache = svc.read_all("pionniers")
    _inst_cache = svc.read_all("installations")
    print(f"   cache refreshed: {len(_pio_cache)} pio / {len(_inst_cache)} inst")
    time.sleep(2)

def find_pio_cached(pio_id: str):
    for r in _pio_cache:
        if str(r.get("pio_id", "")).strip() == pio_id:
            return r
    return None

def find_install_cached(install_id: str):
    for r in _inst_cache:
        if str(r.get("install_id", "")).strip() == install_id:
            return r
    return None

def find_install_by_ns_cached(ns: str):
    ns_up = ns.strip().upper()
    for r in _inst_cache:
        if str(r.get("numero_serie", "")).strip().upper() == ns_up:
            return r
    return None

# Pause entre writes pour éviter quota 429
def pause():
    time.sleep(1.5)

report = []


def log(action: str, detail: str = "", install_id: str = "", pio_id: str = "", result: str = "OK"):
    line = f"[{result}] {action} | pio={pio_id} inst={install_id} | {detail}"
    print(line)
    report.append(line)


def update_install_ns(install_id: str, new_ns: str, expected_pio_id: str | None = None):
    """Met à jour numero_serie de 02_Installations + miroir dans 01_Pionniers.NS si vide."""
    install = find_install_cached(install_id)
    if not install:
        log("update_install_ns", f"install {install_id} introuvable", install_id, "", "SKIP")
        return None
    pio_id = expected_pio_id or install.get("pio_id", "")
    current_ns = str(install.get("numero_serie", "")).strip()
    if current_ns == new_ns:
        log("update_install_ns", f"NS déjà à '{new_ns}' (idempotent)", install_id, pio_id, "SKIP")
        return install
    if current_ns:
        log("update_install_ns", f"⚠️ NS existant '{current_ns}' (sera écrasé par '{new_ns}')", install_id, pio_id, "WARN")
    row_idx = svc.find_row_index_by("installations", "install_id", install_id)
    pause()
    svc.update_cell("installations", row_idx, "numero_serie", new_ns)
    pause()
    install["numero_serie"] = new_ns  # update cache
    log("update_install_ns", f"NS écrit '{new_ns}'", install_id, pio_id, "OK")

    # Miroir 01_Pionniers.NS si vide
    if pio_id:
        pio = find_pio_cached(pio_id)
        if pio and not str(pio.get("NS", "")).strip():
            pio_row_idx = svc.find_row_index_by("pionniers", "pio_id", pio_id)
            pause()
            svc.update_cell("pionniers", pio_row_idx, "NS", new_ns)
            pause()
            pio["NS"] = new_ns
            log("update_pionnier_ns_mirror", "miroir NS écrit", install_id, pio_id, "OK")
    return install


def set_pio_field(pio_id: str, field: str, value: str):
    pio = find_pio_cached(pio_id)
    if not pio:
        log(f"set_{field}", f"pionnier {pio_id} introuvable", "", pio_id, "SKIP")
        return
    cur = str(pio.get(field, "")).strip()
    if cur == value:
        log(f"set_{field}", f"déjà '{value}'", "", pio_id, "SKIP")
        return
    row_idx = svc.find_row_index_by("pionniers", "pio_id", pio_id)
    pause()
    svc.update_cell("pionniers", row_idx, field, value)
    pause()
    pio[field] = value
    log(f"set_{field}", f"'{cur}' → '{value}'", "", pio_id, "OK")


def set_client_type(pio_id: str, value: str):
    set_pio_field(pio_id, "client_type", value)


def set_statut(pio_id: str, value: str):
    set_pio_field(pio_id, "statut", value)


def create_install_for_existing_pio(pio_id: str, produit: str, numero_serie: str,
                                     nom_client: str = "", territoire: str = "MAYOTTE") -> str:
    existing = find_install_by_ns_cached(numero_serie)
    if existing:
        log("create_install", f"NS '{numero_serie}' déjà présent dans {existing.get('install_id')}",
            existing.get("install_id", ""), pio_id, "SKIP")
        return existing.get("install_id", "")

    _, install_id = increment_counter("installation")
    pause()
    svc.append_row("installations", [
        install_id, pio_id, produit, numero_serie, "", "",
        territoire, "", "active", "true", nom_client,
        "", "", "", territoire, "", "", "", "", "true", "", "", SOURCE_TAG,
    ])
    pause()
    # update cache
    _inst_cache.append({
        "install_id": install_id, "pio_id": pio_id, "produit": produit,
        "numero_serie": numero_serie, "nom_client": nom_client,
        "territoire_installation": territoire,
    })
    log("create_install", f"créée pour {pio_id}, NS={numero_serie}, produit={produit}",
        install_id, pio_id, "OK")
    return install_id


def create_new_pionnier(nom: str, prenom: str, produit: str, numero_serie: str,
                         territoire: str = "MAYOTTE", pays: str = "FRANCE",
                         client_type: str = "Particulier") -> tuple[str, str]:
    existing = find_install_by_ns_cached(numero_serie)
    if existing:
        log("create_pionnier", f"NS '{numero_serie}' déjà rattaché à {existing.get('install_id')} (pio={existing.get('pio_id')})",
            existing.get("install_id", ""), existing.get("pio_id", ""), "SKIP")
        return existing.get("pio_id", ""), existing.get("install_id", "")

    _, pio_id = increment_counter("pionnier")
    pause()
    nom_complet = (f"{prenom} {nom}").strip()

    svc.append_row("pionniers", [
        pio_id, numero_serie, nom.upper(), prenom, "", "",
        pays, territoire, client_type, TODAY, "Pionnier",
        "FALSE", "FALSE", "", "FALSE", "FALSE", "FALSE",
        SOURCE_TAG, "", "FALSE", "", "", "",
    ])
    pause()
    _pio_cache.append({"pio_id": pio_id, "NS": numero_serie, "nom": nom.upper(), "prenom": prenom, "client_type": client_type, "statut": "Pionnier"})

    _, install_id = increment_counter("installation")
    pause()
    svc.append_row("installations", [
        install_id, pio_id, produit, numero_serie, "", "",
        territoire, "", "active", "true", nom_complet,
        "", "", "", territoire, "", "", "", "", "true", "", "", SOURCE_TAG,
    ])
    pause()
    _inst_cache.append({"install_id": install_id, "pio_id": pio_id, "produit": produit,
                        "numero_serie": numero_serie, "nom_client": nom_complet})
    log("create_pionnier", f"{nom_complet} | produit={produit} | NS={numero_serie}",
        install_id, pio_id, "OK")
    return pio_id, install_id


# ============================================================================
# EXÉCUTION
# ============================================================================
print(f"=== START EXEC {NOW_ISO} ===\n")
print("Loading cache...")
refresh_cache()

# --- Catégorie A — Ajout NS sur installation existante ---
print("\n--- Catégorie A — Ajouts NS ---")
update_install_ns("INST-2121", "HR88C24AFR0078", "PIO-1122")  # BERTHET
update_install_ns("INST-2123", "HR88C23JFR0705", "PIO-1124")  # CORRADO BERJOTIN
update_install_ns("INST-2124", "HR88C22KFR0388", "PIO-1125")  # DE BOLLIVIER
update_install_ns("INST-2126", "HR88C25DAZ0057", "PIO-1127")  # GARCIA
update_install_ns("INST-2140", "HR88C25DAZ0067", "PIO-1141")  # ROBERT
update_install_ns("INST-2143", "HR88C24AFR0003", "PIO-1144")  # SOS OXYGENE
set_client_type("PIO-1144", "Structure")                       # SOS OXYGENE = entreprise

# --- Catégorie B — Nouvelle installation pour pionnier existant ---
print("\n--- Catégorie B — Nouvelle install CLEMENT (2e G30) ---")
create_install_for_existing_pio(
    pio_id="PIO-1077",
    produit="G30",
    numero_serie="HR88C23LFR1043",
    nom_client="CLEMENT Olivier",
    territoire="MAYOTTE",
)

# --- Catégorie C — Création de 12 nouveaux pionniers ---
print("\n--- Catégorie C — Création de 12 nouveaux pionniers ---")
new_pioneers = [
    ("DUHEM",      "Robin",     "G30",       "HR88C24AFR0042"),
    ("FERREUX",    "Medhi",     "G30",       "HR88C25DAZ0085"),
    ("GEISSEL",    "Romain",    "Ocean 500", "ZL9510W23JFR0087S"),
    ("JUDIC",      "Alice",     "Ocean 500", "ZL9510W23IFR0083S"),
    ("KEISLER",    "Fernand",   "G30",       "HR88C23LFR1162"),
    ("KEISLER",    "Murielle",  "G30",       "HR88C24AFR0007"),
    ("MADI",       "Idriss",    "Ocean 500", "ZL9510W25DAZ0080S"),
    ("LAUGERE",    "",          "Ocean 500", "ZL9510W23JFR0085S"),
    ("LEPOURRIEL", "",          "G30",       "HR88C24AFR0075"),
    ("LERICHE",    "",          "Ocean 500", "ZL9510W23JFR0127S"),
    ("RASTAMI",    "Cedryann",  "G30",       "HR88C24AFR0069"),
    ("PESQUEIRA",  "Clement",   "G30",       "HR88C23JFR0766"),
]
for nom, prenom, produit, ns in new_pioneers:
    create_new_pionnier(nom=nom, prenom=prenom, produit=produit, numero_serie=ns)

# --- Catégorie D — Archivage LACOMBE ---
print("\n--- Catégorie D — Archivage ---")
set_statut("PIO-1029", "Inactif - revendu")

# Rapport final
print("\n=== FIN EXEC ===")
print(f"Total opérations loggées : {len(report)}")
print(f"OK   : {sum(1 for x in report if '[OK]' in x)}")
print(f"SKIP : {sum(1 for x in report if '[SKIP]' in x)}")
print(f"WARN : {sum(1 for x in report if '[WARN]' in x)}")

# Log final unique dans le sheet (1 seul log_event pour économiser quota)
try:
    svc.log_event(
        "batch_sandrine_2026-06-16",
        result="OK",
        message=f"{sum(1 for x in report if '[OK]' in x)} OK / {sum(1 for x in report if '[SKIP]' in x)} SKIP / {sum(1 for x in report if '[WARN]' in x)} WARN",
    )
except Exception:
    pass

