# RAPPORT 6 — STRUCTURE CIBLE ORIENTÉE MÉTIER & EXPLOITATION

*Version recentrée sur la réalité du projet : Sheet transitoire, migration future Odoo, 01_Pionniers = référence absolue, Pionniers = particuliers uniquement, NS = donnée d'enrichissement progressif.*

---

## 1. Principes directeurs (verrouillés)

| # | Principe | Conséquence |
|---|---|---|
| 1 | **Le Sheet est transitoire** | Pas d'optimisation ERP. Priorité au fonctionnement fiable de l'app, pas à la pureté du modèle. |
| 2 | **01_Pionniers = référence absolue** | Toute autre table dépend de `pio_id`. Pas de structure parallèle. |
| 3 | **Pionnier = particulier uniquement** | Entreprises, administrations, associations **sortent du périmètre**. Elles ne sont **pas** réintégrées ailleurs dans le Sheet. |
| 4 | **`pio_id` = identifiant principal** | Le NS reste une **donnée technique d'enrichissement progressif**, pas une clé métier. |
| 5 | **Migration Odoo future** | Le Sheet doit rester **exportable proprement** (CSV, mapping clair vers entités Odoo). |
| 6 | **Collecte NS via l'app** | Workflow utilisateur côté espace pionnier (à concevoir). Pas d'imports massifs depuis sources externes. |

---

## 2. Périmètre du Sheet (resserré)

### Ce qui RESTE

| Onglet | Rôle métier | Volume cible |
|---|---|---|
| `01_Pionniers` | Particuliers du programme | ~85-100 |
| `02_Installations` | Générateurs liés à un pionnier | ~85-110 (1+ par pionnier) |
| `05_Maintenances` | Historique SAV | progressif |
| `06_Documents` | Index des HTML générés | 5 par pionnier |
| `04_Parametres` | Compteurs IDs | 4 compteurs |
| `07_Catalog` | Catalogue produits dynamique | 9 produits |
| `08_Automations_Log` | Logs + idempotence + audit eIDAS | progressif |

### Ce qui SORT

| Onglet | Raison | Action |
|---|---|---|
| `03_Medias` | Vide, jamais utilisé | Supprimer |
| `07_Produits` | Doublon obsolète de `07_Catalog` | Supprimer |
| `00_Fondateurs` | Travail temporaire | Archiver + supprimer une fois les fondateurs reportés dans `01.fondateur=true` |
| `Import` | 118 contacts externes non particuliers ou déjà présents | Archiver + supprimer après recoupement |

### Ce qui NE SERA PAS créé

