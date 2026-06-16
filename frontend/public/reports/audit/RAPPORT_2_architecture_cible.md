# RAPPORT 2 — PROPOSITION D'ARCHITECTURE CIBLE

*Aucune modification effectuée. Architecture à valider avant migration.*

---

## Principe

**01_Pionniers** reste la **référence absolue** (clients particuliers).
**Toute autre table dépend de la table parent par clé étrangère**.

Les clients B2B (structures, institutions, collèges, douane, etc.) **n'ont pas leur place dans 01_Pionniers** mais bénéficient d'une table dédiée.

---

## 🎯 Vue d'ensemble cible

```
01_Pionniers          (particuliers — référentiel)
   ├─ 02_Installations  (générateurs liés à un pio_id)
   │     └─ 05_Maintenances  (interventions SAV liées à un install_id)
   │     └─ 06_Documents     (HTML générés liés à install_id + pio_id)
   └─ 03_Ambassadeurs   (signatures eIDAS — historique légal)

09_Clients_B2B        (structures — administrations, entreprises, collèges)
   └─ 02_Installations  (générateurs liés à un client_b2b_id OU un pio_id)

04_Parametres         (compteurs ID + listes de valeurs)
07_Catalog            (catalogue produits dynamique)
08_Automations_Log    (logs/idempotence/eIDAS)
```

---

## 📚 Détail par onglet

### `01_Pionniers` — **CONSERVER + nettoyer**

**Rôle** : Référentiel unique des particuliers (un être humain physique = une ligne).

| Colonne | Type | Source | Note |
|---|---|---|---|
| `pio_id` (PK) | TEXT | Auto-incrément `04_Parametres.Compteurs` | clé primaire |
| `nom` | TEXT MAJUSCULES | Saisie manuelle / Import | convention |
| `prenom` | TEXT CamelCase | Saisie | |
| `email` | TEXT | Saisie | unique recommandé |
| `telephone` | TEXT | Saisie | |
| `pays` | TEXT | `France` par défaut | |
| `territoire` | TEXT | `Mayotte` / `Réunion` / `Comores` / `Madagascar` / `France` | enum |
| `date_entree` | ISO 8601 | Auto à la création | |
| `statut` | enum | `Pionnier` / `Inactif` / `Test` | ⚠️ retirer "En attente" |
| `fondateur` | bool | Manuel admin (max 100) | |
| `ambassadeur` | bool | Mis à `true` via `/api/ambassadeur/signature` | |
| `super_ambassadeur` | bool | **NOUVEAU** — via `/api/admin/promote-super` | |
| `date_signature_ambassadeur` | ISO | Auto | |
| `date_promotion_super` | ISO | Auto | |
| `source_creation` | enum | `backend_livraison` / `import_parc_2026` / `import_csv_sav` / `manuel` | |
| `welcome_email_sent` | bool | true seulement si envoi RÉEL réussi | corrige le bug actuel |
| `commentaire` | TEXT | libre | |

**À RETIRER de 01_Pionniers** :
- `NS` → déplacé vers `02_Installations` (un pionnier peut avoir plusieurs NS)
- `certificat_url`, `carte_url`, `qr_code_url` → déplacés vers `06_Documents`
- `client_type` → toujours "Particulier" donc redondant (les B2B vont dans `09_Clients_B2B`)
- `droit_image`, `temoignage_autorise`, `visite_possible` → déplacés vers `03_Ambassadeurs` (uniquement signés)
- `communaute_statut` → calculé à la volée (fondateur + ambassadeur + super)
- `workflow_status` → déplacé vers `08_Automations_Log`

**Volume cible** : ~80-90 lignes (particuliers réels) + 4-10 cas test isolés.

---

### `02_Installations` — **CONSERVER + restructurer**

**Rôle** : Un générateur physique installé = une ligne. Relation forte à `01_Pionniers` OU `09_Clients_B2B`.

