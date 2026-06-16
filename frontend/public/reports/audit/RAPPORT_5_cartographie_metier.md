# RAPPORT 5 — CARTOGRAPHIE MÉTIER (PRÉ-MIGRATION)

*Lecture seule. Aucune modification effectuée.*
*Cartographie complète : chaque onglet, chaque colonne, chaque statut — usage, dépendances, impact de suppression.*

---

## Méthodologie

- Analyse **statique** du code (`grep` sur `/app/backend/`) : tous les fichiers `.py` et `.html`
- **3 niveaux** d'usage détectés :
  - 🟢 **Lecture par le code** (`r.get('col')`)
  - 🔵 **Écriture par le code** (`append_row`, `update_cell`)
  - 🟣 **Variable de template** (`{{COL_UPPER}}` dans un HTML)
- **Distinction "écriture positionnelle"** : `append_row` écrit toutes les colonnes d'une ligne dans l'ordre — donc même les colonnes non lues sont remplies à la création. Elles sont quand même **réservées par le code**.

---

# 📑 ONGLET PAR ONGLET

## 🟦 `00_Fondateurs` — Onglet de travail temporaire

**Rôle métier** : Liste manuelle des 137 noms historiques pour identifier les "100 vrais fondateurs" parmi les pionniers.

**Utilisateur** : Sébastien (vous) — manuel uniquement
**Code** : ❌ Non lu, non écrit par le backend
**App** : Aucune fonctionnalité ne s'appuie dessus

| Colonne | Rôle métier | Code | Conséquence suppression |
|---|---|---|---|
| `ordre` | Numéro de classement chronologique | ❌ | Aucune |
| (col 1) | Nom complet brut | ❌ | Perte du travail manuel |
| `prenom` | Prénom (33 remplis) | ❌ | Aucune |
| `raison_sociale`, `ville`, `territoire`, `email`, `telephone`, `date_installation_estimee`, `commentaire`, `pio_id_propose`, `match_status` | Tous vides | ❌ | Aucune |

**Conséquence suppression de l'onglet** :
- ✅ Backend : 0 impact
- ✅ App : 0 impact
- ⚠️ Métier : il faudra avoir reporté les vrais fondateurs dans `01_Pionniers.fondateur=true` avant suppression. Actuellement **67 lignes** sont déjà marquées `fondateur=true` dans `01_Pionniers`.

---

## 🟦 `01_Pionniers` — RÉFÉRENTIEL PARTICULIERS (cœur du système)

**Rôle métier** : Source de vérité absolue des particuliers ayant reçu un générateur.
**Utilisateur** : Backend (lecture/écriture), tous les HTML générés (lecture via variables `{{PIO_ID}}`, `{{PRENOM}}`, etc.)

### Détail des 23 colonnes

