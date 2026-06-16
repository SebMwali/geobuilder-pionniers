# PLAN OPÉRATIONNEL — EXÉCUTION PROGRESSIVE GEOBUILDER PIONNIERS

*Fin de la phase d'analyse. Place à l'exécution.*

---

## 🎯 Vision globale

Passer d'un système **incomplet et fragile** à un système **fiable et exploitable**, sans jamais mettre en péril les données historiques.

**Stratégie en 8 lots indépendants**, chacun apportant une **valeur métier mesurable**, exécutables en parallèle quand le permettent les dépendances.

---

## 📊 Vue d'ensemble priorisée

| Ordre | Lot | Valeur métier | Risque | Durée |
|---|---|---|---|---|
| 🥇 | **LOT 0** — Fiabilisation immédiate | Élimine les erreurs visibles aujourd'hui | 🟢 | 2 h |
| 🥈 | **LOT 1** — Détection doublons + endpoint régénération | Évite les doublons silencieux + débloque cas 2 | 🟢 | 1 j |
| 🥉 | **LOT 2** — Collecte NS via app | Récupère progressivement les NS manquants | 🟡 | 3-4 j |
| 4 | **LOT 3** — Liaison pionniers/générateurs | Met en cohérence 01 ↔ 02 au fil de la collecte | 🟢 | continu |
| 5 | **LOT 4** — Intégration historique SAV | Récupère 91 interventions Lot A | 🟡 | 1-2 j |
| 6 | **LOT 5** — Multi-générateurs (UI espace) | Affichage propre des Pionniers multi-installations | 🟡 | 2 j |
| 7 | **LOT 6** — Régénération passeports existants | Met à jour tout après évolutions structurelles | 🟢 | 0.5 j |
| 8 | **LOT 7** — Exports Odoo | Anticipe la migration finale | 🟢 | 2 j |

**Total chemin critique** : ~3 semaines en exécution séquentielle ; ~2 semaines avec parallélisation.

---

# 🥇 LOT 0 — FIABILISATION IMMÉDIATE

## Objectif
Éliminer les pollutions visibles dans le Sheet en quelques heures, sans rien casser.

## Actions concrètes
1. **Suppression** des onglets `03_Medias` (vide) et `07_Produits` (doublon de `07_Catalog`)
2. **Renommage statut** `"En attente"` → `"Pionnier"` (196 lignes de `01_Pionniers`)
3. **Correction des 4 `#REF!`** dans `02_Installations.pio_id` (INST-2109, 2120, 2148, 2149) — arbitrage cas par cas
4. **Dédoublonnage** des 3 NS doublons dans `01_Pionniers` (héritage du remplissage v1)
5. **Sortie** des 17 structures quasi-certaines de `01_Pionniers` (vers archive CSV — pas vers un nouvel onglet)
6. **Complétion** des 8 lignes "acronymes" (prénom manquant) après votre arbitrage

## Prérequis
- ✅ Snapshot JSON intégral des onglets concernés (sauvegarde)
- ✅ Tests backend `/app/backend/tests` au vert (76/76 OK)

## Impact utilisateur
- 🟢 Aucun (modifications admin uniquement)
- L'app reste opérationnelle pendant tout le LOT

## Risque
🟢 **Minime** — chaque action est isolée, reversible via le snapshot

## Durée estimée
**2 heures**, avec validation interactive à chaque action

## Dépendances
Aucune — démarrable immédiatement

## Livrable
Sheet propre, audit-ready, prêt à recevoir les lots suivants.

---

# 🥈 LOT 1 — DÉTECTION DOUBLONS + ENDPOINT RÉGÉNÉRATION

## Objectif
1. Bloquer la création de doublons silencieux à chaque webhook
2. Permettre la régénération d'un Pionnier existant (cas 2 du rapport 7)

## Actions concrètes

### 1.1 Détection doublons (R-DEDUP-1)
- Modifier `server.py` (`/api/webhook/intervention`)
- Avant `INSERT` Pionnier, calculer hash `lowercase(email) + uppercase(nom)`
- Si match dans `01_Pionniers` existant → **bloquer création**, retourner `pio_id` existant
- Logger dans `08_Automations_Log` (action=`doublon_detecte`)

