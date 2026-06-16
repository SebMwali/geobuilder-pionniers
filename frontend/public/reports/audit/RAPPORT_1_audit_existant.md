# RAPPORT 1 — AUDIT COMPLET DE L'EXISTANT
*Lecture seule. Aucune modification effectuée.*

---

## 1. Cartographie des 11 onglets

| Onglet | Lignes brutes | Lignes remplies | Colonnes | Rôle réel | État |
|---|---|---|---|---|---|
| **00_Fondateurs** | 138 | 138 | 12 | Liste manuelle de noms (références historiques) | ⚠️ **10/12 colonnes vides** — onglet de travail temporaire |
| **01_Pionniers** | 197 | 150 | 23 | Référentiel des clients particuliers | ⚠️ 47 lignes brutes vides |
| **02_Installations** | 261 | 156 | 23 | Référentiel des générateurs installés | ⚠️ 105 lignes pré-créées vides + 4 `#REF!` |
| **03_Medias** | 0 | 0 | 5 | Photos/témoignages clients | 🔴 **VIDE — jamais utilisé** |
| **04_Parametres** | 15 | 15 | 7 | Compteurs ID + listes de valeurs | ✅ Utilisé pour `pio_id`/`install_id` |
| **05_Maintenances** | 126 | 126 | 12 | Historique SAV | ⚠️ 75% des champs `date`/`technicien`/`statut` vides |
| **06_Documents** | 5 | 5 | 10 | Index des HTML générés | ⚠️ Quasi vide — uniquement 1 pionnier de test |
| **07_Produits** | 7 | 7 | 9 | Catalogue produits (ancienne version) | 🔴 **DOUBLON de 07_Catalog — non utilisé par le code** |
| **07_Catalog** | 9 | 9 | 8 | Catalogue produits (nouvelle version) | ✅ Utilisé par le backend |
| **08_Automations_Log** | 7 | 7 | 7 | Logs idempotence webhooks | ✅ Utilisé |
| **Import** | 118 | 118 | 7 | Import historique 118 noms/emails/tél | 🔴 **Jamais rapatrié dans 01_Pionniers** |

---

## 2. Détail des champs de **01_Pionniers** (référence)

| Colonne | Taux remplissage | Observation |
|---|---|---|
| pio_id | 76% (150/197) | ✅ OK pour les remplies |
| NS | **45% (88/197)** | 🟡 Vient du remplissage récent (limité aux installations avec NS) |
| nom | 76% | ✅ |
| prenom | 54% | 🟡 Sociétés/structures sans prénom (normal) |
| email | 75% | ✅ |
| telephone | 74% | ✅ |
| pays | 65% | 🟡 35% sans pays |
| **territoire** | **0.5%** | 🔴 **Quasi vide** — 1 seule ligne renseignée |
| client_type | 100% (191 Particulier / 3 Entreprise / 2 Administration) | ✅ |
| **date_entree** | **0.5%** | 🔴 **Quasi vide** — historique perdu |
| statut | 100% | ⚠️ **196 "En attente" + 1 "Pionnier"** — incohérent, tous devraient être "Pionnier" |
| fondateur | 100% (67 true) | 🟡 67 fondateurs déclarés — à valider |
| ambassadeur | 100% (1 true) | ✅ |
| communaute_statut | 0.5% | 🔴 |
| droit_image / temoignage / visite | 100% | ✅ |
| source_creation | 99.5% | ✅ |
| workflow_status | 0.5% | 🔴 |
| welcome_email_sent | 100% | ✅ |
| certificat_url / carte_url | 0.5% | 🔴 |
| qr_code_url | 0% | 🔴 Jamais utilisé |

---

## 3. Onglets utilisés par le code backend

Vérification grep sur `/app/backend/` :

