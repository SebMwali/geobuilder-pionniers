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

### Session du 15/02/2026 (itération 7 — Badges luxe Fondateur + Ambassadeur dans passeport)
- ✅ Import des templates **`badge-fondateur.html`** (458 KB) et **`badge-ambassadeur.html`** (537 KB) depuis le repo GitHub dans `/app/backend/templates/`
- ✅ Variables dynamiques : `{{PIO_ID}}`, `{{ANNEE}}`, `{{PAYS}}` (uniquement pour badge-ambassadeur)
- ✅ Rendu automatique pour chaque fondateur → push sur `docs/badges/fondateur/{PIO}.html` et `docs/badges/ambassadeur/{PIO}.html`
- ✅ **Statut Communauté du passeport** = 2 iframes ratio natif 794×1059 scalé à 0.3527 (cards 280×374)
- ✅ Overlay "✓ FONDATEUR ACQUIS" / "✓ AMBASSADEUR ACQUIS" en vert sous chaque badge
- ✅ Carte Ambassadeur du portail → pointe désormais vers `/badges/ambassadeur/{PIO}.html` (badge personnalisé)
- ✅ PIO-1186 patché rétroactivement avec ces 2 nouveaux badges

### Session du 15/02/2026 (itération 6 — Cold start mitigation)
- ✅ Diagnostic confirmé par support Emergent : preview = scale-to-zero, pas d'always-on toggle
- ⚠️ Workaround : GitHub Actions cron `.github/workflows/keepalive.yml` à coller manuellement (PAT n'a pas scope `workflow`)
- 📌 Solution propre suggérée : passer en Emergent Deploy (50 crédits/mois = 24/7)

### Session du 15/02/2026 (suite — itération 5 : Espace Pionnier finalisation visuelle)
- ✅ **Hero landscape** : nouvelle image aérienne tropicale `DJI_0516.jpg` poussée sur `docs/assets/portail-hero-landscape.jpg` (océan Indien — île, lagon turquoise, plages)
- ✅ **Voile hero** : dégradé diagonal 55%→30%→65% pour lisibilité texte + text-shadow renforcé
- ✅ **Titres hero** : `Bonjour Sébastien` en blanc, accent `--blue-bright` sur le prénom, pill `PIO-ID` avec backdrop-blur
- ✅ **Logo header & footer** : remplacé par Cloudinary `Couverture_FB_n9rsza.png` (140×62 / 130×54)
- ✅ **Restructuration "Vos Documents Officiels"** : passage de 4 à **6 cartes** en grille 3×2 — intègre désormais Carte Ambassadeur + Carte Super Ambassadeur
- ✅ **Section "Communauté"** : réduite — ne contient plus que le bloc WhatsApp (centré verticalement, agrandi, ombre verte)
- ✅ **Cards lock/grey** : Carte Ambassadeur + Super Ambassadeur grisées (filter:grayscale, opacity:0.45, pointer-events:none) tant que non acquises
- ✅ **Cleanup CSS** : suppression complète des classes `.mini-card*` devenues inutiles
- ✅ Tests pytest 80/80 ✓

### Session du 15/02/2026 (itération 4 : Espace Pionnier amélioré)
- ✅ **Espace Pionnier** : ajout 2 mini-cartes Ambassadeur + Super Ambassadeur (greyed/locked si non acquises)
- ✅ **WhatsApp** : module compact (au lieu du gros bloc centré)
- ✅ **Texte Super Ambassadeur** : "Vous êtes très actif, montrez votre Geobuilder et inspirez d'autres Pionniers."
- ✅ **Footer tagline** : "Ensemble, construisons le monde de demain"
- ✅ **Désignation produit** : juste "G30" (label depuis catalog, sans suffixe "HOME — SÉRIE LIMITÉE")
- ✅ **Voile header** : éclairci (de 85-95% à 18-55%)
- ✅ **URL Instagram** : `https://www.instagram.com/geobuilderoceanindien/` intégrée
- ✅ Catalog G30 : URL Cloudinary `G-30_myykrz.png`
- ✅ Tests pytest 80/80

### À traiter demain (session 16/02)
- 🟡 **Logo header espace pionnier** : remplacer par `Couverture_FB_n9rsza.png` (bannière FB Geobuilder horizontale)
- 🟡 **Voile + image hero** : le voile est encore trop foncé, et l'image montre la famille (email-header.jpeg) au lieu du paysage Comores envoyé par user. Il doit me renvoyer l'image paysage.
- 🟡 **Image installation G30** : possiblement cache Cloudinary à purger (le user voit encore le mauvais visuel)
- 🟡 **Option 1 vs Option 2 catalogue produits** : attente décision user — gérer les désignations dans Google Sheets (07_Catalog) ou dans Python (catalog.py) ?
- 🟡 **Ajouter autres produits** (G60, OCEAN500, TITAN1000...) avec leurs vraies désignations selon décision

### Session du 15/02/2026 (suite — itération 3 : Espace Pionnier + Badge final)
- ✅ **Refonte complète `portail_pionnier.html`** selon charte Geobuilder V1 :
  - Layout : Header logo + Hero (Bonjour + PIO badge + Membre depuis) + MON INSTALLATION (image produit + métadonnées + garantie)
  - 3 distinctions hexagonales argent/bleu (Pionnier ✓ Acquis / Ambassadeur ⏳ En cours / Super Ambassadeur ❌ Non acquis)
  - 4 cartes documents (Certificat Pionnier, Garantie, Passeport, Carte) avec icônes SVG chrome
  - Bloc Communauté WhatsApp (CTA vert)
  - Besoin d'aide (téléphone, email, web)
  - Footer thanks + 4 réseaux sociaux (FB, IG placeholder, YouTube, LinkedIn)
  - Police Montserrat
  - Fond #05080F, accents #3A8FE8
  - Calcul automatique : mois adhésion FR, date installation FR, date fin garantie (+24 mois)
- ✅ **Téléphone/email alignés sur passeport** : `+262 262 66 63 74` / `contact@geobuilder.fr`
- ✅ **URLs sociales réelles intégrées** : Facebook, YouTube, LinkedIn, WhatsApp (lien groupe Geobuilder)
- ✅ **Badge Pionnier** : nom centré entre LED1 (40.8%) et LED2 (52.1%) à 46.5% ; bouton "Imprimer / Sauvegarder en PDF" (style certificat) ; QR centré pixel-perfect avec droplet ; animation pulse + tilt 3D
- ✅ **Bleu Geobuilder #3A8FE8 partout** (révert depuis le cyan vers le vrai bleu charte) avec effet glow électrique sur pictos et LED bars
- ✅ **Email** : pictos PNG hébergés (Gmail-compatibles) + 2 LED bars signature horizontales + alignement cards uniforme (height 78px) + CTA "Devenez Ambassadeur" / "Les Pionniers ouvrent la voie."
- ✅ **Passeport** : middle button "Certificat de Garantie" → "Devenez Ambassadeur"
- ✅ Tests pytest 80/80

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
