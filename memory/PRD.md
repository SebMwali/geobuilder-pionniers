# PRD — Geobuilder Pionniers (Backend FastAPI)

## Original problem statement

Remplacer une automation Make.com défaillante par un backend Python/FastAPI qui :
- utilise **Google Sheets** comme **unique** source de vérité (pas de MongoDB)
- pousse les documents générés (HTML, images extraites du PDF) sur **GitHub Pages**
- expose des webhooks pour la **Livraison** (création complète d'un Pionnier + Installation + documents)
et le **SAV** (ajout maintenance + régénération du passeport)
- envoie un email de bienvenue (mock V1)

L'application doit rester **un moteur documentaire léger**. À terme, Odoo alimentera ce moteur.
Pas d'ERP, pas de gestion de tickets, pas de stocks, pas de planning.

## Architecture validée

- **Base de données** : Google Sheets (onglets `01_Pionniers`, `02_Installations`, `04_Parametres`,
  `05_Maintenances`, `06_Documents`, `08_Automations_Log`)
- **Stockage / hébergement** : GitHub Pages (branche `main-/-/(root)`, dossier `/docs/`)
- **Photos installation** :
  - `photo_generateur_url` : URL **Cloudinary statique** selon le modèle (G30 → URL G30, etc.)
  - `photo_emplacement_url` : **extraite du PDF** d'installation (plus grand JPEG) et poussée sur
    `docs/photos/INST-XXXX/emplacement.jpg`
  - Fallback (clients historiques sans PDF) : `https://res.cloudinary.com/dahmkv4ra/image/upload/v1781392846/G-30_myykrz.png`
- **QR codes** : générés natively côté template via `api.qrserver.com`
  - Passeport → URL du passeport
  - Certificat garantie → URL de validation

## Endpoints API

| Méthode | Route                         | Usage                                                |
|---------|-------------------------------|------------------------------------------------------|
| POST    | `/api/webhook/livraison`      | JSON, payload + optionnel `pdf_url`                  |
| POST    | `/api/webhook/livraison-upload` | multipart/form-data avec PDF en pièce jointe       |
| POST    | `/api/sav/rapport`            | Ajoute une intervention SAV + régénère le passeport  |
| POST    | `/api/admin/sav`              | Admin variant                                         |
| POST    | `/api/admin/livraison`        | Admin variant                                         |
| GET     | `/api/admin/installation/{id}`| Détail installation + historique maintenances        |
| GET     | `/api/admin/pionniers`        | Liste                                                 |
| GET     | `/api/admin/installations`    | Liste                                                 |
| GET     | `/api/admin/maintenances`     | Liste                                                 |
| GET     | `/api/counters`               | État compteurs                                        |
| GET     | `/api/health`                 | Santé intégrations (Sheets, GitHub, Templates)        |

## Pipeline Livraison

1. Alloue IDs : PIO-XXXX, INST-XXXX, 4× DOC-XXXX
2. Si PDF fourni : extrait la photo terrain (plus grand JPEG via PyMuPDF) → push GitHub
3. Photo générateur ← URL Cloudinary statique selon modèle catalog
4. Render templates (passeport, certificats pionnier+garantie, portail, email)
5. Push 4 fichiers HTML sur GitHub Pages
6. Append : 1 ligne `01_Pionniers` (22 cols), 1 ligne `02_Installations` (22 cols, U+V = photos),
   4 lignes `06_Documents` (10 cols)
7. Envoi email mocké

## Pipeline SAV minimal

1. Vérifie l'existence de l'installation
2. Alloue MAINT-XXXX
3. Append 1 ligne `05_Maintenances` (12 cols A→L)
4. Lit l'historique filtré (statuts `Réalisé` / `Terminé` / `OK`)
5. Régénère le passeport et le push sur GitHub
**Aucune photo, aucun ticket, aucun ERP.**

## Structure réelle des Sheets

### 02_Installations (22 colonnes)
A install_id · B pio_id · C produit · D numero_serie · E date_installation · F date_sortie ·
G territoire_installation · H installateur · I installation_status · J pionnier_created ·
K nom_client · L gamme · M contrat_maintenance_type · N date_garantie_fin · O localisation_precise ·
P statut_eau · Q derniere_maintenance · R prochain_entretien · S passeport_url ·
T installation_active · **U photo_generateur_url** · **V photo_emplacement_url**

### 05_Maintenances (12 colonnes)
A maintenance_id · B install_id · C pio_id · D date_intervention · E type_intervention ·
F technicien · G statut · H rapport_url · I observations · J pieces_changees · K prochain_rdv · L source

## What's been implemented (2026-02)

- ✅ Backend FastAPI stable (MongoDB retiré, Google Sheets unique source)
- ✅ Compteurs `04_Parametres` thread-safe
- ✅ Pipeline Livraison E2E (push GitHub Pages, append Sheets)
- ✅ Templates HTML PROD (passeport, certificats, portail, email)
- ✅ **Extraction photo terrain depuis PDF (PyMuPDF, heuristique "plus gros JPEG")**
- ✅ **Endpoint multipart `/api/webhook/livraison-upload`**
- ✅ **Endpoint JSON `/api/webhook/livraison` avec téléchargement d'un `pdf_url`**
- ✅ **Mapping Cloudinary photo générateur par modèle (catalog.py)**
- ✅ **Pipeline SAV minimal `/api/sav/rapport` (append + régénération passeport)**
- ✅ Ancien `/api/webhook/maintenance` retiré
- ✅ Headers Sheets U + V ajoutés à `02_Installations`
- ✅ 61 tests pytest passent (`tests/test_pdf_extractor.py` + `tests/test_sav_pipeline.py`)
- ✅ E2E live sur la prod : `PIO-1157` / `INST-2160` / `MAINT-3124` avec extraction PDF
  + SAV régénération passeport

## Roadmap

### P1 (court terme)
- Email réel (SendGrid / Resend / SMTP) — actuellement mocké
- Filtrage de la photo générateur Cloudinary pour tous les modèles (seul G30 mappé)

### P2 (futur)
- URL_CARTE (génération carte d'identité Pionnier) — variable du template aujourd'hui masquée
- Conversion HTML → PDF via WeasyPrint (V1 = HTML statique uniquement)
- Marquage manuel Fondateurs / page Ambassadeur pour clients Mayotte historiques
- Migration future vers Odoo (Pionniers reste un moteur documentaire alimenté par Odoo)

### Refactoring optionnel
- Déplacement des routes hors de `server.py` vers `/app/backend/routes/` si volume augmente
- Suppression définitive de `MaintenanceInput` (actuellement marquée DEPRECATED)
- Suppression de `pdf_service.py` (WeasyPrint) si on confirme qu'on n'en a pas besoin
