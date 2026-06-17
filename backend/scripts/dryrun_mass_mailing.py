"""
DRY-RUN du mailing de masse — N'ENVOIE AUCUN EMAIL.

Lit `01_Pionniers` et simule l'envoi du welcome email :
- Comptabilise les destinataires éligibles
- Détecte les emails multiples (`;` ou `,`) → TO + CC
- Détecte les emails manquants ou invalides
- Affiche un échantillon
"""
import os, sys, re
from dotenv import load_dotenv
load_dotenv('/app/backend/.env')
sys.path.insert(0, '/app/backend')

from services.sheets_service import get_sheets_service
from services.email_service import parse_email_field

EMAIL_RX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def main():
    sheets = get_sheets_service()
    rows = sheets.read_all("pionniers")
    total = len(rows)

    eligibles = []
    skipped_inactif = []
    skipped_already = []
    missing_email = []
    invalid_email = []
    multi_email = []

    for r in rows:
        statut = (r.get("statut") or "").strip()
        pio_id = (r.get("pio_id") or "").strip()
        nom = (r.get("nom") or "").strip()
        prenom = (r.get("prenom") or "").strip()
        email_raw = (r.get("email") or "").strip()
        welcome_sent = (str(r.get("welcome_email_sent") or "").strip().lower() in ("true", "1", "yes", "oui"))

        if statut and statut.lower() not in ("pionnier", "fondateur"):
            skipped_inactif.append((pio_id, statut))
            continue

        if not email_raw:
            missing_email.append((pio_id, f"{prenom} {nom}"))
            continue

        to, cc = parse_email_field(email_raw)
        if not to:
            missing_email.append((pio_id, f"{prenom} {nom}"))
            continue
        if not EMAIL_RX.match(to):
            invalid_email.append((pio_id, f"{prenom} {nom}", to))
            continue

        all_addrs = [to] + cc
        is_multi = len(all_addrs) > 1
        if is_multi:
            multi_email.append((pio_id, f"{prenom} {nom}", all_addrs))

        eligibles.append({
            "pio_id": pio_id,
            "name": f"{prenom} {nom}".strip(),
            "to": to,
            "cc": cc,
            "fondateur": (r.get("fondateur") or "").strip().lower() == "true",
            "welcome_sent": welcome_sent,
        })

    to_send = [e for e in eligibles if not e["welcome_sent"]]
    already_sent = [e for e in eligibles if e["welcome_sent"]]

    # === RAPPORT ===
    sep = "=" * 80
    print(sep)
    print("  🔎 DRY-RUN MASS MAILING — Welcome Pionniers (AUCUN ENVOI)")
    print(sep)
    print()
    print("📊 RÉCAPITULATIF GLOBAL")
    print(f"  Total lignes lues          : {total}")
    print(f"  ✅ Éligibles (TO valide)    : {len(eligibles)}")
    print(f"     - À envoyer (non envoyé): {len(to_send)}")
    print(f"     - Déjà envoyés          : {len(already_sent)}")
    print(f"  ⚠️ Emails multiples (;/,)  : {len(multi_email)}")
    print(f"  ❌ Email manquant           : {len(missing_email)}")
    print(f"  ❌ Email invalide           : {len(invalid_email)}")
    print(f"  ⏭️ Statut inactif/autre    : {len(skipped_inactif)}")
    print()

    if multi_email:
        print("🔀 EMAILS MULTIPLES — TO/CC qui seront utilisés")
        print("-" * 80)
        for pid, name, addrs in multi_email:
            print(f"  {pid} — {name}")
            print(f"    TO : {addrs[0]}")
            for cc in addrs[1:]:
                print(f"    CC : {cc}")
        print()

    if missing_email:
        print("❌ EMAIL MANQUANT")
        for pid, name in missing_email:
            print(f"  - {pid} — {name}")
        print()

    if invalid_email:
        print("❌ EMAIL INVALIDE")
        for pid, name, addr in invalid_email:
            print(f"  - {pid} — {name} — `{addr}`")
        print()

    if skipped_inactif:
        print("⏭️ STATUTS INACTIFS / AUTRES")
        for pid, statut in skipped_inactif:
            print(f"  - {pid} — statut=`{statut}`")
        print()

    print("📨 ÉCHANTILLON (5 premiers éligibles à envoyer)")
    print("-" * 80)
    for e in to_send[:5]:
        cc_str = (" + CC=" + ", ".join(e["cc"])) if e["cc"] else ""
        flag = " [FONDATEUR]" if e["fondateur"] else ""
        print(f"  {e['pio_id']} — {e['name']}{flag}")
        print(f"    TO : {e['to']}{cc_str}")
    print()
    print(sep)
    print(f"  ✅ DRY-RUN OK — Prêt à envoyer {len(to_send)} emails")
    print(sep)


if __name__ == "__main__":
    main()
