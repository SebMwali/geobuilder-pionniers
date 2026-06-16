"""Exécution Phase 5 — Correctifs suite réponses Sandrine (16/06/2026).

1. RAFFARD PIO-1152 : archivage + libération NS HR88C23LFR1131
2. LE DU Sylvain PIO-1130 : récupère le NS HR88C23LFR1131 sur INST-2129
3. MALTRET PIO-1059 : libération NS HR88C23GFR0299 + tag "À vérifier"
4. Création FRENEHART Lucas (récupère HR88C23GFR0299)
5. Création IBRAHIM Moussy (prenom=Moussy, NS HR88C23JFR0818) + archivage (quitté Mayotte)
6. Compléter prénoms batch précédent :
   - PIO-1205 LAUGERE → Ludovic
   - PIO-1206 LEPOURRIEL → renommer LEPOURIEL Nolwenn + nom_client install "LEPOURIEL Nolwenn / FRANCOIS Nicolas"
   - PIO-1207 LERICHE → Stéphane
"""
from __future__ import annotations
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
TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")
SOURCE_TAG = "import_sandrine_2026-06-16_phase5"

_pio_cache: list = []
_inst_cache: list = []

def refresh_cache():
    global _pio_cache, _inst_cache
    _pio_cache = svc.read_all("pionniers")
    _inst_cache = svc.read_all("installations")
    print(f"   cache: {len(_pio_cache)} pio / {len(_inst_cache)} inst")
    time.sleep(2)

def pause():
    time.sleep(1.5)

def find_pio(pio_id: str):
    for r in _pio_cache:
        if str(r.get("pio_id", "")).strip() == pio_id:
            return r
    return None

def find_install(install_id: str):
    for r in _inst_cache:
        if str(r.get("install_id", "")).strip() == install_id:
            return r
    return None

def find_install_by_ns(ns: str):
    ns_up = ns.strip().upper()
    for r in _inst_cache:
        if str(r.get("numero_serie", "")).strip().upper() == ns_up:
            return r
    return None

report = []

def log(action, detail="", pio_id="", install_id="", result="OK"):
    line = f"[{result}] {action} | pio={pio_id} inst={install_id} | {detail}"
    print(line)
    report.append(line)

def set_pio_field(pio_id: str, field: str, value: str):
    pio = find_pio(pio_id)
    if not pio:
        log(f"set_{field}", f"pio {pio_id} introuvable", pio_id, "", "SKIP")
        return
    cur = str(pio.get(field, "")).strip()
    if cur == value:
        log(f"set_{field}", f"déjà '{value}'", pio_id, "", "SKIP")
        return
    row_idx = svc.find_row_index_by("pionniers", "pio_id", pio_id)
    pause()
    svc.update_cell("pionniers", row_idx, field, value)
    pause()
    pio[field] = value
    log(f"set_{field}", f"'{cur}' → '{value}'", pio_id, "", "OK")

def set_install_field(install_id: str, field: str, value: str):
    inst = find_install(install_id)
    if not inst:
        log(f"set_inst_{field}", f"install {install_id} introuvable", "", install_id, "SKIP")
        return
    cur = str(inst.get(field, "")).strip()
    if cur == value:
        log(f"set_inst_{field}", f"déjà '{value}'", "", install_id, "SKIP")
        return
    row_idx = svc.find_row_index_by("installations", "install_id", install_id)
    pause()
    svc.update_cell("installations", row_idx, field, value)
    pause()
    inst[field] = value
    log(f"set_inst_{field}", f"'{cur}' → '{value}'", "", install_id, "OK")

