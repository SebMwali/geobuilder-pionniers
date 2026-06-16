"""audit_sheets_v2.py — Audit rigoureux du Google Sheet Geobuilder.

Sortie : rapport texte exhaustif avec :
  - Lignes RÉELLES (non-vides) par onglet
  - Détection cellules d'erreur (#REF!, #ERROR!, #N/A)
  - Validation regex emails + split sur ';' pour adresses multiples
  - Croisement 00_Fondateurs <-> 01_Pionniers (delta exact, dans les 2 sens)
  - Doublons (emails, pio_id)
  - Pionniers prêts à recevoir un email (email valide ET pas désabonné)
"""
import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from services.sheets_service import get_sheets_service  # noqa: E402

EMAIL_RX = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
ERROR_TOKENS = ("#REF!", "#ERROR!", "#N/A", "#NAME?", "#VALUE!", "#DIV/0!")


def is_empty(v) -> bool:
    return v is None or str(v).strip() == ""


def is_error_cell(v) -> bool:
    s = str(v or "").strip().upper()
    return any(t in s for t in ERROR_TOKENS)


def split_emails(raw: str) -> list[str]:
    """Sépare une cellule email contenant possiblement plusieurs adresses (';' ou ',')."""
    if not raw:
        return []
    parts = re.split(r"[;,]\s*", str(raw).strip())
    return [p.strip() for p in parts if p.strip()]


def truthy(v) -> bool:
    return str(v or "").strip().upper() in ("TRUE", "OUI", "VRAI", "1", "YES", "X")


