# PRD — Geobuilder Pionniers (Backend FastAPI)

## Original problem statement
Remplacer une automatisation Make.com défaillante par un backend Python/FastAPI pour le produit "Geobuilder" (Pionniers de l'eau). Le système utilise STRICTEMENT Google Sheets comme base de données (pas de MongoDB), génère des documents HTML dynamiques (Passeport d'installation, Certificats Pionnier/Garantie, Badge, Ambassadeur), les publie sur GitHub Pages, et envoie un email de bienvenue via Resend.

**Langue utilisateur**: Français uniquement.

## Architecture
- Backend: FastAPI (Python)
- Database: Google Sheets ONLY
- File storage/hosting: GitHub Pages (`PyGithub`)
- Email: Resend SDK (domaine `geobuilder.fr` vérifié)
- PDF extraction: PyMuPDF (image + texte `Modèle`/`Adresse`)
- QR code: api.qrserver.com

## Webhook entrant
`POST /api/webhook/livraison` — payload SAV-natif minimal (ns, client, email_client, date, rapport_pdf_url, report_id) OU payload PIONNIERS-DATA canonique complet. Idempotence via `report_id` stocké en col W de `02_Installations`.

## Templates publiés (5 fichiers GitHub Pages par livraison)
1. `docs/passeports/{INST_ID}/index.html` — Passeport d'installation
2. `docs/certificats/pionnier/{PIO_ID}.html` — Certificat Pionnier
3. `docs/certificats/garantie/{INST_ID}.html` — Certificat de garantie
4. `docs/pionniers/{PIO_ID}/index.html` — Portail Pionnier (espace personnel)
5. `docs/cartes/{PIO_ID}.html` — **Badge Pionnier HTML éditable** (avec QR code vers espace)

Si `fondateur=true` : push supplémentaire `docs/ambassadeurs/{PIO_ID}.html`.

## What's been implemented

### Session du 15/02/2026 (suite — itération 2)
- ✅ **Email — Pictogrammes bleu électrique** : SVG 40×40 #3A8FE8 au-dessus de chaque stat (Personne / Globe / Calendrier) selon charte V1
- ✅ **Email — Bouton "Ma Famille" → "Devenez Ambassadeur"** :
  - Pour non-fondateur : pointe vers `docs/ambassadeur.html` (landing universelle existante)
  - Pour fondateur : pointe vers `docs/ambassadeurs/{PIO}.html` (page perso)
  - Titre en bleu pour attirer l'œil + bordure carte plus marquée
- ✅ **Email — Gmail trim "..." résolu** (marqueur invisible + `<table>` HTML, refactor cards en table-based)
- ✅ **Passeport — middle button "Certificat de Garantie" → "Devenez Ambassadeur"** : doc-card du milieu remplacée avec pictogramme étoile et lien vers `ambassadeur.html`. Garantie reste accessible via le gros bouton "VOIR LE CERTIFICAT DE GARANTIE" du bloc Vérification.
- ✅ **Badge Pionnier** : utilise maintenant la **vraie image vierge** fournie comme background + overlay HTML aux positions calibrées (1024×1536 ratio). Nom client, territoire, année, QR code parfaitement positionnés.
- ✅ **Ambassadeur footer (per-pionnier)** : logo Geobuilder externe (URL job autre) → logo hébergé sur GitHub Pages `assets/geobuilder-logo.png`.
- ✅ Tests pytest 80/80 OK.

### Session du 14/02/2026
- ✅ Bypass Make.com complet — webhook direct SAV → Pionniers
- ✅ Extraction PDF (photo, Modèle, Adresse) via PyMuPDF
- ✅ Idempotence par `report_id`
- ✅ Génération `ambassadeur.html` pour fondateurs
- ✅ Resend API intégré, email réel envoyé
- ✅ QR garantie corrigé

