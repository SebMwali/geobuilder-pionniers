# Documentation — Intégration SAV → Pionniers (V2)

## 🎯 Architecture finale

```
Technicien → Rapport SAV → SAV-app → Bloc PIONNIERS-DATA → Pionniers (Backend FastAPI)
                                                                ↓
                                                  Google Sheets + GitHub Pages + Email
```

**Aucun intermédiaire (Make, Zapier, etc.) requis.** Demain, Odoo remplacera SAV en utilisant exactement le même contrat d'API.

---

## 📡 Endpoints exposés

| URL | Méthode | Usage |
|-----|---------|-------|
| `POST /api/webhook/livraison` | JSON | Création d'un Pionnier (LIVRAISON). PDF transmis via URL. |
| `POST /api/webhook/livraison-upload` | multipart/form-data | Idem, mais PDF en pièce jointe directe. |
| `POST /api/sav/rapport` | JSON | Ajout d'une intervention SAV existante (régénère le passeport). |

**Base URL de production (preview en cours) :**
```
https://pioneer-ecosystem.preview.emergentagent.com
```

---

## 1️⃣ Endpoint LIVRAISON — JSON (mode recommandé)

`POST /api/webhook/livraison`

### Payload — schéma PIONNIERS-DATA officiel

```json
{
  "type": "LIVRAISON",
  "report_id": "f2d742da-aef0-4e14-886c-7a5c08fd439d",

  "nom": "FUMAZ",
  "prenom": "Sebastien",
  "email": "sebastien.fumaz@geobuilder.fr",
  "telephone": "+262 692 12 34 56",

  "numero_serie": "HR88C25DAZ0100",
  "produit": "G30",
  "territoire": "MAYOTTE",
  "pays": "FRANCE",

  "localisation": "Rue de la Paix, Mamoudzou",
  "date_installation": "2026-06-14",
  "technicien": "Bacar",
  "fondateur": false,

  "rapport_pdf_url": "https://sav-supervisor-app.preview.emergentagent.com/api/reports/<uuid>/pdf",

  "photo_generateur_url": "",
  "photo_emplacement_url": ""
}
```

### Champs

| Champ | Type | Obligatoire | Notes |
|-------|------|:---:|-------|
| `type` | string | ✅ | Toujours `"LIVRAISON"` pour cet endpoint |
| `report_id` | string | ⚠️ Recommandé | UUID unique du rapport SAV. **Clé d'idempotence** côté Pionniers. |
| `nom` | string | ✅ | Nom de famille |
| `prenom` | string | ✅ | Prénom |
| `email` | string | ✅ | Adresse e-mail valide |
| `telephone` | string | ❌ | Format libre |
| `numero_serie` | string | ✅ | NS du générateur, format libre |
| `produit` | string | ✅ | Code modèle : `G30`, `G20`, `OCEAN500`, `TITAN1000`, `SOURCE` |
| `territoire` | string | ✅ | `MAYOTTE`, `REUNION`, `MOHELI`, `FRANCE`, etc. |
| `pays` | string | ❌ | Si absent, prend la valeur de `territoire` |
| `localisation` | string | ❌ | Adresse précise |
| `date_installation` | string | ❌ | Format `YYYY-MM-DD`. Si absent, date du jour. |
| `technicien` | string | ❌ | Nom du technicien (stocké en col H de `02_Installations`) |
| `fondateur` | bool | ❌ | Si `true` → génère `ambassadeur.html` immédiatement |
| `rapport_pdf_url` | string | ❌ | URL du PDF. Pionniers télécharge et extrait la photo terrain. |
| `photo_generateur_url` | string | ❌ | Override (sinon Cloudinary statique selon `produit`) |
| `photo_emplacement_url` | string | ❌ | Override (sinon extrait du PDF, sinon fallback) |

### Réponse — `200 OK`

```json
{
  "pio_id": "PIO-1158",
  "install_id": "INST-2161",
  "url_portail":    "https://sebmwali.github.io/geobuilder-pionniers/pionniers/PIO-1158/index.html",
  "url_passeport":  "https://sebmwali.github.io/geobuilder-pionniers/passeports/INST-2161/index.html",
  "url_certificat": "https://sebmwali.github.io/geobuilder-pionniers/certificats/pionnier/PIO-1158.html",
  "url_garantie":   "https://sebmwali.github.io/geobuilder-pionniers/certificats/garantie/INST-2161.html",
  "url_ambassadeur":"https://sebmwali.github.io/geobuilder-pionniers/ambassadeurs/PIO-1158.html",
  "photo_generateur_url":  "https://res.cloudinary.com/.../G30-_fqyqhz.png",
  "photo_emplacement_url": "https://sebmwali.github.io/.../photos/INST-2161/emplacement.jpg",
  "report_id": "f2d742da-aef0-4e14-886c-7a5c08fd439d",
  "github": { "passeport": "...", "certificat_pionnier": "...", ... }
}
```