- ❌ Pas de `09_Clients_B2B` (les structures ne sont pas dans le programme)
- ❌ Pas de `03_Ambassadeurs` séparé (les signatures restent dans `08_Automations_Log` et les flags dans `01_Pionniers` — c'est suffisant pour le périmètre transitoire)
- ❌ Pas de table d'utilisateurs admin séparée
- ❌ Pas de table catalogue détaillée (le `07_Catalog` actuel suffit)

---

## 3. Structure cible — Vue métier

```
   ┌──────────────────────────┐
   │      01_Pionniers        │  ← RÉFÉRENCE ABSOLUE
   │   (particuliers uniqt)   │
   └──────────────────────────┘
              │
              │ 1 → N
              ▼
   ┌──────────────────────────┐
   │     02_Installations     │  ← 1+ générateurs par pionnier
   │  (NS = enrichi via app)  │
   └──────────────────────────┘
              │
              │ 1 → N
              ▼
   ┌──────────────────────────┐
   │     05_Maintenances      │  ← historique SAV progressif
   └──────────────────────────┘

   Side: 06_Documents, 07_Catalog, 04_Parametres, 08_Automations_Log
         (supports techniques de l'app, n'apparaissent pas dans le workflow Pionnier)
```

---

## 4. `01_Pionniers` — Colonnes recentrées sur l'utile

| Colonne | Rôle | Statut |
|---|---|---|
| `pio_id` (PK) | Identifiant Pionnier | 🔒 CRITIQUE |
| `nom` | Nom de famille (MAJUSCULES) | 🔒 CRITIQUE |
| `prenom` | Prénom | 🔒 CRITIQUE |
| `email` | Contact principal | 🔒 CRITIQUE |
| `telephone` | Contact secondaire | ✅ Conservé |
| `pays` | France / Mayotte / etc. | ✅ Conservé |
| `territoire` | Mayotte / Réunion / Comores / etc. | ✅ Conservé (à compléter) |
| `date_entree` | Date d'entrée dans la communauté | ✅ Conservé (à compléter) |
| `statut` | "Pionnier" / "Inactif" | 🟡 À normaliser ("En attente" → "Pionnier") |
| `fondateur` | true/false | 🔒 CRITIQUE (badge Fondateur) |
| `ambassadeur` | true/false | 🔒 CRITIQUE (déverrouillage cartes) |
| `super_ambassadeur` | true/false | ⚠️ À ajouter (aujourd'hui caché dans `communaute_statut`) — plus lisible |
| `droit_image` | true/false | ✅ (eIDAS) |
| `temoignage_autorise` | true/false | ✅ (eIDAS) |
| `source_creation` | "backend_livraison" / "import_2026" | ✅ Conservé |
| `commentaire` | Notes libres admin | ⚠️ À ajouter |

**À retirer** (sans risque) :
- `NS` → déjà dans `02_Installations.numero_serie`, redondance source d'erreur
- `client_type` → toujours "Particulier" par définition
- `communaute_statut` → remplacé par `super_ambassadeur=bool`
- `visite_possible` → non utilisé
- `workflow_status` → vide / non utilisé
- `welcome_email_sent` → faux positif systématique
- `certificat_url`, `carte_url`, `qr_code_url` → reconstructibles depuis `pio_id`

**Volume** : 16 colonnes au lieu de 23. Plus lisibles, plus directement exportables vers Odoo.

---

## 5. `02_Installations` — Recentrée sur l'essentiel

| Colonne | Rôle | Statut |
|---|---|---|
| `install_id` (PK) | Auto-incrément | 🔒 CRITIQUE |
| `pio_id` (FK → 01) | Le pionnier propriétaire | 🔒 CRITIQUE |
| `produit` | "G30" / "Ocean 500" / etc. (référence à `07_Catalog`) | 🔒 CRITIQUE |
| `numero_serie` | NS (vide tant que pas collecté) | ✅ Enrichi progressivement |
| `date_installation` | Date d'installation | ✅ |
| `date_garantie_fin` | Calculée auto = +24 mois | ✅ |
| `territoire_installation` | Lieu d'installation | ✅ |
| `passeport_url` | URL GitHub Pages | ✅ |
| `photo_generateur_url` | Photo réelle (extraite du PDF) | ✅ |
| `report_id` | Idempotence webhook | 🔒 CRITIQUE |
| `source_creation` | "webhook" / "manuel" / "ns_via_app" | ⚠️ À ajouter (pour tracer comment le NS a été collecté) |

**À retirer** :
- `date_sortie`, `installateur`, `installation_status`, `pionnier_created`, `nom_client`, `gamme`, `contrat_maintenance_type`, `localisation_precise`, `statut_eau`, `derniere_maintenance`, `prochain_entretien`, `installation_active`, `photo_emplacement_url`

**Volume** : 11 colonnes au lieu de 23. Toutes les colonnes ont un sens métier ou technique.

**Évolution NS** :
- Au moment de la livraison : `numero_serie = ""` si non communiqué
- Au moment de la collecte via l'app : un workflow "Saisir mon NS" remplit cette case
- Le passeport et le certificat affichent le NS dès qu'il est disponible

---

## 6. `05_Maintenances` — Simplifiée

| Colonne | Rôle | Statut |
|---|---|---|
| `maintenance_id` (PK) | Auto-incrément | 🔒 CRITIQUE |
| `install_id` (FK → 02) | Le générateur | 🔒 CRITIQUE |
| `pio_id` (FK → 01) | Confort de lookup direct | ✅ Conservé |
| `date_intervention` | Date | ✅ |
| `type_intervention` | LIVRAISON / MAINTENANCE / SAV | ✅ |
| `technicien` | Nom du technicien | ✅ |
| `description` | Synthèse de l'intervention | ⚠️ À ajouter (aujourd'hui dans `observations` qui mélange tout) |
| `statut` | CLOTUREE / A_FAIRE | ✅ |
| `report_id` | Idempotence | ⚠️ À ajouter (actuellement seulement dans 08_Log) |
| `source` | "webhook_sav" / "manuel" | ✅ |

**À retirer** :
- `rapport_url` (jamais utilisé)
- `pieces_changees` (jamais utilisé)
- `prochain_rdv` (jamais utilisé)
- `observations` → renommé en `description` (plus clair)

**Volume** : 10 colonnes au lieu de 12.

---

## 7. Plan orienté métier en 4 phases

### 🟢 PHASE 1 — Fiabiliser l'existant (1-2 jours, risque minimal)

**Objectif** : retirer les pollutions, normaliser, sans casser l'app.

| Action | Bénéfice métier | Validation requise |
|---|---|---|
| 1.1 Supprimer `03_Medias`, `07_Produits` | Sheet plus lisible, moins de risques de confusion | ✅ Vous |
| 1.2 Archiver `00_Fondateurs` + `Import` après extraction | Idem | ✅ Vous |
| 1.3 Renommer statut `"En attente"` → `"Pionnier"` (196 lignes) | Cohérence visuelle | ✅ Vous |
| 1.4 Corriger les 4 `#REF!` dans `02_Installations` | Fin des erreurs visibles | ✅ Vous (arbitrage des 4 lignes) |
| 1.5 Dédoublonner les 3 NS doublons dans `01_Pionniers` | Cohérence | ✅ Vous |
| 1.6 Retirer les structures non-particulières de `01_Pionniers` (5-20 lignes) | Périmètre clean (= règle métier) | ✅ Vous (validation cas par cas) |

**Résultat** : un Sheet propre, fiable, sans dette technique gênante.

---

### 🟡 PHASE 2 — Préparer la collecte NS via l'app (1 semaine)

**Objectif** : permettre aux pionniers d'enrichir leurs propres NS depuis leur espace.

**Fonctionnalité à concevoir** :

1. **Sur l'espace pionnier** (`portail_pionnier.html`) :
   - Ajouter une carte "📷 Saisir le NS de votre générateur"
   - Formulaire simple : un champ texte + photo optionnelle
   - Soumission via `POST /api/pionnier/saisir-ns` (à créer)
   - Affichage différencié si NS déjà renseigné ou non

2. **Workflow backend** :
   - `POST /api/pionnier/saisir-ns` reçoit `{pio_id, install_id, numero_serie, photo_url}`
   - Valide le format (regex HR88… / EA60… / etc.)
   - Vérifie l'unicité (NS pas déjà attribué à un autre install)
   - Update `02_Installations.numero_serie` et `source_creation = "ns_via_app"`
   - Log dans `08_Automations_Log`
   - Régénère le Passeport pour afficher le NS

3. **Côté admin** :
   - Vue `/api/admin/ns-pending` listant les pionniers sans NS
   - Possibilité de relancer par email (envoi groupé)

**Bénéfice métier** :
- Vous récupérez progressivement les NS sans saisie admin manuelle
- Chaque Pionnier devient acteur de la complétion de sa fiche
- Traçabilité automatique de la provenance du NS

---

### 🟡 PHASE 3 — Simplification des colonnes (1-2 jours, après validation)

**Objectif** : retirer les colonnes mortes pour préparer un export Odoo propre.

**Approche prudente** :
1. Pour chaque colonne marquée "à retirer" → vérifier le code `append_row` correspondant
2. Mettre à jour le code si nécessaire (les `append_row` sont positionnels)
3. Supprimer la colonne du sheet en dernier
4. Lancer les tests `/app/backend/tests`

**Volumes** :
- `01_Pionniers` : 23 → 16 colonnes (-30%)
- `02_Installations` : 23 → 11 colonnes (-50%)
- `05_Maintenances` : 12 → 10 colonnes (-15%)

**Bénéfice métier** :
- Sheet beaucoup plus lisible
- Export CSV simple, immédiatement utilisable côté Odoo

---

### 🟣 PHASE 4 — Préparer la migration Odoo (à planifier)

**Objectif** : rendre l'export du Sheet vers Odoo direct.

**Pas d'écriture côté Sheet** — uniquement préparer la sortie.

**Livrables** :

1. **Mapping Sheet → Odoo** :

   | Onglet Sheet | Entité Odoo | Notes |
   |---|---|---|
   | `01_Pionniers` | `res.partner` (catégorie "Pionnier") | Particuliers, is_company=False |
   | `02_Installations` | Modèle custom `geobuilder.installation` | Lié au partner via `partner_id` |
   | `05_Maintenances` | `helpdesk.ticket` ou modèle custom `geobuilder.maintenance` | Lié à l'installation |
   | `07_Catalog` | `product.template` | Catégorie "Générateur" |
   | `08_Automations_Log` | Archive uniquement (CSV) | Pas migré côté Odoo |
   | `06_Documents` | `ir.attachment` ou modèle custom | Lié au partner |

2. **Scripts d'export** :
   - `python3 scripts/export_odoo_pionniers.py` → produit `odoo_partners.csv`
   - `python3 scripts/export_odoo_installations.py` → produit `odoo_installations.csv`
   - `python3 scripts/export_odoo_maintenances.py`

3. **Documentation de migration** :
   - Marche à suivre pour l'import dans Odoo (assistant d'import natif)
   - Mapping des champs (déjà fait ici)
   - Règles de réconciliation (par email pour les partners)

