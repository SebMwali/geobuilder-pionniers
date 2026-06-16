# RAPPORT 8 — SÉCURISATION DES DONNÉES ET RÈGLES DE GESTION

*Rapport d'analyse et de recommandation uniquement. Aucune écriture, aucune suppression, aucune modification.*

---

# PARTIE 1 — UNICITÉ ET IDENTITÉ D'UN PIONNIER

## 1.1 Analyse des candidats à l'identité unique

| Candidat | Avantage | Inconvénient |
|---|---|---|
| **email** | Direct, vérifiable, unique côté Resend | Peut changer ; doublon courant en famille |
| **téléphone** | Stable individuel | Peut changer ; non saisi systématiquement |
| **nom + prénom** | Donnée naturelle | Homonymes, typos, ordre Mahorais ambigu |
| **pio_id** | Auto-géré, immuable | Identifiant artificiel — ne définit pas la personne, l'identifie |
| **email + nom de famille** | Combinaison robuste | Email + nom suffit pour discriminer |
| **téléphone + nom** | Robuste si téléphone stable | Téléphone manquant fréquent |

## 1.2 ⭐ Règle métier officielle recommandée

### R-IDENT-1 : Identité fonctionnelle

**Une personne physique est identifiée fonctionnellement par le couple `email + nom de famille (normalisé MAJUSCULES)`.**

- L'email seul **n'est pas suffisant** (cas du mail familial partagé)
- Le nom seul **n'est pas suffisant** (homonymes)
- La combinaison fournit un compromis robuste et exportable vers Odoo

### R-IDENT-2 : Identité technique

**Le `pio_id` est l'identifiant technique immuable et obligatoire dans le système.**

- Généré automatiquement à la création
- Jamais réutilisé
- Sert de clé étrangère partout

### R-IDENT-3 : Hiérarchie des identifiants

```
pio_id           = identifiant SYSTÈME (immuable)
email + nom      = identité FONCTIONNELLE (modifiable)
téléphone        = info de CONTACT (modifiable)
NS               = donnée TECHNIQUE rattachée à l'install, pas au pionnier
```

## 1.3 Traitement des 7 cas

### Cas 1 — Même personne, nouvel email

- **Risque** : création d'un doublon (nouveau pio_id) si pas de détection
- **Comportement recommandé** :
  - À la création, comparer le `nom_de_famille` + `téléphone` avec l'existant
  - Si match potentiel → écran de confirmation pour l'admin OU log d'alerte
  - Mise à jour de l'email sur la fiche existante plutôt que création
- **Impact app** : éviter la duplication d'espaces pionniers, conserver l'historique

### Cas 2 — Même personne, nouveau téléphone