| Colonne | Type | Source | Note |
|---|---|---|---|
| `install_id` (PK) | TEXT | Auto-incrément | |
| `pio_id` (FK nullable) | TEXT | → 01 | NULL si client B2B |
| `client_b2b_id` (FK nullable) | TEXT | → 09 | NULL si particulier |
| `numero_serie` (UK) | TEXT MAJUSCULES | Webhook OU import | unique |
| `produit_id` | TEXT | → 07_Catalog | au lieu de label libre |
| `date_installation` | DATE | | |
| `date_garantie_fin` | DATE | calculé = +2 ans | actuellement vide partout |
| `date_sortie` | DATE nullable | si désinstallé | |
| `territoire_installation` | enum | hérité du client | |
| `installateur` | TEXT | technicien | |
| `localisation_precise` | TEXT | adresse | |
| `installation_status` | enum | `active` / `desinstallee` / `panne` | |
| `passeport_url` | TEXT | GitHub Pages | |
| `photo_generateur_url` | TEXT | URL (extraite du rapport PDF) | |
| `photo_emplacement_url` | TEXT | URL | |
| `report_id` | TEXT | idempotence | |
| `source_creation` | enum | `webhook` / `import_parc_2026` | |

**À RETIRER** :
- `pionnier_created` → redondant
- `nom_client` → lookup via `pio_id`/`client_b2b_id`
- `gamme` → vient de `07_Catalog.gamme` via `produit_id`
- `contrat_maintenance_type` → géré ailleurs (futur)
- `derniere_maintenance` → calculé via `05_Maintenances`
- `prochain_entretien` → calculé
- `statut_eau` → non utilisé
- `installation_active` → redondant avec `installation_status`

**Volume cible** : ~511 lignes (le parc réel complet) sans pré-remplir de lignes vides.

---

### 🆕 `09_Clients_B2B` — **CRÉER**

**Rôle** : Structures (préfecture, collèges, douane, mairies, associations, entreprises…).

| Colonne | Type | Note |
|---|---|---|
| `client_b2b_id` (PK) | TEXT | ex `B2B-0001` |
| `raison_sociale` | TEXT | "PREFECTURE MAYOTTE", "COLLEGE TSINGONI" |
| `siret` | TEXT | optionnel |
| `categorie` | enum | `Administration` / `Education` / `Sante` / `Entreprise` / `Association` |
| `contact_principal_nom` | TEXT | personne référente |
| `contact_principal_email` | TEXT | |
| `contact_principal_telephone` | TEXT | |
| `pays`, `territoire` | TEXT | |
| `adresse` | TEXT | |
| `date_entree` | ISO | |
| `statut` | enum | `Actif` / `Inactif` |
| `commentaire` | TEXT | |

**Volume cible** : ~130 structures du parc complet.

---

### `05_Maintenances` — **CONSERVER + enrichir**

**Rôle** : Historique SAV.

| Colonne | Type | Note |
|---|---|---|
| `maintenance_id` (PK) | TEXT | |
| `install_id` (FK) | → 02 | |
| `pio_id` (FK nullable) | → 01 | NULL si B2B |
| `client_b2b_id` (FK nullable) | → 09 | NULL si particulier |
| `date_intervention` | DATE | |
| `type_intervention` | enum | `LIVRAISON` / `MAINTENANCE_MENSUELLE` / `MAINTENANCE_ANNUELLE` / `SAV` / `36_MOIS` |
| `technicien` | TEXT | |
| `description` | TEXT | |
| `observations` | TEXT | |
| `pieces_changees` | TEXT | |
| `statut` | enum | `CLOTUREE` / `EN_COURS` / `A_FAIRE` / `A_PLANIFIER` |
| `rapport_url` | TEXT | URL du PDF | |
| `report_id` | TEXT | idempotence | |
| `source` | enum | `webhook_sav` / `import_csv_2026` / `manuel` |

---

### `06_Documents` — **CONSERVER + enrichir**

**Rôle** : Index de TOUS les HTML générés (référentiel des URLs publiées).

| Colonne | Type |
|---|---|
| `doc_id` (PK) | |
| `pio_id` ou `client_b2b_id` (FK) | |
| `install_id` (FK nullable) | |
| `type_doc` | enum `PASSEPORT` / `CERTIFICAT_PIONNIER` / `CERTIFICAT_GARANTIE` / `PORTAIL` / `BADGE` / `AMBASSADEUR` / `BADGE_FONDATEUR_LUX` / `BADGE_AMBASSADEUR_LUX` / `ATTESTATION_EIDAS` |
| `date_generation` | ISO |
| `url_doc` | TEXT (URL GitHub Pages) |
| `version` | INT (incrémenté à chaque regen) |
| `html_hash` | SHA-256 du contenu | optionnel |