**Quand déclencher la Phase 4 ?** Au moment où vous serez prêt à basculer.

---

## 8. Règles d'exploitation au quotidien (pendant la phase Sheet)

### 8.1 Création d'un nouveau pionnier

**Cas 1 — Nouvelle livraison via app SAV** :
- Webhook `/api/webhook/intervention` (type LIVRAISON) crée automatiquement Pionnier + Installation + Documents
- ✅ Workflow fiable, déjà en place

**Cas 2 — Création manuelle dans le Sheet** :
- ⚠️ Interdit en pratique : si vous ajoutez une ligne manuellement, le compteur `04_Parametres.Valeur Actuelle` n'est pas incrémenté → collision future
- → Si besoin d'une création manuelle, à faire via un futur endpoint admin (`POST /api/admin/create-pionnier`)

### 8.2 Mise à jour d'un Pionnier existant

| Modification | Méthode autorisée |
|---|---|
| Email / téléphone | ✏️ Édition directe dans le Sheet |
| Statut Fondateur | ✏️ Édition directe (sera lu au prochain accès espace pionnier) |
| Statut Ambassadeur | 🔒 **UNIQUEMENT via** `/api/ambassadeur/signature` (signature eIDAS requise) |
| Super Ambassadeur | 🔒 **UNIQUEMENT via** `/api/admin/promote-super` |
| pio_id | ❌ **JAMAIS** (clé primaire — casserait toutes les URLs) |
| nom / prenom | ✏️ Édition directe (mais le passeport doit être régénéré) |
| NS | ✏️ Édition directe OU via futur formulaire app |