def create_new_pionnier(nom: str, prenom: str, produit: str, numero_serie: str,
                         statut: str = "Pionnier",
                         territoire: str = "MAYOTTE", pays: str = "FRANCE",
                         client_type: str = "Particulier"):
    existing = find_install_by_ns(numero_serie)
    if existing:
        log("create_pionnier", f"NS '{numero_serie}' déjà rattaché à {existing.get('install_id')}",
            existing.get("pio_id",""), existing.get("install_id",""), "SKIP")
        return
    _, pio_id = increment_counter("pionnier")
    pause()
    nom_complet = (f"{prenom} {nom}").strip()
    svc.append_row("pionniers", [
        pio_id, numero_serie, nom.upper(), prenom, "", "",
        pays, territoire, client_type, TODAY, statut,
        "FALSE", "FALSE", "", "FALSE", "FALSE", "FALSE",
        SOURCE_TAG, "", "FALSE", "", "", "",
    ])
    pause()
    _pio_cache.append({"pio_id": pio_id, "NS": numero_serie, "nom": nom.upper(), "prenom": prenom, "statut": statut})
    _, install_id = increment_counter("installation")
    pause()
    inst_status = "archivée" if "Inactif" in statut else "active"
    svc.append_row("installations", [
        install_id, pio_id, produit, numero_serie, "", "",
        territoire, "", inst_status, "true", nom_complet,
        "", "", "", territoire, "", "", "", "", "true", "", "", SOURCE_TAG,
    ])
    pause()
    _inst_cache.append({"install_id": install_id, "pio_id": pio_id, "produit": produit,
                        "numero_serie": numero_serie, "nom_client": nom_complet})
    log("create_pionnier", f"{nom_complet} | NS={numero_serie} | statut={statut}", pio_id, install_id, "OK")

# ============================================================================
print(f"=== START Phase 5 — {datetime.now(timezone.utc).isoformat()} ===\n")
print("Loading cache...")
refresh_cache()

# --- Action 1 : Transfert NS HR88C23LFR1131 RAFFARD → LE DU Sylvain ---
print("\n--- Action 1 : Transfert NS HR88C23LFR1131 RAFFARD → LE DU Sylvain ---")
set_pio_field("PIO-1152", "NS", "")
set_install_field("INST-2151", "numero_serie", "")
set_install_field("INST-2151", "installation_status", "archivée")
set_pio_field("PIO-1152", "statut", "Inactif - quitté Mayotte")
# Maintenant attribuer à LE DU
set_pio_field("PIO-1130", "NS", "HR88C23LFR1131")
set_install_field("INST-2129", "numero_serie", "HR88C23LFR1131")

# --- Action 2 : MALTRET — libération NS + tag à vérifier ---
print("\n--- Action 2 : MALTRET PIO-1059 — libération NS HR88C23GFR0299 ---")
set_pio_field("PIO-1059", "NS", "")
set_install_field("INST-2058", "numero_serie", "")
set_pio_field("PIO-1059", "statut", "À vérifier - identité incertaine")

# --- Action 3 : Création FRENEHART Lucas avec NS HR88C23GFR0299 ---
print("\n--- Action 3 : Création FRENEHART Lucas (NS HR88C23GFR0299) ---")
create_new_pionnier("FRENEHART", "Lucas", "G30", "HR88C23GFR0299")

# --- Action 4 : Création IBRAHIM Moussy (Moussy = prénom) + archivage immédiat ---
print("\n--- Action 4 : Création IBRAHIM Moussy (quitté Mayotte) ---")
create_new_pionnier("IBRAHIM", "Moussy", "G30", "HR88C23JFR0818",
                    statut="Inactif - quitté Mayotte")

# --- Action 5 : Compléter prénoms batch précédent ---
print("\n--- Action 5 : Compléter prénoms ---")
set_pio_field("PIO-1205", "prenom", "Ludovic")  # LAUGERE
set_pio_field("PIO-1207", "prenom", "Stéphane")  # LERICHE

# LEPOURRIEL → corriger orthographe + ajouter prénom + couple
set_pio_field("PIO-1206", "nom", "LEPOURIEL")  # un seul R
set_pio_field("PIO-1206", "prenom", "Nolwenn")
# Pour l'install : nom_client refléter le couple
# Trouver l'install
inst_pio_1206 = [r for r in _inst_cache if str(r.get("pio_id","")).strip() == "PIO-1206"]
if inst_pio_1206:
    iid = inst_pio_1206[0].get("install_id","")
    set_install_field(iid, "nom_client", "LEPOURIEL Nolwenn / FRANCOIS Nicolas")

# Rapport final
print("\n=== FIN Phase 5 ===")
print(f"Total : {len(report)} | OK={sum(1 for x in report if '[OK]' in x)} | SKIP={sum(1 for x in report if '[SKIP]' in x)}")

try:
    svc.log_event("batch_sandrine_phase5", result="OK",
                  message=f"OK={sum(1 for x in report if '[OK]' in x)} SKIP={sum(1 for x in report if '[SKIP]' in x)}")
except Exception:
    pass
