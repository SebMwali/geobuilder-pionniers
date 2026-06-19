"""
Mass mailing — Welcome Pionniers.

USAGE:
  # Mode SAFE (par défaut, aucun envoi, ne modifie rien) :
  python3 scripts/mass_mailing_send.py

  # Mode RÉEL (envoie via Resend + marque welcome_email_sent=true dans le Sheet) :
  python3 scripts/mass_mailing_send.py --confirm-send

  # Reprendre un envoi interrompu (saute ceux déjà marqués welcome_email_sent=true) :
  python3 scripts/mass_mailing_send.py --confirm-send --resume

Filtre :
  - statut ∈ {Pionnier, Fondateur, En attente}
  - email non vide et valide
  - welcome_email_sent ≠ true  (sauf si --force)

Logs : /tmp/mass_mailing_YYYYMMDD_HHMMSS.log
"""
import argparse
import asyncio
import os
import re
import sys
import time
from datetime import datetime

from dotenv import load_dotenv
load_dotenv('/app/backend/.env')
sys.path.insert(0, '/app/backend')

from services.sheets_service import get_sheets_service
from services.email_service import send_email_mock, parse_email_field
from services.template_service import render_template

EMAIL_RX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PAGES_BASE = os.environ.get("GITHUB_PAGES_URL", "").rstrip("/")
SUBJECT = "Bienvenue dans la Famille des Pionniers Geobuilder"
THROTTLE_SECONDS = 0.6  # Resend: 2 req/s max → on reste sous la limite
DAILY_QUOTA_CAP = 95  # Resend free plan = 100/jour. On garde une marge de 5.

LOG_PATH = f"/tmp/mass_mailing_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"


def log(msg: str):
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def build_url_map(install_rows):
    """pio_id → install_id (le 1er trouvé)."""
    mapping = {}
    for r in install_rows:
        pid = (r.get("pio_id") or "").strip()
        iid = (r.get("install_id") or "").strip()
        if pid and iid and pid not in mapping:
            mapping[pid] = iid
    return mapping


def build_ctx_email(pio_id, install_id, pays, fondateur):
    annee = str(datetime.now().year)
    url_carte_pionnier = f"{PAGES_BASE}/cartes/{pio_id}.html"
    url_badge_fondateur = f"{PAGES_BASE}/badges/fondateur/{pio_id}.html"
    return {
        "ANNEE": annee,
        "INSTALL_ID": install_id,
        "PAYS": pays,
        "PIO_ID": pio_id,
        "URL_CARTE": url_badge_fondateur if fondateur else url_carte_pionnier,
        "URL_CERTIFICAT": f"{PAGES_BASE}/certificats/pionnier/{pio_id}.html",
        "URL_ESPACE": f"{PAGES_BASE}/pionniers/{pio_id}/index.html",
        "URL_FAMILLE": PAGES_BASE + "/",
        "URL_GARANTIE": f"{PAGES_BASE}/certificats/garantie/{install_id}.html" if install_id else "",
        "URL_PASSEPORT": f"{PAGES_BASE}/passeports/{install_id}/index.html" if install_id else "",
        "URL_AMBASSADEUR_CTA": f"{PAGES_BASE}/ambassadeur.html",
        "CTA_AMBASSADEUR_TITLE": "Devenez Ambassadeur",
        "CTA_AMBASSADEUR_DESC": "Les Pionniers ouvrent la voie.",
    }


async def send_one(record, dry: bool):
    pio_id = record["pio_id"]
    name = record["name"]
    to = record["to"]
    cc = record["cc"]
    fondateur = record["fondateur"]
    install_id = record["install_id"]

    if dry:
        flag = "[FONDATEUR]" if fondateur else ""
        cc_s = (" CC=" + ",".join(cc)) if cc else ""
        log(f"  DRY {pio_id} {name} {flag} → {to}{cc_s} (install={install_id or 'NONE'})")
        return ("DRY", None)

    try:
        ctx = build_ctx_email(pio_id, install_id, record["pays"], fondateur)
        html = render_template("email-final.html", ctx)
        resp = await send_email_mock(
            to,
            SUBJECT,
            html,
            metadata={"pio_id": pio_id, "install_id": install_id, "campaign": "mass_welcome"},
            tags={"pio_id": pio_id, "install_id": install_id, "template": "bienvenue_livraison",
                  "campaign": "mass_welcome"},
            cc=cc or None,
        )
        status = resp.get("status", "?")
        eid = resp.get("id", "")
        return (status, eid)
    except Exception as e:
        return ("ERROR", str(e))