| Onglet | Lecture | Écriture | Usage |
|---|---|---|---|
| 01_Pionniers | ✅ `read_all("pionniers")` | ✅ `append_row` + `update_cell` | webhook livraison, ambassadeur, promote-super |
| 02_Installations | ✅ | ✅ `append_row` | webhook livraison |
| 05_Maintenances | ✅ | ✅ `append_row` | webhook SAV |
| 06_Documents | — | ✅ `append_row` | webhook livraison |
| 04_Parametres | — | ✅ `update_cell` | counter_service (incrémentation pio_id/install_id) |
| 07_Catalog | ✅ `read_all("catalog")` | — | catalog.py (5 min cache) |
| 08_Automations_Log | — | ✅ `append_row` | sheets_service.log_event |
| **07_Produits** | ❌ | ❌ | 🔴 **Jamais lu/écrit par le code → mort** |
| **03_Medias** | ❌ | ❌ | 🔴 **Jamais utilisé → mort** |
| **00_Fondateurs** | ❌ | ❌ | 🔴 Onglet de travail temporaire — pas dans le code |
| **Import** | ❌ | ❌ | 🔴 Import externe jamais consommé |

---

## 4. Relations entre onglets — Orphelins & doublons

### 4.1 Orphelins

| Anomalie | Compte | Détail |
|---|---|---|
| Pionniers sans aucune installation | **2** | PIO-1038 (Ahamadi Harouna) + 1 autre |
| Installations avec `pio_id` inexistant dans 01 | **5** | Probablement les 4 `#REF!` + 1 autre |
| Installations sans `pio_id` | **1** | INST-2152 (SELARL VETO) |
| **NS dans 01_Pionniers absents de 02_Installations** | **15** | Ex : `HR88C22KFR0405` (PIO-1145), `HR88C23JFR0763` (PIO-1139) |
| Maintenances avec `install_id` inexistant | **3** | À investiguer |
| Maintenances avec `pio_id` inexistant | **1** | À investiguer |
| Documents avec `pio_id` inexistant | 0 | ✅ |

### 4.2 Doublons

| Anomalie | Compte | Détail |
|---|---|---|
| `pio_id` doublon dans 01_Pionniers | 0 | ✅ |
| `NS` doublon dans 02_Installations | 0 | ✅ |
| **`NS` doublon dans 01_Pionniers** | **3** | `HR88C23EFR0120`, `HR88C23JFR0849`, `HR88C23LFR1131` (probablement issus du remplissage récent — à investiguer) |
| Emails doublon dans 01_Pionniers | 0 | ✅ |

### 4.3 Incohérences

| Anomalie | Compte | Sévérité |
|---|---|---|
| `nom_client` 02 ≠ `prenom+nom` 01 | **76** | 🟡 La plupart sont juste l'ordre inversé (ex `TOYFA MATTOIR` vs `MATTOIR TOYFA`) |
| **Cellules `#REF!`** dans `02_Installations.pio_id` | **4** | 🔴 INST-2109, INST-2120, INST-2148, INST-2149 |
| **Statut "En attente"** pour 196/197 pionniers | **196** | 🔴 Tous devraient être "Pionnier" |

---

## 5. Numéros de série (NS) — analyse complète

| Source | NS uniques | Couverture |
|---|---|---|
| **Parc réel utilisateur** *(TSV fourni)* | **511** | référence absolue |
| 02_Installations (sheet) | 81 | **16%** du parc |
| 01_Pionniers (colonne NS) | 88 | 17% du parc |
| 05_Maintenances | 0 (pas de colonne NS, lié via install_id) | — |
| CSV `FINAL.csv` (107 interventions historiques) | 67 | 13% du parc |
| CSV `NON_RESOLU.csv` | 49 | 10% du parc |
| `pionniers_final_propre.csv` (votre version validée) | 79 | 15% du parc |

**Conclusion** : le sheet ne référence aujourd'hui que **~16% du parc réel**.

### NS à risque

- **4 NS au format suspect** : `H88C22KFR0402` (R manquant), `HR888C23GFR0283` (R en trop), `HR88C23GR0301/302/403` (F manquant), `EA60L23FR0066S/0080S` (lettre manquante)
- **3 NS en doublon** dans 01_Pionniers (remplissage récent erroné)

---

## 6. Historique SAV — disponibilité

| Source | Contenu | État |
|---|---|---|
| 05_Maintenances (sheet) | 126 lignes | ⚠️ 100% via API webhook, ne contient PAS l'historique avant migration |
| `FINAL.csv` (app SAV externe) | 107 interventions sur 67 NS | 🔴 **Jamais importé dans 05_Maintenances** |
| `NON_RESOLU.csv` | 49 NS sans intervention | informationnel |

**Tous les onglets de maintenance historique sont actuellement déconnectés de Geobuilder.**

---

