# RAPPORT 3 — PLAN DE MIGRATION DÉTAILLÉ

*Aucune écriture exécutée. Chaque étape est documentée pour validation.*

---

## Principe directeur

1. **Rien n'est touché sans validation explicite étape par étape**
2. **Avant chaque écriture en masse → backup JSON intégral**
3. **Chaque étape est réversible** (script de rollback fourni)
4. **Tests unitaires (`/app/backend/tests`)** ne doivent jamais casser après une étape
5. L'application backend reste **opérationnelle** pendant toute la migration

---

## 📅 Phasage en 8 étapes

| # | Étape | Risque | Durée estimée | Bloquant pour la suite |
|---|---|---|---|---|
| 0 | Préparation (snapshots, dry-runs) | 🟢 | 30 min | Oui |
| 1 | Nettoyage administratif (onglets morts) | 🟢 | 15 min | Non |
| 2 | Correction des #REF! et orphelins | 🟡 | 30 min | Oui |
| 3 | Normalisation `01_Pionniers` (statut, casse, dates) | 🟡 | 30 min | Non |
| 4 | Création `09_Clients_B2B` + déplacement structures | 🟡 | 1 h | Oui |
| 5 | Création `03_Ambassadeurs` + migration signatures | 🟢 | 30 min | Non |
| 6 | Import du parc complet dans `02_Installations` | 🔴 | 2 h | Oui |
| 7 | Import historique SAV dans `05_Maintenances` | 🔴 | 1 h | Non |
| 8 | Mise à jour code backend + tests + déploiement | 🟡 | 2 h | — |

**Durée totale estimée** : ~7 h (réparties sur 2-3 jours pour validation utilisateur)

---

## 🟢 Étape 0 — Préparation

**Objectif** : sécuriser avant toute action.

### Actions

1. **Snapshot intégral** : exporter chaque onglet en JSON dans `/app/memory/snapshots/2026-02-XX/`
2. **Geler les écritures backend** : annoncer à l'utilisateur d'éviter de déclencher des webhooks pendant la fenêtre de migration
3. **Activer un mode "audit"** : un flag `MIGRATION_IN_PROGRESS=true` côté backend pour logger en plus grand détail
4. **Lancer la suite de tests** : `pytest /app/backend/tests` → ligne de base 76/76 passing
5. **Vérifier l'accès Sheets/GitHub/Resend** : un script de test

### Validation

- ✅ Snapshots dans `/app/memory/snapshots/...`
- ✅ Tests passent
- ✅ Backups consultables

### Rollback

Rien à rollback (lecture seule).

---

## 🟢 Étape 1 — Nettoyage administratif

**Objectif** : supprimer ce qui pollue.

### Actions

| Action | Onglet/Objet | Validation |
|---|---|---|
| 1.1 Export CSV puis suppression | `03_Medias` (vide) | confirmer onglet vide |
| 1.2 Export CSV puis suppression | `07_Produits` (doublon) | confirmer non utilisé code |
| 1.3 Export CSV puis suppression | `00_Fondateurs` (après extraction des fondateurs) | confirmer données reportées dans 01.fondateur |
| 1.4 Export CSV puis suppression | `Import` (après extraction utile) | confirmer données reportées |

### Validation

- Tests backend : 76/76 ✅
- Frontend : pas d'impact (UI publique sur GitHub Pages)

### Rollback

Recréer les onglets depuis les CSV exportés.

---

## 🟡 Étape 2 — Correction des `#REF!` et orphelins

**Objectif** : retirer les pollutions visibles.

### Cas à traiter

| Type | Compte | Action proposée |
|---|---|---|
| `02_Installations.pio_id = #REF!` | 4 (INST-2109, 2120, 2148, 2149) | Demander à l'utilisateur le bon `pio_id` OU supprimer la ligne si test |
| `02_Installations.pio_id` inexistant dans 01 | 5 | Idem — chercher le bon pio_id |
| `02_Installations` sans `pio_id` | 1 (INST-2152 / SELARL VETO) | Sera traité en étape 4 (B2B) |
| `05_Maintenances.install_id` inexistant | 3 | Demander à l'utilisateur |
| `05_Maintenances.pio_id` inexistant | 1 | Idem |

### Actions

1. Produire un rapport ligne par ligne (`/app/frontend/public/reports/audit/etape2_a_arbitrer.csv`)
2. **Attendre votre arbitrage cas par cas**
3. Appliquer en batch après validation

### Validation

- Aucun `#REF!` restant dans `02_Installations`
- Aucun orphelin
- Tests backend OK

### Rollback

Restaurer les cellules depuis le snapshot.

---

## 🟡 Étape 3 — Normalisation `01_Pionniers`

