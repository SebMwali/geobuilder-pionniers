# PRD — Geobuilder Pionniers (Backend FastAPI)

## Original problem statement

Remplacer une automation Make.com défaillante par un backend Python/FastAPI qui :
- utilise **Google Sheets** comme **unique** source de vérité
- pousse les documents (HTML, photos extraites du PDF) sur **GitHub Pages**
- expose des webhooks **directs SAV → Pionniers** (suppression de Make)
- conserve une architecture découplée pour qu'Odoo puisse remplacer SAV sans toucher Pionniers
- envoie un email de bienvenue (mock V1)

L'application doit rester **un moteur documentaire léger**. Aucun ERP, ticket, planning, stock, tournée.

## Architecture validée (V2 — sans Make)

```
SAV-app (ou Odoo demain) → POST /api/webhook/livraison
                                   ↓
                          Bloc PIONNIERS-DATA (JSON canonique)
                                   ↓
                       Backend Pionniers (FastAPI)
                                   ↓
                Google Sheets + GitHub Pages + Email
```

- **Base de données** : Google Sheets (`01_Pionniers`, `02_Installations`, `04_Parametres`, `05_Maintenances`, `06_Documents`, `08_Automations_Log`)
- **Stockage / hébergement** : GitHub Pages (branche `main-/-/(root)`, dossier `/docs/`)
- **Photos installation** :
  - `photo_generateur_url` : URL **Cloudinary statique** selon modèle (G30 mappé en V1)
  - `photo_emplacement_url` : **extraite du PDF** d'installation (PyMuPDF, plus grand JPEG)
  - Fallback : `https://res.cloudinary.com/dahmkv4ra/image/upload/v1781392846/G-30_myykrz.png`
- **Idempotence** : `report_id` stocké en col W de `02_Installations`. Renvois ignorés.
- **Fondateur** : `fondateur=true` → génère `docs/ambassadeurs/{pio_id}.html` immédiatement.

## Schéma PIONNIERS-DATA officiel

Voir `/app/memory/SAV_INTEGRATION.md` pour la spec complète (champs, types, exemples curl).

## Endpoints API

| Méthode | Route | Usage |
|---------|-------|-------|
| POST | `/api/webhook/livraison` | JSON PIONNIERS-DATA (mode principal) |
| POST | `/api/webhook/livraison-upload` | multipart/form-data avec PDF en pièce jointe |
| POST | `/api/sav/rapport` | Ajout intervention + régénère passeport |
| POST | `/api/admin/sav` | Variant admin |
| POST | `/api/admin/livraison` | Variant admin |
| GET | `/api/admin/installation/{id}` | Détail + historique maintenances |
| GET | `/api/admin/pionniers` / `installations` / `maintenances` | Listes |
| GET | `/api/counters` | État compteurs |
| GET | `/api/health` | Santé intégrations |

## Inventaire QR codes

| Document | Destination du QR |
|---|---|
| `passeport_installation.html` | `passeport_url` (sa propre URL GitHub Pages) |
| `certificat-garantie.html` | `URL_GARANTIE` (sa propre URL GitHub Pages) ← V2 corrigé |
| `certificat-pionnier.html` | Aucun QR (document symbolique) |
| `portail_pionnier.html` | Aucun QR |
| `ambassadeur.html` | Aucun QR |
| `email-final.html` | Aucun QR |

## Structure réelle des Sheets

### 02_Installations (23 colonnes)
A install_id · B pio_id · C produit · D numero_serie · E date_installation · F date_sortie ·
G territoire_installation · H installateur · I installation_status · J pionnier_created ·
K nom_client · L gamme · M contrat_maintenance_type · N date_garantie_fin · O localisation_precise ·
P statut_eau · Q derniere_maintenance · R prochain_entretien · S passeport_url ·
T installation_active · U **photo_generateur_url** · V **photo_emplacement_url** · W **report_id**

### 05_Maintenances (12 colonnes)
A maintenance_id · B install_id · C pio_id · D date_intervention · E type_intervention ·
F technicien · G statut · H rapport_url · I observations · J pieces_changees · K prochain_rdv · L source

### 01_Pionniers (22 colonnes)
A pio_id · B nom · C prenom · D email · E telephone · F pays · G territoire · H client_type ·
I date_entree · J statut · **K fondateur** · **L ambassadeur** · M-V (divers)

## What's been implemented (2026-02)

### Phase V1
- Backend FastAPI stable, MongoDB retiré
- Compteurs `04_Parametres` thread-safe
- Pipeline Livraison E2E (Sheets + GitHub Pages)
- Templates HTML PROD (passeport, certificats, portail, email)
- Extraction photo PDF (PyMuPDF, plus gros JPEG)
- Mapping Cloudinary G30
- Pipeline SAV minimal `/api/sav/rapport`
- 61 tests pytest

### Phase V2 — Architecture sans Make
- ✅ Refonte `LivraisonInput` au schéma PIONNIERS-DATA canonique
- ✅ Idempotence via `report_id` (col W, check pré-traitement)
- ✅ Suppression toute logique dérivation NS
- ✅ Champ `fondateur` → génère `ambassadeur.html` automatiquement
- ✅ Template `ambassadeur.html` intégré (depuis le repo GitHub `docs/`)
- ✅ Fix QR certificat-garantie (pointe maintenant vers sa propre URL, plus geobuilder.fr/install/)
- ✅ Endpoint multipart accepte fondateur / report_id / type / technicien
- ✅ Tests V2 : idempotence, fondateur, schéma PIONNIERS-DATA (10 tests)
- ✅ E2E live validé : `PIO-1158/INST-2161` avec fondateur=true → ambassadeur publié + idempotence vérifiée
- ✅ Doc d'intégration SAV → Pionniers (`/app/memory/SAV_INTEGRATION.md`)

**Total tests : 71/71 ✅**

## Roadmap

### P1 — Court terme
- Email réel (SendGrid / Resend / SMTP) — actuellement mocké
- Mapper photo générateur Cloudinary pour G20, OCEAN500, TITAN1000, SOURCE
- Configurer `AMBASSADEUR_WEBHOOK_URL` env var pour le formulaire ambassadeur (collecte consentement)

### P2 — Futur
- `URL_CARTE` (génération carte d'identité Pionnier) — variable du template aujourd'hui masquée
- Conversion HTML → PDF via WeasyPrint (V1 = HTML statique uniquement)
- Logique automatique "Ambassadeur après 60 jours" pour nouveaux clients (actuellement seuls les fondateurs déclenchent ambassadeur)
- Migration future Odoo → Pionniers (architecture déjà compatible : même endpoint, même schéma)

### Refactoring optionnel
- Déplacement routes hors `server.py` vers `/app/backend/routes/`
- Suppression `MaintenanceInput` (DEPRECATED) une fois confirmé qu'aucun consommateur ne l'utilise