| Colonne | Rôle métier | Usage code | Lieu | Conséquence suppression |
|---|---|---|---|---|
| **pio_id** | Clé primaire — identifiant unique du pionnier | 🟢🔵🟣 (11 fichiers) | `server.py`, tous templates, URLs GitHub Pages (`/pionniers/{pio_id}/`) | ⛔ **CASSE TOUT** : impossible de retrouver un pionnier, de générer son passeport, son certificat, son URL, sa carte, son badge |
| **NS** | Numéro de série du générateur (1+) | ❌ Non lu directement | Aucun | 🟢 Aucune (info redondante avec `02_Installations.numero_serie`) → **suppressible** après migration |
| **nom** | Nom de famille | 🟢🟣 | `server.py` (concat avec prenom pour `NOM_COMPLET`), `templates/ambassadeur.html` | ⛔ Le passeport, l'attestation eIDAS, l'email de bienvenue affichent le nom |
| **prenom** | Prénom | 🟢🟣 (3 fichiers) | `server.py`, `portail_pionnier.html` ({{PRENOM}}) | ⛔ Affiché sur espace pionnier "Bonjour {{PRENOM}}" |
| **email** | Adresse de contact (envoi welcome) | 🟢🟣 (3 fichiers) | `server.py` (envoi Resend), `attestation_ambassadeur.html` | ⛔ Sans email, pas d'envoi de bienvenue ni d'attestation |
| **telephone** | Numéro de téléphone | ❌ Non lu | — | 🟢 Aucune — purement informationnel |
| **pays** | France/Mayotte/etc. | 🟢🟣 (4 fichiers) | Certificats garantie/pionnier (affichage) | 🟡 Les certificats afficheraient "—" sans cette info |
| **territoire** | Mayotte/Réunion/Comores/etc. | 🟢🟣 (5 fichiers) | Attestation ambassadeur, badge, certificats | 🟡 Quasi vide (0.5%) — déjà sans impact actuel |
| **client_type** | "Particulier" / "Entreprise" / "Administration" | ❌ Non lu | — | 🟢 Aucune (redondant — règle métier dit "01 = Particulier uniquement") |
| **date_entree** | Date d'entrée dans la communauté | ❌ Non lu | — | 🟢 Aucune (déjà vide à 99.5%) |
| **statut** | "Pionnier" / "En attente" | 🟢 (1 fichier) | `server.py` (filtrage admin) | 🟡 Pas de logique métier dépendante |
| **fondateur** | true/false | 🟢 (1 fichier) | `server.py` (workflow Ambassadeur) | 🔴 Détermine la **génération du Passeport Fondateur** et le badge "Fondateur" |
| **ambassadeur** | true/false | 🟢 (1 fichier) | `server.py` (workflow `/api/ambassadeur/signature`) | 🔴 Détermine le **déverrouillage de la carte Ambassadeur** sur l'espace pionnier |
| **communaute_statut** | "super_ambassadeur" | 🟢 (1 fichier) | `server.py` (workflow `/api/admin/promote-super`) | 🔴 Détermine **déverrouillage de la carte Super Ambassadeur** |
| **droit_image** | true/false | 🟢🟣 (2 fichiers) | `server.py`, formulaire ambassadeur HTML | 🟡 Stocké pour conformité légale |
| **temoignage_autorise** | true/false | 🟢🟣 (2 fichiers) | Idem | 🟡 Idem |
| **visite_possible** | true/false | ❌ Non lu | — | 🟢 Stockage uniquement, pas utilisé |
| **source_creation** | "backend_livraison" / "Import" | ❌ Non lu | — | 🟢 Traçabilité uniquement |
| **workflow_status** | (vide) | ❌ | — | 🟢 Inutilisé |
| **welcome_email_sent** | true/false | ❌ Non lu | — | 🟡 Toujours "true" actuellement (bug : faux positif sur les imports) |
| **certificat_url** | URL du certificat sur GitHub Pages | ❌ Non lu | — | 🟢 Reconstruit dynamiquement à partir de `pio_id` |
| **carte_url** | URL de la carte Pionnier | ❌ Non lu | — | 🟢 Idem |
| **qr_code_url** | URL QR code | ❌ Non lu | — | 🟢 Totalement vide, mort |

### 🎯 Fonctionnalités de l'app qui dépendent de `01_Pionniers`

| Fonctionnalité | Colonnes requises |
|---|---|
| Création pionnier (webhook LIVRAISON) | `pio_id`, `nom`, `prenom`, `email`, `pays`, `territoire` |
| Envoi email bienvenue | `email`, `prenom`, `nom`, `pio_id` |
| Génération Passeport | `pio_id`, `prenom`, `nom`, `fondateur`, `ambassadeur`, `communaute_statut` |
| Génération Certificat Pionnier | `pio_id`, `prenom`, `nom`, `pays` |
| Génération Carte Pionnier | `pio_id`, `prenom`, `nom`, `territoire` |
| Espace Pionnier (portail) | `pio_id`, `prenom`, `nom`, `ambassadeur`, `communaute_statut` |
| Formulaire Ambassadeur | `pio_id`, `nom`, `prenom`, `email`, `droit_image`, `temoignage_autorise` |
| Badge Ambassadeur / Super | `pio_id`, `prenom`, `nom`, `territoire`, `ambassadeur`, `communaute_statut` |
| Attestation eIDAS | `pio_id`, `nom`, `prenom`, `email`, `territoire`, `droit_image`, `temoignage_autorise` |
| Promote Super (admin) | `pio_id`, `communaute_statut` |