**Objectif** : cohérence des données existantes.

### Actions

| # | Action | Lignes impactées | Risque |
|---|---|---|---|
| 3.1 | `statut: "En attente"` → `"Pionnier"` | 196 | 🟢 (changement déjà demandé implicitement) |
| 3.2 | `nom` en MAJUSCULES (les 33 DEJA_SEPARE) | 33 | 🟢 |
| 3.3 | Dédoublonner les 3 NS doublons dans 01 | 3 | 🟡 |
| 3.4 | Aligner `02.nom_client` ↔ `01.prenom + 01.nom` (suppression `02.nom_client` à terme) | 76 incohérences | 🟡 (laisser tel quel pour rétrocompatibilité jusqu'à étape 8) |
| 3.5 | Marquer source_creation = `import_2026` pour les imports | ~150 | 🟢 |

### Validation

- 196 lignes affichent désormais `statut: "Pionnier"`
- Diff disponible avant et après
- Tests backend OK

### Rollback

Restaurer depuis snapshot.

---

## 🟡 Étape 4 — Création `09_Clients_B2B` + déplacement

**Objectif** : sortir les structures de `01_Pionniers`.

### Actions

1. **Créer** l'onglet `09_Clients_B2B` avec les colonnes définies (Rapport 2)
2. **Ajouter** `client_b2b_id` au compteur `04_Parametres`
3. **Identifier** dans `01_Pionniers` les lignes qui sont en réalité des structures :
   - `client_type = "Entreprise"` ou `"Administration"` → 5 lignes
   - + 12-15 lignes mal classées (heuristique structure)
4. **Cataloguer** les 130 structures du parc TSV non encore en sheet
5. **Pour chaque structure** :
   - INSERT dans `09_Clients_B2B`
   - DELETE de `01_Pionniers` (si elle y était)
6. **Ajouter** `02_Installations.client_b2b_id` (nullable)
7. **Mettre à jour** les installations affectées : remplacer `pio_id` par `client_b2b_id` quand approprié

### Validation

- `01_Pionniers` = 100% particuliers
- `09_Clients_B2B` = 130-135 structures
- Aucune installation orpheline

### Rollback

Restaurer le snapshot + supprimer l'onglet `09_Clients_B2B`.

---

## 🟢 Étape 5 — Création `03_Ambassadeurs`

**Objectif** : remplacer `03_Medias` vide + audit légal eIDAS.

### Actions

1. **Renommer** `03_Medias` → `03_Ambassadeurs` (puisque vide)
2. **Recréer** les colonnes selon Rapport 2
3. **Migrer** les signatures de `08_Automations_Log` (action=`signature_eidas`) → 1 ligne par signature
4. **Migrer** les flags `droit_image / temoignage_autorise / visite_possible` de `01_Pionniers` vers `03_Ambassadeurs`
5. **Adapter** le code backend (`/api/ambassadeur/signature`) pour écrire dans `03_Ambassadeurs`

### Validation

- 1 ligne `03_Ambassadeurs` par ambassadeur signé
- Tests backend (signature + promote-super) OK

### Rollback

Restaurer snapshot.

---

## 🔴 Étape 6 — Import du parc complet dans `02_Installations`

**Objectif** : passer de 81 NS référencés à 511.

### Source

- TSV `parc_complet_user.tsv` (511 NS, 221 clients, 8 anomalies à corriger)

### Actions

1. **Pré-nettoyage** des typos (rapport 2.3 audit) :
   - `H88C22KFR0402` → demander à l'utilisateur si c'est `HR88C22KFR0402` ou doublon `HR88C22KFR0415`
   - `HR888C23GFR0283` → `HR88C23GFR0283`
   - `HR88C23GR0301/302/403` → `HR88C23GFR0301/302/403`
   - `EA60L23FR0066S/0080S` → ajouter la lettre manquante
2. **Pour chaque NS du TSV** :
   - Si déjà dans `02_Installations` → SKIP (laisser tel quel)
   - Si client = particulier → match par nom dans `01_Pionniers` → créer install avec `pio_id`
   - Si client = structure → match dans `09_Clients_B2B` → créer install avec `client_b2b_id`
   - Si pas de match → créer install + créer particulier OU structure (selon classification)
3. **Idempotence** : utiliser `numero_serie` comme clé d'unicité
4. **Champs minimum** :
   - `install_id` (auto)
   - `numero_serie`
   - `pio_id` OU `client_b2b_id`
   - `produit_id` (déduit du préfixe NS via mapping)
   - `source_creation = "import_parc_2026"`
   - Reste : vide ou valeur par défaut

### Validation

- `02_Installations` = 511 lignes remplies (vs 156 aujourd'hui)
- Aucun doublon de NS
- Tests backend OK

### Rollback

Supprimer toutes les lignes avec `source_creation = "import_parc_2026"`.

---

## 🔴 Étape 7 — Import historique SAV dans `05_Maintenances`

**Objectif** : récupérer les 107 interventions historiques.

### Sources

- `FINAL.csv` (107 interventions) — réduit à 91 du Lot A après votre filtrage
- `pionniers_final_propre.csv` (votre version validée)

### Actions

1. **Pour chaque intervention du Lot A** :
   - Récupérer `install_id` via `NS` (étape 6 fournit le lookup)
   - Récupérer `pio_id`/`client_b2b_id` via l'installation
   - Construire `maintenance_id` (auto)
   - `report_id = "IMPORT-{NS}-{date}"` (idempotence)
   - `source = "import_csv_2026"`
2. **Skip** les interventions du Lot B (à arbitrer manuellement)
3. **Skip** les lignes avec `date_intervention` non-date (`"relancer"`, `"juin"`, etc.) ou les flagger en `statut = "A_PLANIFIER"`

### Validation

- `05_Maintenances` enrichi avec les 91 lignes Lot A
- Idempotence : ré-exécution n'écrit pas les mêmes lignes 2 fois
- Tests backend OK

### Rollback

Supprimer toutes les lignes avec `source = "import_csv_2026"`.

---

## 🟡 Étape 8 — Mise à jour code backend + tests + déploiement

**Objectif** : aligner le code avec la nouvelle structure.

### Modifications code

| Fichier | Changements |
|---|---|
| `services/sheets_service.py` | Ajouter helpers `read_b2b_clients`, `append_b2b`, `append_ambassadeur_signature` |
| `server.py` (webhook livraison) | Détecter type client (particulier/B2B), router vers 01 ou 09 |
| `server.py` (webhook SAV) | Lookup NS → install_id même si B2B |
| `server.py` (signature ambassadeur) | Écrire dans `03_Ambassadeurs` |
| `services/counter_service.py` | Ajouter compteur `client_b2b_id` et `signature_id` |
| Backend tests | Mettre à jour fixtures pour nouvelle structure |

### Refactor optionnel (peut être différé)

- Découper `server.py` (1700 lignes) en :
  - `/app/backend/routes/webhooks.py`
  - `/app/backend/routes/ambassadeur.py`
  - `/app/backend/routes/admin.py`
  - `/app/backend/services/document_generator.py`

### Validation

- 76+ tests passing
- Webhook LIVRAISON test avec un particulier → 01_Pionniers
- Webhook LIVRAISON test avec une structure → 09_Clients_B2B
- Webhook SAV test → lookup OK avec un NS B2B et un NS particulier
- Signature ambassadeur → écrit dans 03_Ambassadeurs

### Rollback

- Revert git commit
- Restaurer Sheets snapshot
- Redéployer ancienne version

---

## 🛡️ Sécurité globale

### Avant chaque étape

```bash
python3 /app/backend/scripts/snapshot_sheets.py  # export JSON intégral
git tag pre-migration-step-X
git push --tags
```

### Après chaque étape

```bash
pytest /app/backend/tests -v
python3 /app/backend/scripts/validate_relations.py  # vérifie FK
curl test webhook → check sheet state
```

### Communications

- **Avant chaque étape avec impact** → ask_human pour validation
- **Après chaque étape** → rapport de delta (avant/après)

---

## 📂 Livrables techniques de la migration

À produire au fur et à mesure (dossier `/app/frontend/public/reports/migration/`) :

| Fichier | Quand |
|---|---|
| `step0_snapshot.json` | Avant tout |
| `step1_archive_*.csv` | Avant suppression onglets morts |
| `step2_orphans_to_arbitrate.csv` | Avant étape 2 |
| `step3_normalize_diff.csv` | Étape 3 |
| `step4_b2b_creation_plan.csv` | Étape 4 |
| `step6_parc_import_plan.csv` | Étape 6 |
| `step7_sav_import_plan.csv` | Étape 7 |
| `step8_code_diff.md` | Étape 8 |
| `MIGRATION_COMPLETE.md` | À la fin |

---

## ⏱️ Calendrier proposé (à ajuster)

| Jour | Étapes | Action utilisateur |
|---|---|---|
| J | 0 + 1 | Validation préliminaire |
| J+1 | 2 + 3 | Arbitrage des orphelins, validation normalisation |
| J+2 | 4 | Validation classification B2B/Particulier |
| J+3 | 5 + 6 | Validation import parc complet |
| J+4 | 7 + 8 | Validation import SAV + déploiement code |

**Au total** : ~5 jours ouvrables avec votre validation entre chaque étape.
