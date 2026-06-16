"""
Test envoi email de bienvenue SANS numéro de série — Lidiana Mboty.

But: vérifier que le fallback mailto: s'affiche correctement dans le Passeport
et le Portail Pionnier quand NS est absent (cas "Pionniers en attente de NS").

Trick: la validation backend exige `numero_serie` non-vide ; on envoie donc la
valeur sentinelle "NON RENSEIGNÉ" qui est interprétée comme manquante par
`_render_ns_bloc_passeport()` et `_render_ns_bloc_portail()` (voir server.py
lignes 264-295 : tous les `("NON RENSEIGNÉ", "NON RENSEIGNE", "N/A", "-", "")`
déclenchent le bloc mailto).

Destinataire unique: sebastien.fumaz@geobuilder.fr.
"""
import os
import sys
import time
import json
import requests
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

with open("/app/frontend/.env") as f:
    for line in f:
        if line.startswith("REACT_APP_BACKEND_URL="):
            API_BASE = line.split("=", 1)[1].strip()
            break

PAYLOAD = {
    "type": "LIVRAISON",
    "nom": "MBOTY",
    "prenom": "Lidiana",
    "email": "sebastien.fumaz@geobuilder.fr",  # email du test, comme destinataire unique
    "telephone": "",
    "territoire": "Comores",
    "pays": "Moheli",
    "produit": "G30",
    "numero_serie": "NON RENSEIGNÉ",  # sentinelle → fallback mailto
    "date_installation": time.strftime("%Y-%m-%d"),
    "localisation": "Moheli, Comores",
    "fondateur": False,
    "report_id": f"TEST-LIDIANA-NO-NS-{int(time.time())}",
}

print(f"[1/3] POST {API_BASE}/api/webhook/livraison (sans NS)")
r = requests.post(f"{API_BASE}/api/webhook/livraison", json=PAYLOAD, timeout=120)
print(f"  status: {r.status_code}")
if r.status_code != 200:
    print(r.text)
    sys.exit(1)
resp = r.json()
pio_id = resp["pio_id"]
install_id = resp["install_id"]
print(f"  PIO_ID = {pio_id} | INST_ID = {install_id}")
print(f"  Email envoyé à: {PAYLOAD['email']}")

print("\n[2/3] Attente 90s pour propagation GitHub Pages…")
time.sleep(90)

BASE = os.environ["GITHUB_PAGES_URL"].rstrip("/")
urls = {
    "passeport": f"{BASE}/passeports/{install_id}/index.html",
    "certificat_pionnier": f"{BASE}/certificats/pionnier/{pio_id}.html",
    "certificat_garantie": f"{BASE}/certificats/garantie/{install_id}.html",
    "portail": f"{BASE}/pionniers/{pio_id}/index.html",
    "carte": f"{BASE}/cartes/{pio_id}.html",
    "ambassadeur": f"{BASE}/ambassadeur.html",
}
print("[3/3] Vérification des 6 boutons + présence du fallback mailto:")
ok = 0
for k, u in urls.items():
    rr = requests.get(u, timeout=10)
    flag = "OK" if rr.status_code == 200 else "FAIL"
    extra = ""
    if rr.status_code == 200 and k in ("passeport", "portail"):
        has_mailto = "mailto:contact@geobuilder.fr" in rr.text
        has_label = "Non renseigné" in rr.text or "N° de série non renseigné" in rr.text
        extra = f" | mailto={'YES' if has_mailto else 'NO'} | fallback_label={'YES' if has_label else 'NO'}"
    print(f"  [{rr.status_code}] {flag:4} {k}: {u}{extra}")
    if rr.status_code == 200:
        ok += 1

print(f"\nRésumé: {ok}/{len(urls)} boutons OK | Pionnier: {pio_id} / {install_id}")
print("Email reçu par sebastien.fumaz@geobuilder.fr — vérifier que les blocs NS dans Passeport et Portail affichent le bouton mailto.")
