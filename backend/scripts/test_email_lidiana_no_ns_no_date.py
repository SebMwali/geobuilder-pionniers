"""Test combiné — Lidiana Mboty sans NS ET sans date_installation.
Vérifie les 2 fallbacks mailto sur Passeport + Portail, et le nouveau visuel
du Badge Ambassadeur sur /ambassadeur.html.
Destinataire: sebastien.fumaz@geobuilder.fr."""
import os, sys, time, requests
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")
with open("/app/frontend/.env") as f:
    for line in f:
        if line.startswith("REACT_APP_BACKEND_URL="):
            API_BASE = line.split("=", 1)[1].strip(); break

PAYLOAD = {
    "type": "LIVRAISON",
    "nom": "MBOTY",
    "prenom": "Lidiana",
    "email": "sebastien.fumaz@geobuilder.fr",
    "territoire": "Comores",
    "pays": "Moheli",
    "produit": "G30",
    "numero_serie": "NON RENSEIGNÉ",          # → fallback NS
    # date_installation OMISE → fallback date
    "fondateur": False,
    "report_id": f"TEST-LIDIANA-NS-DATE-{int(time.time())}",
}

print(f"[1/3] POST /api/webhook/livraison (sans NS et sans date)")
r = requests.post(f"{API_BASE}/api/webhook/livraison", json=PAYLOAD, timeout=120)
print(f"  status: {r.status_code}")
if r.status_code != 200:
    print(r.text); sys.exit(1)
resp = r.json()
pio_id, install_id = resp["pio_id"], resp["install_id"]
print(f"  PIO_ID = {pio_id} | INST_ID = {install_id}")

print("\n[2/3] Attente 90s propagation GitHub Pages…")
time.sleep(90)

BASE = os.environ["GITHUB_PAGES_URL"].rstrip("/")
urls = {
    "passeport": f"{BASE}/passeports/{install_id}/index.html",
    "portail":   f"{BASE}/pionniers/{pio_id}/index.html",
    "ambassadeur": f"{BASE}/ambassadeur.html",
}
print("[3/3] Vérification fallbacks NS + Date + image Badge Ambassadeur:")
ok = 0
for k, u in urls.items():
    rr = requests.get(u, timeout=15)
    flag = "OK" if rr.status_code == 200 else "FAIL"
    extras = []
    if rr.status_code == 200:
        body = rr.text
        if k in ("passeport","portail"):
            extras.append(f"mailto_NS={'YES' if 'Transmission N° de série' in body else 'NO'}")
            extras.append(f"mailto_DATE={'YES' if 'Transmission date de livraison' in body else 'NO'}")
            extras.append(f"texte_côté={'YES' if 'sur le côté' in body else 'NO'}")
        if k == "ambassadeur":
            new_img = "sebmwali.github.io/geobuilder-pionniers/badge-ambassadeur.png"
            old_img = "customer-assets.emergentagent.com"
            extras.append(f"new_badge_img={'YES' if new_img in body else 'NO'}")
            extras.append(f"old_emergent_img={'NO (good)' if old_img not in body else 'YES (BAD)'}")
    print(f"  [{rr.status_code}] {flag:4} {k}: {u}")
    for e in extras: print(f"          - {e}")
    if rr.status_code == 200: ok += 1

print(f"\nRésumé: {ok}/{len(urls)} URLs OK | Pionnier test: {pio_id} / {install_id}")
print("Email reçu par sebastien.fumaz@geobuilder.fr — Vérifier visuellement les boutons:")
print("  - Passeport : bloc NS \"Non renseigné\" + bloc date \"Non renseignée\" (côté avec mailto)")
print("  - Portail   : bloc NS \"Non renseigné\" + bloc date \"Date de livraison non renseignée\"")
print("  - /ambassadeur.html : image badge = nouveau visuel GitHub Pages")
