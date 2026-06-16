"""
Test envoi email de bienvenue — Lidiana Mboty (Moheli, Comores).

Flow:
1. Appelle /api/webhook/livraison avec les données Lidiana.
2. La pipeline génère les docs HTML + les pousse sur GitHub Pages.
3. L'email de bienvenue est envoyé à Mbotyzizylidiana@gmail.com.
4. On récupère le HTML de l'email dans l'outbox.
5. On renvoie le MÊME HTML à sebastien.fumaz@geobuilder.fr via Resend.
6. Vérifie que les 5 URLs des boutons retournent 200 (et non 404).

Usage: python -m scripts.test_email_lidiana_20260217
"""
import os
import sys
import time
import json
import requests
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

API_BASE = os.environ["REACT_APP_BACKEND_URL_FORCED"] if os.environ.get("REACT_APP_BACKEND_URL_FORCED") else None
if not API_BASE:
    # lire depuis frontend/.env
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                API_BASE = line.split("=", 1)[1].strip()
                break
assert API_BASE, "REACT_APP_BACKEND_URL introuvable"

PAYLOAD = {
    "type": "LIVRAISON",
    "nom": "MBOTY",
    "prenom": "Lidiana",
    "email": "Mbotyzizylidiana@gmail.com",
    "telephone": "",
    "territoire": "Comores",
    "pays": "Moheli",
    "produit": "G30",
    "numero_serie": "TEST-LIDIANA-MBOTY",
    "date_installation": time.strftime("%Y-%m-%d"),
    "localisation": "Moheli, Comores",
    "technicien": "",
    "fondateur": False,
    "report_id": f"TEST-LIDIANA-{int(time.time())}",
}

print(f"[1/4] POST {API_BASE}/api/webhook/livraison")
r = requests.post(f"{API_BASE}/api/webhook/livraison", json=PAYLOAD, timeout=120)
print(f"  status: {r.status_code}")
if r.status_code != 200:
    print(r.text)
    sys.exit(1)
resp = r.json()
print(json.dumps({k: v for k, v in resp.items() if k != "github"}, indent=2, ensure_ascii=False))
pio_id = resp["pio_id"]
install_id = resp["install_id"]
print(f"  PIO_ID = {pio_id} | INST_ID = {install_id}")

# Petit délai pour laisser GitHub Pages se déployer (cache CDN)
print("\n[2/4] Attente 5s pour propagation GitHub Pages…")
time.sleep(5)

BASE = os.environ["GITHUB_PAGES_URL"].rstrip("/")
urls = {
    "passeport": f"{BASE}/passeports/{install_id}/index.html",
    "certificat_pionnier": f"{BASE}/certificats/pionnier/{pio_id}.html",
    "certificat_garantie": f"{BASE}/certificats/garantie/{install_id}.html",
    "portail": f"{BASE}/pionniers/{pio_id}/index.html",
    "carte": f"{BASE}/cartes/{pio_id}.html",
    "ambassadeur": f"{BASE}/ambassadeur.html",
}
print(f"\n[3/4] Vérification des 6 URLs du bouton email (Lidiana):")
status_ok = True
for k, u in urls.items():
    rr = requests.head(u, timeout=10, allow_redirects=True)
    flag = "OK" if rr.status_code == 200 else "FAIL"
    print(f"  [{rr.status_code}] {flag:4} {k}: {u}")
    if rr.status_code != 200:
        status_ok = False

# Render le HTML email localement (le endpoint /api/admin/emails-outbox a été retiré).
print(f"\n[4/4] Render email HTML localement + envoi à sebastien.fumaz@geobuilder.fr")
sys.path.insert(0, "/app/backend")
from services.template_service import render_template  # noqa
from datetime import datetime, timezone

annee = str(datetime.now(timezone.utc).year)
ctx_email = {
    "ANNEE": annee,
    "INSTALL_ID": install_id,
    "PAYS": "Moheli",
    "PIO_ID": pio_id,
    "URL_CARTE": urls["carte"],
    "URL_CERTIFICAT": urls["certificat_pionnier"],
    "URL_ESPACE": urls["portail"],
    "URL_FAMILLE": BASE + "/",
    "URL_GARANTIE": urls["certificat_garantie"],
    "URL_PASSEPORT": urls["passeport"],
    "URL_AMBASSADEUR_CTA": urls["ambassadeur"],
    "CTA_AMBASSADEUR_TITLE": "Devenez Ambassadeur",
    "CTA_AMBASSADEUR_DESC": "Les Pionniers ouvrent la voie.",
}
email_html = render_template("email-final.html", ctx_email)

import resend
resend.api_key = os.environ["RESEND_API_KEY"]
sender_email = os.environ["SENDER_EMAIL"]
sender_name = os.environ.get("SENDER_NAME", "").strip()
sender = f"{sender_name} <{sender_email}>" if sender_name else sender_email
resp2 = resend.Emails.send({
    "from": sender,
    "to": ["sebastien.fumaz@geobuilder.fr"],
    "subject": "Bienvenue dans la Famille des Pionniers Geobuilder — Test Lidiana Mboty",
    "html": email_html,
})
print(f"  ✅ Email envoyé à sebastien.fumaz@geobuilder.fr (Resend id={resp2.get('id')})")

print("\nRésumé:")
print(f"  PIO_ID:     {pio_id}")
print(f"  INST_ID:    {install_id}")
print(f"  URLs OK:    {'OUI (les 6 boutons fonctionnent)' if status_ok else 'NON — certaines URLs sont en 404'}")