### Session du 15/02/2026 (cette session)
- ✅ **Email — Image bannière** : extraction du base64 inline (165KB) → hébergée sur GitHub Pages `assets/email-header.jpeg`. Gmail rend maintenant l'image (le base64 inline était bloqué/affiché en raw).
- ✅ **Email — Multipart/alternative** : ajout fallback `text` dans Resend → Gmail mobile rend correctement le HTML.
- ✅ **Email — Stats alignement** : refactor `display:table` → `<table>` HTML natif (compat Gmail mobile, plus de `...` de troncature).
- ✅ **Email — Doublon image header** : suppression de la 2ème balise `<img>` en bas du template.
- ✅ **Email — Liens corrigés** : `Mon Passeport` → `{{URL_PASSEPORT}}` GitHub Pages (avant : `geobuilder.fr/install/...` cassé). `Ma Carte` → URL badge généré.
- ✅ **Email + Portail — `target="_blank"`** sur tous les boutons.
- ✅ **Passeport** : MANUEL → `G30 USER MANUAL-1.pdf`, FICHE → `Geobuilder_Fiche_G30.pdf`, PRENDRE RDV + ASSISTANCE → `tel:+262262666374`, TÉLÉCHARGER TOUS LES DOCS → `display:none`.
- ✅ **Certificat Pionnier** : TERRITOIRE = MAYOTTE (fix priorité `payload.territoire or payload.pays` au lieu de `payload.pays or payload.territoire`).
- ✅ **Badge Pionnier HTML éditable** (`badge-pionnier.html`) :
  - Design CSS pur selon charte Geobuilder V1 (Montserrat, #0D0D0D, #3A8FE8)
  - Variables : `{{NOM_COMPLET}}`, `{{PIO_ID}}`, `{{TERRITOIRE}}`, `{{ANNEE}}`, `{{URL_ESPACE}}`, `{{QR_URL_ENCODED}}`
  - Logo GEOBUILDER chrome + tagline "REPRENONS LE POUVOIR SUR L'EAU"
  - QR code centré avec halo bleu → renvoie vers Espace Pionnier
  - CTA bleu vers espace + ID PIO en footer
  - 100% portable, sans dépendance image
- ✅ **Tests pytest** : 80/80 passent.

## Schema Google Sheets
- `01_Pionniers` (22 col) : col T `certificat_url`, col U `carte_url` (badge), col V `qr_code_url` (V1 vide)
- `02_Installations` (23 col) : col U `photo_generateur_url`, col V `photo_emplacement_url`, col W `report_id`
- `04_Parametres` : compteurs
- `05_Maintenances` (12 col) : historique SAV
- `06_Documents` (10 col) : log de documents générés

## Prioritized backlog

### P0 — Backlog suivant
- 🟡 **Refonte `portail_pionnier.html`** selon charte graphique V1 :
  - Font Montserrat (Google Fonts)
  - Fond #0D0D0D, accents #3A8FE8
  - Logo Geobuilder header officiel (à héberger : asset `Geobuilder.png` disponible)
  - Tagline "REPRENONS LE POUVOIR SUR L'EAU"
  - Cards sobres, titres "Première lettre bleue + reste blanc"
  - Style sobre, premium, humain, épuré

### P1
- ⏳ Recevoir version **vide** du badge image (sans nom hardcodé) si le user souhaite le design "image riche" plutôt que le CSS pur actuel
- ⏳ Vérification visuelle QR code Passeport → Certificat Garantie

### P2 — Future
- Adapter mapping territoire pour Maurice, Madagascar, Comores
- Mapping Cloudinary G20/OCEAN500/TITAN1000/SOURCE (au-delà G30)
- Conversion HTML→PDF (WeasyPrint) pour certificats imprimables
- Refactor `server.py` (~1090 lignes) en routes/

## 3rd party integrations
- Google Sheets API (Service Account JSON, dans `/app/backend/.env`)
- GitHub API (PAT, dans `.env`)
- Resend (API key, dans `.env`, domaine `geobuilder.fr` vérifié)
- QR code: api.qrserver.com (gratuit, sans clé)

## Files of reference
- `/app/backend/server.py` (orchestration pipeline)
- `/app/backend/services/email_service.py` (Resend + fallback text)
- `/app/backend/services/catalog.py` (URLs produits)
- `/app/backend/services/pdf_extractor.py` (PyMuPDF)
- `/app/backend/templates/email-final.html`
- `/app/backend/templates/badge-pionnier.html` ⭐ nouveau
- `/app/backend/templates/passeport_installation.html`
- `/app/backend/templates/certificat-pionnier.html`
- `/app/backend/templates/portail_pionnier.html` (à refondre)