### 8.3 Régénération d'un document

- Suppression du fichier sur GitHub Pages = orphelin (lien cassé)
- Régénération propre = re-déclencher le webhook OU appeler un endpoint admin dédié (à créer si besoin : `POST /api/admin/regenerate-pionnier/{pio_id}`)

### 8.4 Suivi de la santé du Sheet

À automatiser (futur tableau de bord admin léger ou commande cron) :

| Indicateur | Seuil d'alerte |
|---|---|
| Pionniers sans email | > 0 |
| Pionniers sans NS | (informatif — collecte en cours) |
| Installations orphelines (pio_id inexistant) | > 0 |
| Pio_id en doublon | > 0 |
| NS en doublon dans `02` | > 0 |
| Cellules `#REF!` | > 0 |

---

## 9. Risques résiduels & garde-fous

| Risque | Probabilité | Garde-fou |
|---|---|---|
| Édition manuelle qui casse l'ordre des colonnes | Moyenne | Documentation interne + test périodique webhook |
| Suppression accidentelle d'un onglet critique | Faible | Permissions Google Sheets restreintes |
| Décalage état app ↔ état Sheet | Moyenne | Snapshot hebdomadaire JSON + script de vérification |
| Saturation quotas API Sheets | Faible | Déjà géré (`@_retry_on_quota`) |
| NS saisi en doublon via app | Moyenne | Validation côté backend (unicité) avant écriture |
| Migration Odoo cassée par changements de schéma | À venir | Geler le schéma une fois Phase 3 terminée |

---

## 10. Récapitulatif visuel — Avant / Après

| Aspect | Avant | Après Phase 1 + 3 |
|---|---|---|
| **Onglets** | 11 | **7** (00, 03, 07_Produits, Import supprimés) |
| **01_Pionniers — lignes** | 197 (150 remplies, dont structures B2B) | **~85-100** (particuliers seuls) |
| **01_Pionniers — colonnes** | 23 | **16** |
| **02_Installations — lignes** | 261 (156 remplies) | **= nb pionniers livrés** (~85-110) |
| **02_Installations — colonnes** | 23 | **11** |
| **NS dans 02** | 81 (mix import) | **progressif via app** |
| **`#REF!`** | 4 | **0** |
| **Statut "En attente"** | 196 lignes | **0** |
| **Onglets morts** | 4 | **0** |

---

## 11. Démarrage proposé

Je suggère d'exécuter la **PHASE 1 (Quick wins, ~1 h)** dès que vous validez :

1. ✅ Suppression `03_Medias` (vide) — 30 sec
2. ✅ Suppression `07_Produits` (doublon) — 30 sec
3. ✅ Renommer statut "En attente" → "Pionnier" (196 lignes) — 1 min
4. ✅ Corriger les 4 `#REF!` (vous arbitrez) — 5 min
5. ✅ Dédoublonner les 3 NS doublons — 1 min
6. ✅ Lister les structures non-particulières dans `01_Pionniers` (rapport pour arbitrage)

Puis **PHASE 2** (collecte NS via app) qui est la vraie valeur ajoutée métier.

**Aucune écriture lancée.** Décidez par où démarrer.