## 7. Compatibilité code ↔ structure du Sheet

### Champs utilisés par le backend

| Endpoint | Onglet | Champs lus/écrits | Risque |
|---|---|---|---|
| `POST /api/webhook/intervention` (LIVRAISON) | 01,02,06,07_Catalog | Tous champs métier | ⚠️ Suppose colonnes A→W exactes dans l'ordre |
| `POST /api/webhook/intervention` (SAV) | 02 (lookup NS→pio_id), 05, 08 | `numero_serie`, `install_id`, `pio_id` | ⚠️ Échoue si NS pas dans 02 |
| `POST /api/ambassadeur/signature` | 01 (update `ambassadeur`) | + signature dans 08_Automations_Log | ✅ |
| `POST /api/admin/promote-super` | 01 (update `communaute_statut`) | + log | ✅ |
| `POST /api/admin/reload-catalog` | 07_Catalog (read) | — | ✅ |

### Risques actuels

1. **L'ordre des colonnes** est figé dans le code (`append_row` avec liste positionnelle). Si une colonne est ajoutée/déplacée dans le sheet, le code casse silencieusement.
2. **Le champ `statut`** est forcé à `"Pionnier"` à l'insertion mais les 196 lignes existantes sont en `"En attente"` — incohérence visible côté UI.
3. **Le champ `welcome_email_sent`** est toujours mis à `"true"` mais aucun pionnier importé n'a réellement reçu l'email → faux positif.
4. **Aucune validation de format NS** côté code → accepte typos.

---

## 8. Compatibilité avec la logique métier

### Workflow normal Pionnier

```
LIVRAISON webhook
  ↓
01_Pionniers : INSERT (pio_id auto)
02_Installations : INSERT (install_id auto + NS)
06_Documents : INSERT 4-5 lignes (Passeport/Cert/Garantie/Portail/Ambassadeur)
GitHub Pages : push 4-5 HTML
Email : send via Resend
```

### Workflow Ambassadeur

```
POST /ambassadeur/signature (eIDAS)
  ↓
01_Pionniers : UPDATE ambassadeur=true + communaute_statut
GitHub Pages : régénération passeport (badge grid)
08_Automations_Log : APPEND signature_eidas
```

### Workflow SAV

```
SAV webhook (numero_serie OU install_id)
  ↓
02 lookup (NS → install_id, pio_id)
05_Maintenances : INSERT
08_Automations_Log : APPEND (idempotence report_id)
```

### Workflows MANQUANTS pour réconciliation parc réel

🔴 **Aucun mécanisme pour** :
- Importer en masse l'historique (107 interventions FINAL.csv)
- Importer en masse les 511 NS du parc réel
- Distinguer particuliers / B2B (140 structures dans le parc)
- Marquer un pionnier comme "Fondateur" depuis l'admin sans webhook
- Gérer les NS multi-générateurs pour un même client

---

## 9. Synthèse de l'existant

### Forces

- Architecture backend solide, idempotence webhooks, retry quota, eIDAS, badges, GitHub Pages OK
- 01_Pionniers est **structurellement la bonne référence**
- 07_Catalog dynamique → catalogue produits maintenable

### Faiblesses critiques

1. 🔴 **84% du parc** n'est pas dans `02_Installations`
2. 🔴 **107 interventions historiques** non importées dans 05_Maintenances
3. 🔴 **2 onglets morts** (03_Medias, 07_Produits) + 2 onglets non-rapatriés (00_Fondateurs, Import)
4. 🟡 **15 NS** dans 01_Pionniers absents de 02_Installations (incohérence)
5. 🟡 **76 incohérences de nom** entre 01 et 02 (souvent juste ordre inversé)
6. 🔴 **4 `#REF!`** dans 02_Installations.pio_id
7. 🟡 **140 structures B2B** dans le parc absentes du sheet (pas leur place dans 01_Pionniers selon votre règle)
8. 🟡 **3 NS doublons** récents dans 01_Pionniers (remplissage v1)
9. 🔴 **Statut `En attente`** sur 196/197 lignes (devrait être `Pionnier`)
10. 🟡 **Pas de date_entree** sur 99.5% des pionniers

---

📁 Fichiers détail :
- `01_cartographie.json` — toutes les colonnes par onglet
- `02_relations.json` — orphelins, doublons, incohérences