async def run(args):
    sheets = get_sheets_service()
    log(f"📂 Log file: {LOG_PATH}")
    log(f"🔧 Mode: {'REAL SEND' if args.confirm_send else 'SAFE DRY (no send)'}")
    if args.confirm_send and PAGES_BASE == "":
        log("❌ GITHUB_PAGES_URL manquant dans .env — abort.")
        return

    log("📥 Lecture 01_Pionniers...")
    pionniers = sheets.read_all("pionniers")
    log("📥 Lecture 02_Installations...")
    installs = sheets.read_all("installations")
    pio_to_install = build_url_map(installs)
    log(f"   {len(pionniers)} pionniers / {len(installs)} installations")

    eligible = []
    for r in pionniers:
        statut = (r.get("statut") or "").strip().lower()
        if statut and statut not in ("pionnier", "fondateur", "en attente"):
            continue
        pio_id = (r.get("pio_id") or "").strip()
        email_raw = (r.get("email") or "").strip()
        if not pio_id or not email_raw:
            continue
        to, cc = parse_email_field(email_raw)
        if not to or not EMAIL_RX.match(to):
            continue
        welcome_sent = str(r.get("welcome_email_sent") or "").strip().lower() in ("true", "1", "yes", "oui")
        if welcome_sent and not args.force:
            continue
        eligible.append({
            "pio_id": pio_id,
            "name": f"{(r.get('prenom') or '').strip()} {(r.get('nom') or '').strip()}".strip(),
            "to": to,
            "cc": cc,
            "pays": (r.get("pays") or "").strip(),
            "fondateur": (r.get("fondateur") or "").strip().lower() == "true",
            "install_id": pio_to_install.get(pio_id, ""),
        })

    log(f"✅ {len(eligible)} destinataires éligibles")
    if args.confirm_send and len(eligible) > DAILY_QUOTA_CAP:
        log(f"⚠️  Resend free = 100/jour. Cap appliqué à {DAILY_QUOTA_CAP} → "
            f"{len(eligible) - DAILY_QUOTA_CAP} reste(nt) pour la prochaine campagne.")
        eligible = eligible[:DAILY_QUOTA_CAP]
    if not args.confirm_send:
        log("⚠️  AUCUN ENVOI — passez --confirm-send pour déclencher l'envoi réel.")

    sent_ok, sent_fail = 0, 0
    for i, rec in enumerate(eligible, 1):
        status, info = await send_one(rec, dry=not args.confirm_send)
        if args.confirm_send:
            ok_statuses = ("sent", "SENT", "OK", "ok", "queued")
            if status in ok_statuses:
                sent_ok += 1
                # Marque welcome_email_sent=true
                try:
                    idx = sheets.find_row_index_by("pionniers", "pio_id", rec["pio_id"])
                    if idx:
                        sheets.update_cell("pionniers", idx, "welcome_email_sent", "true")
                except Exception as e:
                    log(f"  ⚠️ Sheet update failed for {rec['pio_id']}: {e}")
                log(f"  ✅ [{i}/{len(eligible)}] {rec['pio_id']} {rec['name']} → {rec['to']} (id={info})")
            else:
                sent_fail += 1
                log(f"  ❌ [{i}/{len(eligible)}] {rec['pio_id']} {rec['name']} → {rec['to']} ERR={status} {info}")
            await asyncio.sleep(THROTTLE_SECONDS)

    log("=" * 60)
    if args.confirm_send:
        log(f"🏁 TERMINÉ — OK={sent_ok}  FAIL={sent_fail}  TOTAL={len(eligible)}")
    else:
        log(f"🏁 DRY-RUN TERMINÉ — {len(eligible)} prêts. Relancez avec --confirm-send pour envoyer.")
    log(f"📂 Log: {LOG_PATH}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--confirm-send", action="store_true",
                   help="Active l'envoi réel via Resend + marque welcome_email_sent=true.")
    p.add_argument("--force", action="store_true",
                   help="Renvoie même aux destinataires déjà marqués welcome_email_sent=true.")
    p.add_argument("--resume", action="store_true",
                   help="(no-op, alias logique car welcome_email_sent skip déjà par défaut).")
    args = p.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