### 1.2 Endpoint régénération
- Nouveau : `POST /api/admin/regenerate-pionnier/{pio_id}`
- Lit `01_Pionniers` et `02_Installations`
- Regénère les 5 HTML (passeport, certif, garantie, portail, carte)
- Push GitHub Pages
- Renvoie email de bienvenue (option `force_email=true`)
- Logge l'opération

### 1.3 Tests pytest
- Ajouter tests unitaires : doublon, régénération nominale, régénération sans install

## Prérequis
- ✅ LOT 0 terminé (Sheet propre)
- ✅ Suite de tests à jour

## Impact utilisateur
- 🟢 Transparent pour les Pionniers existants
- 🟡 Si app SAV envoie un doublon → reçoit une réponse `409 Conflict` à gérer côté app

## Risque
🟢 Faible — protégé par tests et idempotence

## Durée estimée
**1 jour** (dev + tests + déploiement)

## Dépendances
LOT 0

## Livrable
- 1 fonctionnalité critique (dedup)
- 1 endpoint admin opérationnel
- Tests pytest +2/+3

---

# 🥉 LOT 2 — COLLECTE NS VIA APPLICATION

## Objectif
Récupérer progressivement les ~80% de NS manquants en autonomie utilisateur, sans saisie admin.

## Actions concrètes

### 2.1 UI espace pionnier
- Ajouter carte "📷 Renseignez votre N° de série" dans `portail_pionnier.html`
- Visible **uniquement** si `numero_serie` vide pour au moins 1 install du pionnier
- Lien vers nouveau formulaire `/pionniers/{pio_id}/saisir-ns.html`

### 2.2 Formulaire saisie
- Template `saisir_ns.html` : sélecteur d'installation (si plusieurs) + champ NS + upload photo
- Validation côté front : regex format NS
- Soumission via `POST /api/pionnier/saisir-ns`

### 2.3 Backend validation
- Endpoint reçoit `{pio_id, install_id, numero_serie, photo_base64}`
- Contrôle :
  - Format regex
  - Unicité (NS pas déjà attribué)
  - Cohérence préfixe ↔ produit
- Si tous OK → stocke en **attente de validation humaine** dans `08_Automations_Log` (action=`ns_pending_validation`)
- Sinon → renvoie erreur explicite

### 2.4 Interface admin de validation
- Endpoint `GET /api/admin/ns-pending` → liste les saisies à valider
- Endpoint `POST /api/admin/ns-validate/{id}` → valide ou rejette
- **Sur validation** :
  - Update `02_Installations.numero_serie`
  - `source_creation = "ns_via_app"`
  - Régénère Passeport
  - Notif email au Pionnier
- **Sur rejet** : notif email "Veuillez vérifier votre saisie"

### 2.5 Email de relance
- Script `python3 scripts/relance_ns_manquants.py` (manuel pour démarrer)
- Envoi groupé "Saisissez votre NS"

## Prérequis
- ✅ LOT 0 + LOT 1
- ✅ Photo upload : storage simple (GitHub Pages ou Cloudinary)

## Impact utilisateur
- 🔴 Visible — nouvelle carte sur l'espace Pionnier
- ✅ Bénéfice direct : SAV personnalisé activé une fois le NS saisi

## Risque
🟡 Modéré — nouveau flux UI + nouveau endpoint avec validation humaine

## Durée estimée
**3-4 jours** (UI + backend + admin + emails)

## Dépendances
LOT 0, LOT 1

## Livrable
- 1 carte UI sur espace pionnier
- 1 formulaire de saisie
- 2 endpoints backend (saisir / valider)
- 1 vue admin (liste des saisies à valider)
- 1 email de relance opérationnel

---

# LOT 3 — LIAISON PIONNIERS ↔ GÉNÉRATEURS (continu)

## Objectif
Maintenir la cohérence 01 ↔ 02 au fur et à mesure que les NS arrivent.

## Actions concrètes
1. **Script de synchronisation hebdomadaire** :
   - Pour chaque NS validé dans `02_Installations`, vérifier que la garantie `date_garantie_fin` est cohérente
   - Mettre à jour la carte "Mon installation" sur les espaces concernés (régénération auto)
2. **Audit hebdomadaire d'intégrité** :
   - NS orphelins (présents dans 02 mais aucun pio_id valide)
   - Pionniers actifs sans aucune installation
   - Doublons NS détectés
   - Rapport envoyé par email à l'admin