---

### 🆕 `03_Ambassadeurs` — **CRÉER** (remplace `03_Medias` vide)

**Rôle** : Audit légal des signatures Ambassadeur (eIDAS).

| Colonne | Type |
|---|---|
| `signature_id` (PK) | |
| `pio_id` (FK) | |
| `nom_complet` | TEXT |
| `email_signataire` | TEXT |
| `ip_signataire` | TEXT |
| `user_agent` | TEXT |
| `timestamp_utc` | ISO |
| `payload_hash_sha256` | TEXT |
| `droit_image` | bool |
| `temoignage_autorise` | bool |
| `visite_possible` | bool |
| `super_promote_at` | ISO nullable |
| `super_promote_by` | TEXT nullable |

---

### `04_Parametres` — **CONSERVER**

Compteurs : `pio_id`, `install_id`, `maintenance_id`, **`client_b2b_id`** (nouveau), `signature_id` (nouveau), `doc_id`.

---

### `07_Catalog` — **CONSERVER**

Tel quel. Ajouter colonne `gamme` (`G30`, `Ocean 500`, `Ocean 1000`, etc.).

---

### `07_Produits` — **SUPPRIMER**

Doublon de `07_Catalog`, jamais utilisé par le code.

---

### `08_Automations_Log` — **CONSERVER**

Tel quel. Stocke les events webhook + signatures + opérations admin.

---

### `00_Fondateurs` — **ARCHIVER puis SUPPRIMER**

Onglet de travail temporaire. Une fois la sélection des Fondateurs reportée dans `01_Pionniers.fondateur`, l'onglet peut être archivé (export CSV) puis supprimé.

---

### `Import` — **TRAITER puis SUPPRIMER**

Onglet d'import historique (118 contacts). À analyser pour rapatrier dans `01_Pionniers` ou `09_Clients_B2B`.

---

## 🔐 Clés primaires & étrangères

| Table | PK | FK |
|---|---|---|
| 01_Pionniers | pio_id | — |
| 02_Installations | install_id | pio_id OU client_b2b_id (XOR) |
| 05_Maintenances | maintenance_id | install_id (NOT NULL), pio_id OU client_b2b_id |
| 06_Documents | doc_id | pio_id ou client_b2b_id (au moins un), install_id optionnel |
| 03_Ambassadeurs | signature_id | pio_id |
| 09_Clients_B2B | client_b2b_id | — |
| 07_Catalog | produit_id | — |

**Règle XOR** : une installation appartient soit à un particulier (`pio_id`), soit à une structure (`client_b2b_id`), jamais aux deux.

---

## 📊 Vue conceptuelle

```
                     ┌────────────────┐
                     │  04_Parametres │ (compteurs ID)
                     └────────────────┘
                              │
            ┌─────────────────┼─────────────────┐
            ▼                                   ▼
  ┌──────────────────┐                 ┌──────────────────┐
  │   01_Pionniers   │                 │ 09_Clients_B2B   │
  │   (particuliers) │                 │   (structures)   │
  └──────────────────┘                 └──────────────────┘
            │     │                           │     │
            │     └─► 03_Ambassadeurs         │     │
            │                                 │     │
            └────► 02_Installations ◄─────────┘     │
                          │                         │
                          ├─► 05_Maintenances ◄─────┘
                          │
                          └─► 06_Documents ◄────────────────► 07_Catalog
                                  │
                                  └─► 08_Automations_Log
```

---

## 🎯 Bénéfices attendus

1. **Référence unique des particuliers** dans `01_Pionniers` — pas de pollution B2B
2. **Parc complet** dans `02_Installations` (511 NS visibles, pas 81)
3. **Historique SAV** importé dans `05_Maintenances` (107+ interventions)
4. **Élimination des onglets morts** (03_Medias, 07_Produits)
5. **Lookups rapides** par clés étrangères (pas de fuzzy match nom)
6. **Évolutivité** : ajout d'un client B2B ne pollue plus la table Pionniers
7. **Reporting** : compter facilement les fondateurs, ambassadeurs, super
8. **Pas de redondance** (suppression de `nom_client`, `gamme`, `client_type`)