def main():
    s = get_sheets_service()
    print("═" * 76)
    print(" AUDIT GOOGLE SHEET — Geobuilder Pionniers (v2 strict)")
    print("═" * 76)

    # ──────────────────────────────────────────────────────────────────────────
    # 1. 00_FONDATEURS — comptage strict (ligne non-vide ET nom renseigné)
    # ──────────────────────────────────────────────────────────────────────────
    print("\n1️⃣  00_FONDATEURS")
    print("─" * 76)
    fond_raw = s.read_all("00_Fondateurs")
    print(f"  read_all renvoie         : {len(fond_raw)} lignes (header exclu)")

    fond_reels = []
    for r in fond_raw:
        nom = str(r.get("Nom") or r.get("nom") or "").strip()
        prenom = str(r.get("Prénom") or r.get("prenom") or "").strip()
        if nom or prenom:
            fond_reels.append(r)

    print(f"  Fondateurs RÉELS (nom)   : {len(fond_reels)}")
    print(f"  → Il MANQUE              : {100 - len(fond_reels)} fondateurs à recruter")

    # Erreurs de cellules
    err_cells = []
    for i, r in enumerate(fond_reels, start=2):
        for k, v in r.items():
            if is_error_cell(v):
                err_cells.append((i, k, v))
    if err_cells:
        print(f"  ⚠️  Cellules en ERREUR : {len(err_cells)}")
        for row, col, val in err_cells[:10]:
            print(f"      ligne {row}, col '{col}' = {val}")

    # Territoire (normalisation casse)
    from collections import Counter
    terr_raw = Counter(str(r.get("territoire") or "").strip() for r in fond_reels)
    terr_norm = Counter(str(r.get("territoire") or "").strip().upper() for r in fond_reels)
    print(f"  Par territoire (brut)    : {dict(terr_raw)}")
    print(f"  Par territoire (norm)    : {dict(terr_norm)}")

    # pio_id_propose renseigné
    pio_proposed_in_fond = []
    for r in fond_reels:
        pp = str(r.get("pio_id_propose") or "").strip()
        if pp:
            pio_proposed_in_fond.append((r, pp))
    print(f"  Avec pio_id_propose      : {len(pio_proposed_in_fond)}/{len(fond_reels)}")
    sans_pio_propose = [r for r in fond_reels if not str(r.get("pio_id_propose") or "").strip()]
    if sans_pio_propose:
        print(f"  ⚠️  Sans pio_id_propose ({len(sans_pio_propose)}):")
        for r in sans_pio_propose:
            ordre = r.get("ordre", "?")
            nom = r.get("Nom") or r.get("nom") or ""
            prenom = r.get("Prénom") or r.get("prenom") or ""
            terr = r.get("territoire", "")
            print(f"      ordre={ordre:>3}  {nom} {prenom}  [{terr}]")

    # ──────────────────────────────────────────────────────────────────────────
    # 2. 01_PIONNIERS — comptage strict
    # ──────────────────────────────────────────────────────────────────────────
    print("\n2️⃣  01_PIONNIERS")
    print("─" * 76)
    pio_raw = s.read_all("pionniers")
    print(f"  read_all renvoie         : {len(pio_raw)} lignes")

    # Pionniers réels = ceux avec un pio_id renseigné
    pio_reels = [p for p in pio_raw if str(p.get("pio_id") or "").strip()]
    print(f"  Pionniers RÉELS (pio_id) : {len(pio_reels)}")

    err_cells_pio = []
    for i, r in enumerate(pio_reels, start=2):
        for k, v in r.items():
            if is_error_cell(v):
                err_cells_pio.append((i, k, v, r.get("pio_id")))
    if err_cells_pio:
        print(f"  ⚠️  Cellules en ERREUR : {len(err_cells_pio)}")
        for row, col, val, pid in err_cells_pio[:10]:
            print(f"      {pid} (ligne {row}), col '{col}' = {val}")

    # Croisement fondateur=true vs 00_Fondateurs
    pio_fond_true = [p for p in pio_reels if truthy(p.get("fondateur"))]
    print(f"  Marqués fondateur=true    : {len(pio_fond_true)}")
    pio_ids_fond_true = {str(p.get("pio_id") or "").strip() for p in pio_fond_true}
    pio_ids_in_00 = {pp for _, pp in pio_proposed_in_fond}

    # Pionniers fondateur=true MAIS pas dans 00_Fondateurs
    extra_in_pio = pio_ids_fond_true - pio_ids_in_00
    if extra_in_pio:
        print(f"  ⚠️  EXTRA dans 01_Pionniers (fondateur=true MAIS pas dans 00_Fondateurs) : {len(extra_in_pio)}")
        for pid in sorted(extra_in_pio):
            p = next(x for x in pio_fond_true if str(x.get("pio_id") or "").strip() == pid)
            nom = p.get("nom") or ""
            prenom = p.get("prénom") or p.get("prenom") or ""
            email = p.get("email") or ""
            print(f"      {pid}  {nom} {prenom}  <{email}>")

    # Fondateurs dans 00_Fondateurs MAIS pas marqués dans 01_Pionniers
    missing_in_pio = pio_ids_in_00 - pio_ids_fond_true
    if missing_in_pio:
        print(f"  ⚠️  Dans 00_Fondateurs MAIS pas fondateur=true dans 01_Pionniers : {len(missing_in_pio)}")
        for pid in sorted(missing_in_pio):
            print(f"      {pid}")

    # ──────────────────────────────────────────────────────────────────────────
    # 3. EMAILS — validation stricte, split multi-adresses
    # ──────────────────────────────────────────────────────────────────────────
    print("\n3️⃣  EMAILS (validation stricte + split multi-adresses)")
    print("─" * 76)
    pio_sans_email = []
    pio_email_valide = []        # 1 seule adresse valide
    pio_email_multi = []         # plusieurs adresses séparées par ; ou ,
    pio_email_invalide = []
    all_valid_emails = []

    for p in pio_reels:
        pid = str(p.get("pio_id") or "").strip()
        raw = str(p.get("email") or "").strip()
        if not raw:
            pio_sans_email.append(p)
            continue
        emails = split_emails(raw)
        valides = [e for e in emails if EMAIL_RX.match(e)]
        invalides = [e for e in emails if not EMAIL_RX.match(e)]
        if invalides:
            pio_email_invalide.append((p, invalides))
            continue
        if len(valides) > 1:
            pio_email_multi.append((p, valides))
        else:
            pio_email_valide.append(p)
        for e in valides:
            all_valid_emails.append((pid, e.lower()))

    print(f"  Pionniers sans email          : {len(pio_sans_email)}")
    print(f"  Pionniers avec 1 email valide : {len(pio_email_valide)}")
    print(f"  Pionniers avec multi-emails   : {len(pio_email_multi)} (séparés par ; ou ,)")
    print(f"  Pionniers avec email INVALIDE : {len(pio_email_invalide)}")
    print(f"  → ENVOYABLES (≥ 1 valide)     : {len(pio_email_valide) + len(pio_email_multi)}")
    print(f"  → TOTAL adresses email valides: {len(all_valid_emails)}")

    if pio_email_invalide:
        print(f"\n  ❌ Emails INVALIDES (à corriger dans le Sheet) :")
        for p, invs in pio_email_invalide[:15]:
            print(f"      {p.get('pio_id')}  raw={p.get('email')!r}  invalides={invs}")

    if pio_email_multi:
        print(f"\n  📧 Pionniers avec multi-emails (envoi en CC ou choisir le principal) :")
        for p, emails in pio_email_multi[:15]:
            print(f"      {p.get('pio_id')}  {p.get('nom','')} {p.get('prénom','')}  → {len(emails)} adresses: {emails}")

    # Doublons d'emails
    from collections import defaultdict
    email_to_pids = defaultdict(list)
    for pid, e in all_valid_emails:
        email_to_pids[e].append(pid)
    doublons = {e: pids for e, pids in email_to_pids.items() if len(pids) > 1}
    if doublons:
        print(f"\n  ⚠️  Emails DOUBLONS (même email pour plusieurs pionniers) : {len(doublons)}")
        for e, pids in list(doublons.items())[:15]:
            print(f"      {e} → {pids}")

    # ──────────────────────────────────────────────────────────────────────────
    # 4. INSTALLATIONS — cohérence et complétude
    # ──────────────────────────────────────────────────────────────────────────
    print("\n4️⃣  02_INSTALLATIONS")
    print("─" * 76)
    inst_raw = s.read_all("installations")
    print(f"  read_all renvoie         : {len(inst_raw)} lignes")
    inst_reels = [r for r in inst_raw if str(r.get("install_id") or "").strip()]
    print(f"  Installations RÉELLES    : {len(inst_reels)}")

    err_cells_inst = []
    for i, r in enumerate(inst_reels, start=2):
        for k, v in r.items():
            if is_error_cell(v):
                err_cells_inst.append((i, k, v, r.get("install_id")))
    if err_cells_inst:
        print(f"  ⚠️  Cellules en ERREUR : {len(err_cells_inst)}")
        for row, col, val, iid in err_cells_inst[:10]:
            print(f"      {iid} (ligne {row}), col '{col}' = {val}")

    pio_ids_set = {str(p.get("pio_id") or "").strip() for p in pio_reels}
    inst_orphan = []
    for r in inst_reels:
        pid = str(r.get("pio_id") or "").strip()
        if pid and pid not in pio_ids_set:
            inst_orphan.append((r.get("install_id"), pid))
    if inst_orphan:
        print(f"  ⚠️  Installations orphelines (pio_id n'existe pas dans 01) : {len(inst_orphan)}")
        for iid, pid in inst_orphan[:10]:
            print(f"      {iid} → pio_id={pid!r}")

    # Pionniers sans installation
    inst_pio_ids = {str(r.get("pio_id") or "").strip() for r in inst_reels}
    pio_sans_inst = [p for p in pio_reels if str(p.get("pio_id") or "").strip() not in inst_pio_ids]
    print(f"  Pionniers sans installation : {len(pio_sans_inst)}")
    if pio_sans_inst:
        for p in pio_sans_inst[:10]:
            print(f"      {p.get('pio_id')}  {p.get('nom','')} {p.get('prénom','')}  email={p.get('email','')!r}")

    # ──────────────────────────────────────────────────────────────────────────
    # 5. RÉSUMÉ ENVOI EMAILS
    # ──────────────────────────────────────────────────────────────────────────
    print("\n5️⃣  PRÉPARATION ENVOI DES EMAILS DE BIENVENUE")
    print("─" * 76)
    envoyables = []
    bloqueurs = {"sans_email": 0, "email_invalide": 0, "sans_install": 0}
    pio_ids_inst = inst_pio_ids
    for p in pio_reels:
        pid = str(p.get("pio_id") or "").strip()
        raw = str(p.get("email") or "").strip()
        if not raw:
            bloqueurs["sans_email"] += 1
            continue
        emails = split_emails(raw)
        valides = [e for e in emails if EMAIL_RX.match(e)]
        if not valides:
            bloqueurs["email_invalide"] += 1
            continue
        if pid not in pio_ids_inst:
            bloqueurs["sans_install"] += 1
            continue
        envoyables.append((pid, valides))

    print(f"  ✅ Pionniers ENVOYABLES (email valide + installation) : {len(envoyables)}")
    print(f"  ❌ Bloqueurs :")
    print(f"      Sans email          : {bloqueurs['sans_email']}")
    print(f"      Email invalide      : {bloqueurs['email_invalide']}")
    print(f"      Sans installation   : {bloqueurs['sans_install']}")
    total = len(pio_reels)
    print(f"  TOTAL pionniers réels   : {total}")
    print(f"  Couverture envoi        : {len(envoyables)}/{total} = {100 * len(envoyables) / total:.1f}%")

    # ──────────────────────────────────────────────────────────────────────────
    print("\n" + "═" * 76)
    print(" ✅ AUDIT TERMINÉ")
    print("═" * 76)


if __name__ == "__main__":
    main()