---

## 🟦 `02_Installations` — RÉFÉRENTIEL GÉNÉRATEURS

**Rôle métier** : Un générateur physique = une ligne. Relation N:1 vers `01_Pionniers`.

| Colonne | Rôle métier | Usage code | Lieu | Conséquence suppression |
|---|---|---|---|---|
| **install_id** | Clé primaire | 🟢🔵🟣 (3 fichiers) | URL passeport `/passeports/{install_id}/`, certificat garantie | ⛔ **CASSE** : pas de passeport, pas de certificat garantie, pas de lookup SAV |
| **pio_id** | Clé étrangère vers 01 | 🟢🔵🟣 (11 fichiers) | Tous les workflows | ⛔ Sans ce lien, impossible de générer les docs pour le bon pionnier |
| **produit** | Identifiant produit (G30, etc.) | 🟢🟣 (3 fichiers) | `server.py`, `pdf_extractor.py`, certificat garantie | 🔴 Sans, pas de catalogue lookup, pas de garantie spécifique |
| **numero_serie** | NS du générateur | 🟢🔵🟣 (3 fichiers) | webhook SAV (lookup), passeport, espace pionnier | ⛔ Sans NS, le webhook SAV ne sait plus retrouver l'install ; le passeport l'affiche |
| **date_installation** | Date d'installation | 🟢🟣 (2 fichiers) | Certificat garantie, calcul garantie+2ans | 🔴 Sans, pas de date affichée, pas de calcul de fin de garantie |
| **date_sortie** | Date de désinstallation | ❌ Non lu | — | 🟢 (totalement vide aujourd'hui) |
| **territoire_installation** | Pour adapter le passeport/badge | 🟢 (1 fichier) | `server.py` (mapping territoire) | 🟡 Fallback sur `01.territoire` |
| **installateur** | Nom du technicien | ❌ Non lu | — | 🟢 Stockage uniquement |
| **installation_status** | "active" / "desinstallee" / etc. | ❌ Non lu (sauf comme valeur par défaut) | — | 🟢 Stockage uniquement |
| **pionnier_created** | bool (a-t-on créé le pionnier ?) | ❌ Non lu | — | 🟢 Flag interne historique |
| **nom_client** | Nom redondant pour debug visuel | 🟢 (1 fichier) | `server.py` (debug uniquement) | 🟢 Redondant avec 01_Pionniers — **suppressible** après migration |
| **gamme** | Gamme produit (G30/G60/etc.) | ❌ Non lu | — | 🟢 Redondant avec `07_Catalog.gamme` via `produit_id` |
| **contrat_maintenance_type** | "Annuel" / etc. | ❌ Non lu | — | 🟢 Stockage uniquement |
| **date_garantie_fin** | Date fin garantie | 🟢🟣 (2 fichiers) | Espace pionnier, certificat garantie | 🔴 Sans, pas de date affichée. Mais calculable depuis `date_installation` + `07_Catalog.garantie_mois` |
| **localisation_precise** | Adresse texte | 🟢 (1 fichier) | server.py (cert garantie) | 🟡 Affichage uniquement |
| **statut_eau** | (legacy) | ❌ Non lu | — | 🟢 Mort |
| **derniere_maintenance** | Date dernière maintenance | ❌ Non lu | — | 🟢 Calculable via `05_Maintenances` |
| **prochain_entretien** | Date prochain entretien | 🟢 (1 fichier) | server.py (calcul) | 🟡 Calculé à chaque livraison |
| **passeport_url** | URL Passeport GitHub Pages | 🟢 (1 fichier) | server.py (référence) | 🟡 Reconstructible depuis `install_id` |
| **installation_active** | bool | ❌ Non lu | — | 🟢 Redondant avec `installation_status` |
| **photo_generateur_url** | URL Cloudinary | 🟢 (2 fichiers) | `server.py`, `catalog.py` (fallback) | 🟡 Sans, photo G30 par défaut |
| **photo_emplacement_url** | URL Cloudinary | 🟢 (1 fichier) | server.py | 🟢 Optionnel |
| **report_id** | Idempotence webhook | 🟢 (1 fichier) | server.py | 🔴 Empêche les doubles enregistrements |

### 🎯 Fonctionnalités de l'app qui dépendent de `02_Installations`

| Fonctionnalité | Colonnes requises |
|---|---|
| Webhook LIVRAISON | Toutes (insert d'une nouvelle ligne) |
| Webhook SAV (lookup NS → install) | `numero_serie`, `install_id`, `pio_id` |
| Génération Passeport | `install_id`, `pio_id`, `numero_serie`, `date_installation`, `produit`, `photo_generateur_url`, `territoire_installation` |
| Génération Certificat Garantie | `install_id`, `pio_id`, `produit`, `date_installation`, `date_garantie_fin`, `localisation_precise` |
| Espace Pionnier (carte "Mon installation") | `install_id`, `numero_serie`, `date_installation`, `date_garantie_fin`, `produit`, `photo_generateur_url` |
| Régénération passeport (après promote super) | `install_id`, `pio_id`, `numero_serie`, `produit`, `photo_generateur_url` |

---

## 🟦 `03_Medias` — VIDE

**Rôle métier déclaré** : Photos / témoignages clients
**Réalité** : Aucune ligne, jamais utilisé
**Code** : ❌ Aucune lecture/écriture
**Conséquence suppression** : 🟢 0 impact

---

## 🟦 `04_Parametres` — COMPTEURS & ÉNUMÉRATIONS

**Rôle métier** : Compteurs auto-incrémentaux (`pio_id`, `install_id`, etc.) + listes de valeurs (produits, statuts).

| Colonne | Usage |
|---|---|
| `Produits` | Énumération (lecture humaine) |
| `Client Types` | Énumération |
| `Statuts Pionnier` | Énumération |
| `Statuts Installation` | Énumération |
| `Statuts Media` | Énumération |
| **`Compteurs`** | Liste des compteurs (pio_id, install_id, maintenance_id, doc_id) |
| **`Valeur Actuelle`** | Valeurs courantes des compteurs (incrémentées par `counter_service.py`) |

**Code** : 🔵 `counter_service.py` lit `Compteurs` et écrit dans `Valeur Actuelle`
**Conséquence suppression** : ⛔ **CASSE LE BACKEND** : impossible d'attribuer de nouveaux IDs

---

## 🟦 `05_Maintenances` — HISTORIQUE SAV

**Rôle métier** : Une intervention SAV ou maintenance = une ligne

| Colonne | Rôle | Usage code | Conséquence suppression |
|---|---|---|---|
| **maintenance_id** | PK | 🟢🔵 (1 fichier) | ⛔ Sans, impossible d'identifier une intervention |
| **install_id** | FK → 02 | 🟢🔵 (3 fichiers) | ⛔ Sans, impossible de relier l'intervention à un générateur |
| **pio_id** | FK → 01 | 🟢🔵 (11 fichiers) | 🔴 Redondant avec install_id mais utilisé pour log |
| **date_intervention** | Date | 🟢 (1 fichier) | 🟡 Affichage |
| **type_intervention** | LIVRAISON/MAINTENANCE/SAV | 🟢 (1 fichier) | 🟡 Filtrage |
| **technicien** | Bacar/Assani/etc. | 🟢 (2 fichiers) | 🟢 Affichage |
| **statut** | CLOTUREE / A_FAIRE / etc. | 🟢 (1 fichier) | 🟡 Filtrage |
| **rapport_url** | URL PDF | ❌ Non lu | 🟢 Stockage uniquement |
| **observations** | Texte libre | 🟢 (1 fichier) | 🟢 Affichage |
| **pieces_changees** | Texte | ❌ Non lu | 🟢 Stockage |
| **prochain_rdv** | Date | ❌ Non lu | 🟢 Stockage |
| **source** | "webhook_sav" / "import_csv" | ❌ Non lu | 🟢 Traçabilité |

### Fonctionnalités dépendantes

| Fonctionnalité | Colonnes requises |
|---|---|
| Webhook SAV (insert) | Toutes (positionnelles) |
| Idempotence webhook | `report_id` (présent dans `08_Automations_Log`, **pas ici**) |
| Affichage historique (futur) | `install_id`, `date_intervention`, `type_intervention`, `technicien`, `observations` |

---

## 🟦 `06_Documents` — INDEX HTML GÉNÉRÉS

**Rôle métier** : Référencer chaque HTML poussé sur GitHub Pages.

| Colonne | Rôle | Usage code | Conséquence suppression |
|---|---|---|---|
| **doc_id** | PK | 🟢🔵🟣 (1 fichier) | 🟡 |
| **install_id** | FK | 🟢🔵 (3 fichiers) | 🟡 |
| **pio_id** | FK | 🟢🔵 (11 fichiers) | 🟡 |
| **type_doc** | PASSEPORT / CERTIFICAT / GARANTIE / PORTAIL / AMBASSADEUR | ❌ Non lu nominalement (positionnel) | 🟡 Sans, impossible de filtrer par type |
| **date_generation** | Date | ❌ Non lu | 🟢 Stockage |
| **url_doc** | URL GitHub Pages | ❌ Non lu | 🟡 Stockage |
| **statut_envoi** | "sent" / "pending" | ❌ Non lu | 🟢 |
| **date_envoi** | (vide) | ❌ | 🟢 |
| **canal_envoi** | (vide) | ❌ | 🟢 |
| **html_content** | HTML brut | ❌ Non lu | 🟢 Sauvegarde de secours |

**Conséquence suppression de l'onglet** :
- 🟡 Pas de casse immédiate (URLs GitHub Pages reconstructibles)
- 🟡 Mais perte de l'historique d'envoi → impossible de savoir qui a reçu quoi

---

## 🟦 `07_Produits` — ANCIEN CATALOGUE (À SUPPRIMER)

**Rôle métier déclaré** : Catalogue produits
**Réalité** : **Doublon obsolète** de `07_Catalog`, jamais lu par le code
**Conséquence suppression** : 🟢 0 impact

---

## 🟦 `07_Catalog` — CATALOGUE PRODUITS DYNAMIQUE (utilisé)

**Rôle métier** : Référentiel des produits commercialisés (G30, G60, Ocean…).

| Colonne | Rôle | Usage code | Conséquence suppression |
|---|---|---|---|
| **produit_id** | PK ("G30") | 🟢 (1 fichier) | ⛔ Référence dans `02_Installations.produit` |
| **label** | "Générateur G30" | 🟢🟣 (3 fichiers) | 🔴 Affiché partout (passeport, certif, espace) |
| **garantie_mois** | 24 (par défaut) | 🟢 (2 fichiers) | 🔴 Calcul `date_garantie_fin` |
| **image_cloudinary_id** | ID Cloudinary | 🟢 (2 fichiers) | 🔴 Image du produit |
| **fiche_technique_url** | URL | 🟢 (2 fichiers) | 🟡 Affichage |
| **manuel_url** | URL | 🟢 (2 fichiers) | 🟡 Affichage |
| **photo_generateur_url** | URL | 🟢 (2 fichiers) | 🔴 Photo affichée si pas de photo réelle |
| **actif** | bool | 🟢 (1 fichier) | 🟡 Filtrage catalogue |

**Conséquence suppression de l'onglet** :
- ⛔ **CASSE** : webhook LIVRAISON échoue (pas de catalogue), passeport affiche "—" partout, calcul garantie impossible

---

## 🟦 `08_Automations_Log` — LOGS & IDEMPOTENCE

**Rôle métier** : Journal de tous les events webhooks + idempotence SAV + audit légal eIDAS.

| Colonne | Rôle | Usage code | Conséquence suppression |
|---|---|---|---|
| **timestamp** | Date UTC | ❌ Non lu nominalement (positionnel) | 🟡 Traçabilité |
| **action** | "livraison" / "sav" / "signature_eidas" / etc. | 🟢 (1 fichier) | 🔴 Filtrage idempotence |
| **install_id** | FK | 🟢 (3 fichiers) | 🟡 |
| **pio_id** | FK | 🟢 (11 fichiers) | 🟡 |
| **result** | "ok" / "error" | ❌ Non lu | 🟢 |
| **message** | "report_id=..." | 🟢 (1 fichier) | 🔴 **CONTIENT le `report_id`** utilisé pour idempotence SAV |
| **erreur_detail** | Stack trace | ❌ | 🟢 |

**Conséquence suppression de l'onglet** :
- ⛔ **CASSE l'idempotence SAV** : un même rapport sera enregistré plusieurs fois
- 🔴 **Perte de l'audit eIDAS** : non-conformité réglementaire pour les signatures Ambassadeur

---

## 🟦 `Import` — IMPORT EXTERNE NON RAPATRIÉ

**Rôle métier** : Liste de 118 contacts (avatar, nom, email, téléphone, pays) importée d'une source externe (probablement Tally ou similaire).

**Code** : ❌ Aucune lecture
**Réalité** : Ces 118 contacts n'ont jamais été transférés dans `01_Pionniers`.

**Conséquence suppression** :
- 🟢 0 impact technique
- 🟡 Perte de cette source si pas archivée. À analyser AVANT suppression : combien de ces 118 contacts sont déjà dans `01_Pionniers` ? (à recouper par email)

---

# 📊 SYNTHÈSE STATUTS / ÉNUMÉRATIONS

## Statuts dans `01_Pionniers.statut`

| Valeur | Lignes | Rôle | Lieu d'utilisation |
|---|---|---|---|
| `"Pionnier"` | 1 | Pionnier actif | Code mais pas de logique conditionnelle dessus |
| `"En attente"` | 196 | (Legacy — devrait être Pionnier) | Visible côté admin uniquement |

**Conséquence** : Aucune logique métier ne s'appuie sur la valeur → renommage en masse sans risque.

## Statuts Communauté (`01.fondateur`, `01.ambassadeur`, `01.communaute_statut`)

| Combinaison | Effet visible |
|---|---|
| `fondateur=false, ambassadeur=false` | Espace Pionnier basique, badge Pionnier seul |
| `fondateur=true, ambassadeur=false` | Badge Fondateur (luxueux) + grille verrouillée Ambassadeur |
| `fondateur=*, ambassadeur=true, communaute_statut!="super_ambassadeur"` | Badge Ambassadeur déverrouillé + Carte Ambassadeur |
| `ambassadeur=true, communaute_statut="super_ambassadeur"` | Badge Super Ambassadeur + 3 cartes déverrouillées |

→ **Ces 3 colonnes sont CRITIQUES** : leur modification a un effet visible immédiat sur l'espace pionnier publié sur GitHub Pages (après régénération).

## Statuts dans `02_Installations.installation_status`

| Valeur | Lignes | Usage code |
|---|---|---|
| `"active"` | ~155 | ❌ Non lu (juste stocké) |
| (autre) | 0 | — |

→ Pas de logique métier → suppression possible.

## Statuts dans `05_Maintenances.statut`

| Valeur | Lignes |
|---|---|
| `CLOTUREE`, `A_FAIRE`, `A_PLANIFIER` | mixed |
| (vide) | majoritaire |

→ Affichage uniquement, pas de logique métier.

---

# 🔥 COLONNES CRITIQUES (Non supprimables sans casse majeure)

| Onglet.Colonne | Pourquoi critique |
|---|---|
| `01_Pionniers.pio_id` | Clé primaire — utilisée partout |
| `01_Pionniers.nom` + `.prenom` | Affichés dans tous les documents générés |
| `01_Pionniers.email` | Envoi email bienvenue |
| `01_Pionniers.fondateur` | Détermine génération Passeport Fondateur |
| `01_Pionniers.ambassadeur` | Détermine déverrouillage cartes |
| `01_Pionniers.communaute_statut` | Détermine Super Ambassadeur |
| `02_Installations.install_id` | Clé primaire — URL passeport |
| `02_Installations.pio_id` | Relation vers pionnier |
| `02_Installations.numero_serie` | Webhook SAV (lookup) |
| `02_Installations.produit` | Lookup catalogue |
| `02_Installations.date_installation` | Calcul garantie |
| `02_Installations.date_garantie_fin` | Affichage garantie (ou recalculé) |
| `02_Installations.report_id` | Idempotence webhook |
| `04_Parametres.Compteurs` + `Valeur Actuelle` | Auto-incrément des IDs |
| `05_Maintenances.maintenance_id` | PK |
| `05_Maintenances.install_id` | FK |
| `07_Catalog.produit_id` + `.label` + `.garantie_mois` + `.image_cloudinary_id` | Tous les calculs produits |
| `08_Automations_Log.action` + `.message` | Idempotence + audit eIDAS |

---

# 🟢 COLONNES SUPPRIMABLES SANS CASSE

| Onglet.Colonne | Pourquoi |
|---|---|
| `01_Pionniers.NS` | Redondant avec `02_Installations.numero_serie` (après vérification que le code n'utilise plus la version 01) |
| `01_Pionniers.telephone` | Stockage uniquement |
| `01_Pionniers.client_type` | Règle métier "01 = Particulier" |
| `01_Pionniers.date_entree` | Vide à 99.5%, non utilisé |
| `01_Pionniers.visite_possible` | Stockage uniquement |
| `01_Pionniers.workflow_status` | Vide, mort |
| `01_Pionniers.welcome_email_sent` | Bug — toujours true même sans envoi |
| `01_Pionniers.certificat_url`, `carte_url`, `qr_code_url` | Reconstructibles dynamiquement |
| `02_Installations.date_sortie` | Vide à 100% |
| `02_Installations.installateur` | Non lu |
| `02_Installations.pionnier_created` | Historique, non lu |
| `02_Installations.nom_client` | Redondant avec lookup pio_id |
| `02_Installations.gamme` | Redondant avec `07_Catalog.gamme` |
| `02_Installations.contrat_maintenance_type` | Non lu |
| `02_Installations.statut_eau` | Legacy mort |
| `02_Installations.derniere_maintenance` | Calculable via 05 |
| `02_Installations.installation_active` | Redondant |
| `05_Maintenances.rapport_url`, `.pieces_changees`, `.prochain_rdv`, `.source` | Stockage uniquement |
| `06_Documents.statut_envoi`, `.date_envoi`, `.canal_envoi`, `.html_content` | Non lus |
| `07_Catalog.actif` | Filtrage rarement appliqué |
| `08_Automations_Log.result`, `.erreur_detail`, `.timestamp` | Stockage uniquement (timestamp est positionnel) |

---

# ⚠️ FAUX POSITIFS POSSIBLES

Certaines colonnes apparaissent "non lues" parce que le code utilise `append_row(values)` avec une **liste positionnelle** plutôt qu'un dictionnaire. Cela signifie que **l'ordre des colonnes est essentiel** : si vous ajoutez/retirez/déplacez une colonne dans le sheet sans modifier le code, vous casserez l'écriture.

**Colonnes potentiellement écrites positionnellement** :
- Toutes les colonnes de `01_Pionniers` (via `append_row("pionniers", [...])`)
- Toutes les colonnes de `02_Installations`, `05_Maintenances`, `06_Documents`

**Recommandation** : avant suppression d'une colonne, vérifier le code `append_row` exact et le mettre à jour.

---

# 🎯 RECOMMANDATIONS AVANT MIGRATION

1. **NE PAS toucher** aux colonnes "CRITIQUES" sans plan d'adaptation du code
2. **Sécuriser** la suppression des colonnes "SUPPRIMABLES" en mettant à jour `append_row` au passage
3. **Renommer** `01.statut = "En attente"` → `"Pionnier"` est **sans risque** (aucune logique métier)
4. **Conserver** absolument `08_Automations_Log` (idempotence + eIDAS)
5. **Conserver** absolument `04_Parametres.Compteurs` et `Valeur Actuelle`
6. **Tester** chaque changement structurel via les tests `/app/backend/tests` avant de publier

---

📁 Document complet pour consultation : ce rapport sert de **référence absolue** pour valider/ajuster les choix de migration.