### Idempotence — `200 OK` avec `idempotent_replay: true`

Si vous renvoyez le **même `report_id`**, Pionniers ne rejoue rien et retourne les IDs existants :

```json
{
  "pio_id": "PIO-1158",
  "install_id": "INST-2161",
  "url_passeport": "...",
  "idempotent_replay": true,
  "report_id": "f2d742da-..."
}
```

→ Vous pouvez réessayer sans risque de doublon.

### Erreurs

| Code | Cause |
|------|-------|
| `422` | Champ obligatoire manquant ou type invalide |
| `502` | Erreur de push GitHub Pages (très rare, réessayer) |
| `500` | Erreur interne (consultez les logs Pionniers) |

---

## 2️⃣ Endpoint LIVRAISON — multipart (PDF en pièce jointe)

`POST /api/webhook/livraison-upload`

Identique au précédent **mais** :
- `Content-Type: multipart/form-data`
- Tous les champs (sauf `rapport_pdf_url`) sont envoyés en champs de formulaire (`Form()`)
- Le PDF est envoyé directement en pièce jointe sous le nom `pdf`

Exemple `curl` :
```bash
curl -X POST https://pioneer-ecosystem.preview.emergentagent.com/api/webhook/livraison-upload \
  -F "type=LIVRAISON" \
  -F "report_id=f2d742da-..." \
  -F "nom=FUMAZ" -F "prenom=Sebastien" \
  -F "email=sebastien.fumaz@geobuilder.fr" \
  -F "numero_serie=HR88C25DAZ0100" \
  -F "produit=G30" -F "territoire=MAYOTTE" -F "pays=FRANCE" \
  -F "localisation=Rue de la Paix, Mamoudzou" \
  -F "date_installation=2026-06-14" \
  -F "technicien=Bacar" -F "fondateur=false" \
  -F "pdf=@/path/to/rapport.pdf"
```

---

## 3️⃣ Endpoint SAV — rapport d'intervention

`POST /api/sav/rapport`

Pour les **interventions post-installation** (préventive, corrective, contrôle, etc.).
**Ne crée PAS de PIO/INST/DOC.** Ajoute juste une ligne d'historique et régénère le passeport.

### Payload

```json
{
  "install_id": "INST-2161",
  "date_intervention": "2026-08-15",
  "type_intervention": "Maintenance préventive 6 mois",
  "technicien": "Karim Mwali",
  "statut": "Réalisé",
  "observations": "Filtre changé, contrôle OK",
  "pieces_changees": "Filtre charbon actif",
  "prochain_rdv": "2027-02-15",
  "source": "sav-app",
  "rapport_url": "https://sav-app.../reports/<uuid>/pdf"
}
```

### Statuts qui apparaissent dans l'historique passeport
- `Réalisé`
- `Terminé`
- `OK`

Tous les autres statuts sont **ignorés** dans le passeport (mais conservés dans `05_Maintenances`).

### Réponse

```json
{
  "maintenance_id": "MAINT-3125",
  "install_id": "INST-2161",
  "pio_id": "PIO-1158",
  "url_passeport": "https://sebmwali.github.io/geobuilder-pionniers/passeports/INST-2161/index.html"
}
```

---

## 📋 Catalogue des produits supportés

| Code à envoyer dans `produit` | Label affiché | Garantie | Photo générateur |
|-------------------------------|---------------|----------|------------------|
| `G30` ou `G30 Home`           | G30 Home      | 24 mois  | Cloudinary `G30-_fqyqhz.png` |
| `G20` ou `G20 MOJA`           | G20 Moja      | 24 mois  | _(à mapper P1)_ |
| `OCEAN500` ou `Ocean 500`     | Ocean 500     | 36 mois  | _(à mapper P1)_ |
| `TITAN1000` ou `Titan 1000`   | Titan 1000    | 60 mois  | _(à mapper P1)_ |
| `SOURCE` ou `Source`          | Source        | 24 mois  | _(à mapper P1)_ |

Un code inconnu sera accepté avec une garantie par défaut de 24 mois.

---

## 🔐 Authentification

**Aucune** sur les 3 endpoints publics ci-dessus. Pionniers fait confiance à l'amont (SAV/Odoo).

> Vous pouvez ajouter un Bearer token / IP allowlist plus tard si nécessaire.

---

## 🧪 Test manuel rapide

```bash
curl -X POST https://pioneer-ecosystem.preview.emergentagent.com/api/webhook/livraison \
  -H "Content-Type: application/json" \
  -d '{
    "type": "LIVRAISON",
    "report_id": "test-001",
    "nom": "TEST", "prenom": "John",
    "email": "test@example.com",
    "numero_serie": "TEST-NS-001",
    "produit": "G30", "territoire": "MAYOTTE",
    "date_installation": "2026-06-14"
  }'
```

Devrait répondre `HTTP 200` avec PIO/INST/URLs.

Re-jouer la même commande → renvoie les mêmes IDs avec `idempotent_replay: true`.