- **Risque** : faible (le téléphone n'est pas identité)
- **Comportement recommandé** : update direct sur `01_Pionniers.telephone` (édition admin ou self-service Phase 3)
- **Impact app** : aucun

### Cas 3 — Erreur de saisie sur le nom

- **Risque** : doublon caché (nom faussement différent)
- **Comportement recommandé** :
  - Correction directe par l'admin sur `01_Pionniers.nom`
  - **Régénérer les documents** (Passeport, Certificats) car ils affichent le nom
- **Impact app** : 🔴 Documents existants sur GitHub Pages affichent encore l'ancien nom → besoin de régénération explicite

### Cas 4 — Deux personnes avec le même email familial

- **Risque** : confusion identité, doublons silencieux
- **Comportement recommandé** :
  - **Email seul n'est pas identifiant** → la règle R-IDENT-1 protège
  - Possibilité de 2 pio_id avec le même email tant que `nom_de_famille` diffère
  - Si même nom + même email → arbitrage manuel (parents, conjoints, enfants ?)
- **Impact app** : les emails de bienvenue arrivent sur la même boîte, c'est OK

### Cas 5 — Deux personnes avec le même nom

- **Risque** : confusion lors de matching
- **Comportement recommandé** :
  - Discrimination par `email` + `prenom`
  - Si email identique + nom identique → cas 1 (même personne, considérer ainsi)
  - Si email différent + nom identique → 2 personnes distinctes (OK)
- **Impact app** : aucun si email distincts

### Cas 6 — Fusion de fiches pionniers

- **Risque** : perte de données, casse de FKs
- **Comportement recommandé** :
  - Identifier la fiche **canonique** (gardée) et la fiche **fusionnée** (absorbée)
  - Reporter sur la canonique : la plus ancienne `date_entree`, toutes les installations, tout l'historique
  - **NE PAS supprimer** la fiche absorbée mais marquer `statut="Fusionné"` + commentaire pointant vers canonique
  - Régénérer documents de la canonique
- **Impact app** : 🟡 Les URLs de la fiche fusionnée restent en place mais redirigent visuellement vers la canonique (à concevoir)

### Cas 7 — Détection automatique de doublons

**Algorithme proposé** :
1. Pour chaque nouvelle création (webhook) :
   - Calculer hash `lowercase(email) + uppercase(nom_de_famille)`
   - Vérifier si ce hash existe déjà dans `01_Pionniers`
2. Si doublon détecté :
   - **Bloquer la création silencieuse**
   - Logger dans `08_Automations_Log` (action=`doublon_detecte`)
   - Retourner une erreur à l'app SAV avec le `pio_id` existant
3. Audit hebdomadaire :
   - Script qui détecte les doublons potentiels par similarité Levenshtein des noms
   - Rapport mensuel à valider par vous

**Risque résiduel** : variantes orthographiques (ex : `Mickaël` vs `Mickael`) → matching sur la version normalisée (sans accent, MAJ).

---

# PARTIE 2 — GESTION DES NUMÉROS DE SÉRIE

## 2.1 Workflow détaillé en 6 étapes

### Étape 1 — Saisie du NS par le Pionnier

- **Lieu** : Espace Pionnier (`portail_pionnier.html`), nouvelle carte interactive
- **Données saisies** : NS texte libre + numéro d'installation concerné (si plusieurs)
- **Données enregistrées** : aucune (étape de saisie, pas encore validée)
- **Contrôles** :
  - Format respecté : regex `^(HR88C\d{2}[A-Z]+\d+|EA\d+L\d+[A-Z]+\d+S?|ZL\d+W\d+[A-Z]+\d+S?|HR90[A-Z0-9]+)$`
- **Risques** : typo de l'utilisateur → étape 3 doit lever
- **Actions possibles** : annuler, recommencer

### Étape 2 — Photo de l'étiquette

- **Données saisies** : fichier image (JPEG/PNG, max 5 MB)
- **Données enregistrées** : aucune si étape 1 n'est pas validée encore
- **Contrôles** : taille, format, dimension minimum
- **Risques** : photo non-lisible, photo d'un autre générateur
- **Actions possibles** : retake, skip (photo optionnelle)

### Étape 3 — Contrôle automatique

- **Vérifications** :
  - **Format NS** : regex
  - **Unicité** : ce NS n'existe pas déjà ailleurs dans `02_Installations.numero_serie`
  - **Cohérence produit** : préfixe NS doit matcher le produit de l'installation (HR88 = G30, EA60 = Ocean 500, etc.)
- **Données enregistrées** : aucune
- **Risques** :
  - NS valide mais déjà attribué → conflit
  - NS valide mais préfixe ne matche pas le produit → typo probable
- **Actions** :
  - ✅ Si tous contrôles OK → étape 4
  - ❌ Si conflit → message d'erreur explicite + suggestion (re-saisie ou demande de support)

### Étape 4 — Contrôle humain Geobuilder

- **Action** : un admin (vous ou délégué) valide manuellement les saisies en attente
- **Données affichées** : pio_id, nom, install_id, NS saisi, photo, conformité auto
- **Contrôles humains** :
  - Vérification visuelle de la photo (le NS lu sur la photo correspond au NS saisi ?)
  - Cohérence avec l'historique du Pionnier
- **Risques** : engorgement (si beaucoup de saisies)
- **Actions** :
  - ✅ Valider → étape 5
  - ❌ Rejeter avec motif → notification email au Pionnier pour re-saisir

### Étape 5 — Validation

- **Données enregistrées** :
  - `02_Installations.numero_serie = NS saisi`
  - `02_Installations.source_creation = "ns_via_app"`
  - `02_Installations.photo_generateur_url = URL photo` (si fournie)
  - `08_Automations_Log` : ligne `action=saisie_ns_validee, pio=...`, hash du payload
- **Contrôles** : transaction atomique (tout ou rien)

### Étape 6 — Association définitive et régénération

- **Données mises à jour** :
  - `02_Installations` (NS, photo)
  - Régénération du **Passeport** (avec NS affiché)
  - Régénération de la **carte "Mon installation"** sur l'espace pionnier
  - Push GitHub Pages
- **Notification** : email "Votre numéro de série a été enregistré"
- **Impact espace pionnier** : la carte d'alerte disparaît, le NS est visible

## 2.2 Cas particuliers

### NS déjà attribué

- **Détection** : Étape 3 (contrôle unicité)
- **Conduite** :
  - Bloquer la saisie côté front
  - Logger l'incident dans `08_Automations_Log`
  - Inviter le Pionnier à contacter le support
  - **JAMAIS** réassigner automatiquement

### NS inexistant (jamais émis)

- **Détection** : impossible automatiquement (pas de base constructeur)
- **Conduite** :
  - Saisie acceptée si format valide
  - Photo de l'étiquette obligatoire dans ce cas
  - Contrôle humain renforcé (étape 4)

### NS mal saisi (typo)

- **Détection** : Étape 3 ou 4
- **Conduite** :
  - Si format OK mais préfixe ne matche pas le produit → rejet auto avec message "Vérifiez le NS"
  - Si format invalide → rejet immédiat avec exemple

### Photo absente

- **Conduite** : saisie acceptée si format NS strictement valide ET pas de conflit. Sinon, photo obligatoire.

### Plusieurs NS pour un même pionnier

- **Cas** : pionnier multi-générateurs
- **Conduite** :
  - Formulaire liste les installations sans NS rattachées à `pio_id`
  - Le Pionnier doit explicitement choisir quelle installation
  - Pas de NS unique = pas d'ambiguïté possible

### Plusieurs pionniers revendiquant le même NS

- **Conduite** :
  - 1er arrivé = 1er servi (validé en étape 5)
  - Les suivants reçoivent une alerte "Ce NS est déjà attribué — contactez le support"
  - Arbitrage humain obligatoire en cas de revendication conflictuelle
  - Logger l'historique des revendications dans `08_Automations_Log`

---

# PARTIE 3 — STRUCTURES PRÉSENTES DANS `01_PIONNIERS`

**Analyse en lecture seule. Aucune ligne supprimée.**

📁 Données complètes : [`structures_dans_01_pionniers.json`](https://pioneer-ecosystem.preview.emergentagent.com/reports/audit/structures_dans_01_pionniers.json)

## 3.1 Liste exhaustive (25 lignes suspectées)

### 🔴 Confiance 1.0 — Structures déjà déclarées non-Particulier (5)

| pio_id | nom complet | client_type actuel | Catégorie |
|---|---|---|---|
| **PIO-1012** | Hippocampe plongée | `Entreprise` | Entreprise |
| **PIO-1014** | Atelier Mahorais d'architecture | `Entreprise` | Entreprise |
| **PIO-1017** | Patricia Marceaux | `Administration` | Administration (à vérifier : prénom + nom évoquent un particulier) |
| **PIO-1018** | Association unono wa matso | `Administration` | Association |
| **PIO-1086** | Foundi distribution | `Entreprise` | Entreprise / Groupe distribution |

### 🟠 Confiance 0.9 — Mot-clé structure dans le nom (12)

| pio_id | nom complet | Justification |
|---|---|---|
| PIO-1076 | CIRAD Antenne de Mayotte | "CIRAD" + "Antenne" |
| PIO-1078 | CRECHE Les enfants des Margouillats | "CRECHE" |
| PIO-1079 | Cabinet Infirmier Triquet Triquet François | "Cabinet Infirmier" — profession libérale |
| PIO-1087 | France Alzheimer Mayotte | Association |
| PIO-1091 | HELILAGON | Société |
| PIO-1106 | Mayotte Clotures et Jardins Fraisse | Entreprise |
| PIO-1135 | SARL VETO | "SARL" |
| PIO-1142 | ROCS | Acronyme + structure (vu dans le parc) |
| PIO-1143 | SAS MATIS | "SAS" |
| PIO-1144 | SOS OXYGENE | "SOS OXYGENE" — entreprise médicale |
| PIO-1146 | Gaëlle TOURON | "TOURON" — vue dans le parc comme "BAOBAB/TOURON" (à confirmer) |
| PIO-1151 | Tetrama exploitation | "Exploitation" |

### 🟡 Confiance 0.6 — Acronyme MAJ sans prénom — à confirmer cas par cas (8)

| pio_id | nom complet | Interprétation possible |
|---|---|---|
| PIO-1007 | STEPHAN | Probablement nom de famille de particulier |
| PIO-1039 | WEISS | Probablement nom de famille |
| PIO-1067 | ANSEL | Probablement nom de famille |
| PIO-1094 | JOSEPH | Probablement nom de famille |
| PIO-1107 | ABASSI | Probablement nom de famille (mahorais) |
| PIO-1128 | GARNIER | Probablement nom de famille |
| PIO-1134 | OTHMANI | Probablement nom de famille (mahorais) |
| PIO-1152 | RAFFARD | Probablement nom de famille |

→ Ces 8 cas sont **probablement de vrais particuliers** mal saisis (sans prénom). À compléter, pas à exclure.

## 3.2 Synthèse — Lignes à arbitrer

| Catégorie | Nombre | Action proposée (à valider) |
|---|---|---|
| 🔴 Structures certaines (à exclure) | **17** | Préparer leur sortie de `01_Pionniers` |
| 🟡 Acronymes ambigus (à compléter) | **8** | Compléter le prénom manquant |

**Aucune action prise**. À vous de valider la liste avant toute exclusion.

---

# PARTIE 4 — RÉCUPÉRATION D'ACCÈS — Cas 8

## 4.1 Scénarios à couvrir

### 4.1.1 Scénario A — Email perdu (ou inaccessible)

- **Parcours utilisateur** :
  1. Le pionnier va sur une page publique "Je ne peux plus accéder à mon espace"
  2. Saisit `nom + téléphone + ville` (combinaison robuste)
  3. Le système retrouve sa fiche
  4. Envoi d'un email de récupération vers son **nouvel email** (à confirmer)
- **Contrôles** :
  - Match flou nom + téléphone
  - Validation par admin si match incertain
- **Validation** : changement email validé après clic dans email (token signé)
- **Impacts** : update `01_Pionniers.email`

### 4.1.2 Scénario B — Téléphone changé

- **Parcours** : le pionnier accède via son email (lien d'origine), va dans son espace, met à jour son téléphone
- **Contrôles** : aucun — donnée non-critique
- **Validation** : aucune

### 4.1.3 Scénario C — Lien d'origine perdu

- **Parcours** :
  1. Le pionnier va sur "Retrouver mon espace"
  2. Saisit `email`
  3. Reçoit l'email contenant ses 5 liens (espace, certif, passeport, garantie, carte)
- **Contrôles** : email présent dans `01_Pionniers`
- **Validation** : aucune (l'email est self-validant)
- **Impacts** : aucun changement de données

### 4.1.4 Scénario D — Compte jamais activé

- **Diagnostic** : `01.welcome_email_sent=false` ou bounce email connu
- **Parcours** :
  1. Admin sélectionne la fiche
  2. Endpoint `POST /api/admin/regenerate-pionnier/{pio_id}`
  3. Re-génère les 5 HTML + push GitHub Pages + envoi email
- **Contrôles** : la fiche existe et est complète (email + nom + pio_id)
- **Impacts** : `welcome_email_sent=true` + log

### 4.1.5 Scénario E — Pionnier historique créé avant l'app

- **Cas** : le pionnier existe dans `01_Pionniers` (import historique) mais n'a jamais eu d'HTML publié, jamais eu d'email
- **Diagnostic** : `01.welcome_email_sent != true` ET pas de lignes correspondantes dans `06_Documents`
- **Parcours** :
  1. Identique au scénario D
  2. Plus une vérification que `02_Installations` contient une install pour ce `pio_id` (sinon impossible de générer Passeport)
- **Si pas d'install** : créer une install temporaire ou attendre que le pionnier saisisse son NS (Phase 2)

## 4.2 Tableau récapitulatif

| Scénario | Contrôle requis | Validation requise | Impact données |
|---|---|---|---|
| A — Email perdu | Match nom+téléphone | Token email | Update `email` |
| B — Téléphone changé | aucun | aucun | Update `telephone` |
| C — Lien perdu | Email existant | aucun | aucun |
| D — Compte jamais activé | Fiche complète | Admin | `welcome_email_sent=true` + logs |
| E — Historique pré-app | Fiche complète + install présente | Admin | Idem D, + éventuel besoin de saisir NS |

---

# PARTIE 5 — MATRICE D'ACTIONS AUTORISÉES / INTERDITES

## 5.1 Vue d'ensemble

| Action | 🟢 Auto | 🟡 Validation humaine | 🔴 Interdit sans décision explicite |
|---|---|---|---|
| Création Pionnier via webhook LIVRAISON | ✅ | | |
| Création Installation via webhook | ✅ | | |
| Création Maintenance via webhook SAV | ✅ | | |
| Génération documents HTML | ✅ | | |
| Push GitHub Pages | ✅ | | |
| Envoi email bienvenue | ✅ | | |
| Idempotence (skip si `report_id` déjà vu) | ✅ | | |
| Log dans `08_Automations_Log` | ✅ | | |
| Calcul `date_garantie_fin` (+24 mois) | ✅ | | |
| Lecture catalogue produits | ✅ | | |
| Régénération Passeport après signature Ambassadeur | ✅ | | |
| Régénération Passeport après promote Super | ✅ | | |
| Signature Ambassadeur (eIDAS) | ✅ (init utilisateur) | | |
| Promotion Super Ambassadeur | | ✅ (admin) | |
| Désignation Fondateur (max 100) | | ✅ (admin) | |
| Update email Pionnier | | ✅ (admin ou self-service avec token) | |
| Update téléphone | | ✅ (self-service ou admin) | |
| Update nom/prenom | | ✅ (admin) + régen documents | |
| **Saisie NS via app** | | ✅ (contrôle humain étape 4) | |
| **Détection doublon Pionnier** | ✅ alerte | ✅ arbitrage | |
| **Fusion de fiches** | | ✅ (admin obligatoire) | |
| **Suppression d'une ligne `01_Pionniers`** | | | ✅ Interdit — utiliser `statut="Fusionné"` ou `"Inactif"` |
| **Suppression d'une ligne `02_Installations`** | | | ✅ Interdit — utiliser `statut="Désinstallée"` |
| **Suppression d'une ligne `05_Maintenances`** | | | ✅ Interdit |
| **Modification du `pio_id` existant** | | | ✅ Interdit — casse toutes les URLs |
| **Modification du `install_id` existant** | | | ✅ Interdit |
| **Suppression d'un onglet critique** (01, 02, 04, 05, 06, 07_Catalog, 08) | | | ✅ Interdit |
| **Édition massive de `01.fondateur`** | | ✅ Sébastien uniquement | |
| **Réassignation d'un NS** | | | ✅ Interdit en automatique (arbitrage humain obligatoire) |
| **Export de données** | ✅ | | |
| **Suppression onglets morts** (`03_Medias`, `07_Produits`) | | ✅ Sébastien | |
| **Renommage statut "En attente" → "Pionnier"** | | ✅ Sébastien | |
| **Correction `#REF!`** | | ✅ Sébastien (arbitrage par cas) | |

## 5.2 Règles d'or

| # | Règle |
|---|---|
| OR-1 | **Aucune écriture massive sans backup** JSON préalable |
| OR-2 | **Aucune suppression de ligne** dans 01, 02, 05 — toujours marquer un statut |
| OR-3 | **Aucune réassignation automatique** de NS ou pio_id |
| OR-4 | **Toute fusion de fiches** doit être tracée dans `08_Automations_Log` |
| OR-5 | **Toute édition admin** doit être loggée dans `08_Automations_Log` |
| OR-6 | **Les onglets `01_Pionniers`, `02_Installations`, `05_Maintenances`** sont en lecture seule sauf workflow validé |

---

# 📋 LIVRABLE FINAL — RÈGLES MÉTIER OFFICIELLES

| # | Code | Règle | Statut |
|---|---|---|---|
| 1 | R-IDENT-1 | Identité fonctionnelle = `email + nom_de_famille` | À valider |
| 2 | R-IDENT-2 | `pio_id` = identifiant technique immuable | À valider |
| 3 | R-IDENT-3 | Hiérarchie `pio_id` > `email+nom` > `téléphone` > `NS` | À valider |
| 4 | R-NS-1 | Format NS validé par regex à la saisie | À valider |
| 5 | R-NS-2 | Unicité NS dans `02_Installations` obligatoire | À valider |
| 6 | R-NS-3 | Cohérence préfixe NS ↔ produit obligatoire | À valider |
| 7 | R-NS-4 | Validation humaine obligatoire avant écriture NS | À valider |
| 8 | R-NS-5 | Pas de réassignation auto de NS | À valider |
| 9 | R-DEDUP-1 | Détection doublon `email + nom_de_famille` à chaque création | À valider |
| 10 | R-DEDUP-2 | Audit hebdomadaire des similarités Levenshtein | À valider |
| 11 | R-FUSION-1 | Pas de suppression — `statut="Fusionné"` | À valider |
| 12 | R-FUSION-2 | Trace obligatoire dans `08_Automations_Log` | À valider |
| 13 | R-ACCES-1 | Récupération via `email + token` | À valider |
| 14 | R-ACCES-2 | Endpoint admin pour régénération Pionnier existant | À valider |
| 15 | R-STRUCT-1 | Structures (B2B) interdites dans `01_Pionniers` | ✅ Validée précédemment |
| 16 | R-STRUCT-2 | 17 lignes structures identifiées à sortir | À arbitrer |
| 17 | R-FOND-1 | Statut Fondateur limité à 100 | À valider |
| 18 | R-FOND-2 | Désignation Fondateur exclusivement admin | À valider |
| 19 | R-AMBASS-1 | Statut Ambassadeur volontaire et signé eIDAS | ✅ Implémentée |
| 20 | R-SUPER-1 | Statut Super = décision admin exclusive | ✅ Implémentée |
| 21 | R-IMMUTABLE-1 | `pio_id`, `install_id`, `maintenance_id` immuables | À valider |
| 22 | R-AUDIT-1 | Toute édition admin loggée dans `08_Automations_Log` | À implémenter |

---

## 🎯 Conclusion

Vous disposez maintenant de :
- **22 règles métier officielles** à valider/ajuster
- Un **workflow NS complet** en 6 étapes avec gestion des cas particuliers
- Une **liste précise des 25 lignes suspectées** d'être des structures (17 quasi-certaines + 8 ambiguës)
- Un **parcours de récupération d'accès** en 5 scénarios
- Une **matrice 🟢/🟡/🔴** complète des actions autorisées

**Aucune écriture effectuée.**

À vous de valider règle par règle. Je peux ensuite produire :
- Un rapport synthétique des règles approuvées
- Le détail technique d'implémentation pour chaque règle (Phase 2 par exemple)
- L'arbitrage cas par cas des 25 lignes structures