## Prérequis
- ✅ LOT 2 (collecte active)

## Impact utilisateur
- 🟢 Aucun

## Risque
🟢 Minime — purement passif et de lecture/écriture limitée

## Durée estimée
**Continu** — 0.5 j de mise en place initiale, puis automatique

## Dépendances
LOT 2

## Livrable
- 1 script `scripts/sync_pionniers_installations.py`
- 1 cron de rapport hebdomadaire

---

# LOT 4 — INTÉGRATION HISTORIQUE SAV

## Objectif
Importer les **91 interventions du Lot A** (validées dans le rapport d'audit) dans `05_Maintenances`.

## Actions concrètes

### 4.1 Préparation des données
- Repartir du fichier `lot_A_interventions_detail.csv` (déjà produit)
- Pour chaque ligne :
  - Lookup `install_id` via NS
  - Lookup `pio_id` via install
  - Construire `maintenance_id` (auto-incrémenté)
  - `report_id = "IMPORT-{NS}-{date}"` (idempotence)

### 4.2 Import en batch
- Script `python3 scripts/import_historique_sav.py`
- Batch update sur `05_Maintenances` (1 seul appel API)
- Source : `"import_csv_2026"`

### 4.3 Validation post-import
- Vérification : 91 lignes créées, aucun doublon
- Affichage du `report_id` rejeté pour idempotence

### 4.4 Lot B (16 interventions) — différé
- Liste séparée en attente de votre arbitrage cas par cas

## Prérequis
- ✅ LOT 0 + LOT 2 (NS connus)
- ⚠️ Certaines interventions Lot A référencent des NS pas encore dans `02_Installations` → import partiel possible

## Impact utilisateur
- 🟢 Aucun à court terme
- 🟡 À terme : historique visible dans espace pionnier (carte "Mon historique SAV" — Lot 5)

## Risque
🟡 Modéré — données externes, qualité variable

## Durée estimée
**1-2 jours** (script + tests + validation)

## Dépendances
LOT 0. Mieux : LOT 2 partiellement complet.

## Livrable
- Script d'import
- 91 lignes intégrées dans `05_Maintenances`
- Rapport de validation

---

# LOT 5 — MULTI-GÉNÉRATEURS (UI espace pionnier)

## Objectif
Afficher proprement les Pionniers qui possèdent plusieurs générateurs (cas 4 du rapport 7).

## Actions concrètes

### 5.1 Adapter `portail_pionnier.html`
- Si `len(installations) > 1` → afficher un **carousel** ou **onglets** par installation
- Chaque installation affiche : NS, date_installation, date_garantie_fin, photo, lien Passeport, lien Garantie

### 5.2 Adapter le passeport
- 1 passeport par installation (déjà le cas dans le code)
- Pas de changement majeur, juste vérification du rendu

### 5.3 Adapter l'email de bienvenue
- Si le Pionnier reçoit un 2e générateur : email différent ("Bienvenue dans votre 2e installation")

## Prérequis
- ✅ LOT 2 (NS connus) — sinon le carousel n'a rien à afficher

## Impact utilisateur
- 🔴 Visible — nouveau rendu pour les Pionniers multi-installations
- ✅ Bénéfice : ils voient tous leurs générateurs au même endroit

## Risque
🟡 Modéré — template HTML à tester sur plusieurs cas

## Durée estimée
**2 jours**

## Dépendances
LOT 2 (idéalement)

## Livrable
- Template `portail_pionnier.html` v2 (carousel)
- Email "2e générateur" différencié
- Tests sur 3-5 cas réels

---

# LOT 6 — RÉGÉNÉRATION DES PASSEPORTS EXISTANTS

## Objectif
Mettre à jour TOUS les passeports existants après les évolutions structurelles (LOTs 0, 2, 5).

## Actions concrètes

### 6.1 Script de régénération en masse
- Pour chaque ligne de `02_Installations` non-orpheline :
  - Régénérer Passeport (template à jour)
  - Push GitHub Pages
  - Update `06_Documents`
- Logging dans `08_Automations_Log`

### 6.2 Régénération sélective
- Endpoint admin `POST /api/admin/regenerate-all` (avec dry-run)
- Possibilité de filtrer par : territoire, date, statut

### 6.3 Régénération espaces pionniers
- Idem pour tous les `portail_pionnier.html` après LOT 5

## Prérequis
- ✅ LOT 0, 1, 2, 4, 5 terminés

## Impact utilisateur
- 🔴 Visible — tous les pionniers voient leurs documents mis à jour
- ✅ Cohérence totale

## Risque
🟡 Modéré — un bug de template casse 100+ documents simultanément. **Toujours faire un dry-run d'abord.**

## Durée estimée
**0.5 jour** (exécution + validation)

## Dépendances
LOTs 0, 1, 2, 4, 5

## Livrable
- 1 endpoint admin
- 1 script de régénération massive
- Tous les documents alignés sur la dernière version des templates

---

# LOT 7 — PRÉPARATION EXPORTS ODOO

## Objectif
Anticiper la migration finale en produisant les exports CSV adaptés à l'import natif Odoo.

## Actions concrètes

### 7.1 Mapping documenté
- Document `/app/memory/MAPPING_ODOO.md` :
  - `01_Pionniers` → `res.partner` (catégorie "Pionnier", `is_company=False`)
  - `02_Installations` → modèle custom `geobuilder.installation`
  - `05_Maintenances` → modèle custom `geobuilder.maintenance` ou `helpdesk.ticket`
  - `07_Catalog` → `product.template`

### 7.2 Scripts d'export
- `scripts/export_odoo_pionniers.py` → `exports/odoo_partners.csv`
- `scripts/export_odoo_installations.py` → `exports/odoo_installations.csv`
- `scripts/export_odoo_maintenances.py` → `exports/odoo_maintenances.csv`
- `scripts/export_odoo_products.py` → `exports/odoo_products.csv`

### 7.3 Tests
- Vérifier que les CSV sont importables dans une instance Odoo de test (vous fournissez l'instance ou je simule via dry-run)

### 7.4 Documentation de migration
- Marche à suivre pour l'import (ordre, dépendances FK)
- Plan de rollback (snapshot Odoo pré-import)

## Prérequis
- ✅ LOTs 0-6 terminés (données stables)

## Impact utilisateur
- 🟢 Aucun (préparatoire)

## Risque
🟢 Minime — scripts de lecture seule + génération de fichiers

## Durée estimée
**2 jours**

## Dépendances
LOTs 0 à 6

## Livrable
- 4 scripts d'export prêts à l'emploi
- 1 document de mapping
- 1 procédure de migration documentée

---

# 📅 Calendrier proposé (exécution séquentielle)

| Semaine | Lots | Jalons |
|---|---|---|
| **S1** | LOT 0 + LOT 1 | Sheet propre + anti-doublon |
| **S2** | LOT 2 (début) + LOT 4 | Collecte NS active + SAV intégré |
| **S3** | LOT 2 (fin) + LOT 3 + LOT 5 | Multi-générateurs + audit continu |
| **S4** | LOT 6 + LOT 7 | Régénération + préparation Odoo |

**Total** : ~4 semaines en exécution sérielle, **~3 semaines en parallélisant** (LOT 4 ↔ LOT 2, LOT 5 ↔ LOT 3, LOT 7 ↔ LOT 6).

---

# 🎯 Démarrage proposé

**Je propose de démarrer immédiatement le LOT 0 (2h, risque minimal)** dans l'ordre suivant :

1. ✅ **Snapshot intégral** des 11 onglets (sauvegarde JSON)
2. ✅ **Suppression de `03_Medias`** (onglet vide)
3. ✅ **Suppression de `07_Produits`** (doublon obsolète)
4. ✅ **Renommage statut** "En attente" → "Pionnier" sur 196 lignes
5. ✅ **Arbitrage des 4 `#REF!`** (je vous montre les 4 cas, vous décidez)
6. ✅ **Dédoublonnage des 3 NS** dans `01_Pionniers`
7. ✅ **Validation des 17 structures à sortir** (cas par cas)
8. ✅ **Test backend** (tous les `pytest` doivent passer)

**Souhaitez-vous que je lance le LOT 0 maintenant ?**

a. ✅ **Oui, démarre par le snapshot puis enchaîne avec validation à chaque étape**
b. 🔍 **Montre-moi le détail des 4 `#REF!` et des 3 NS doublons d'abord**
c. ✏️ **Modifier l'ordre des LOTs** (lequel prioriser ?)
d. 🚦 **Démarrer par un autre LOT** que le LOT 0 (lequel ?)
