# RAPPORT 7 — PARCOURS MÉTIER COMPLETS DU PROGRAMME PIONNIERS

*Rapport d'analyse uniquement. Aucune écriture, aucune suppression, aucune modification.*
*Lisible par un chef de projet métier — pas seulement par un développeur.*

---

## 0. Vocabulaire de référence

| Terme | Définition |
|---|---|
| **Pionnier** | Un particulier ayant reçu un générateur Geobuilder. Identifié par `pio_id` (ex : `PIO-1196`). |
| **Installation** | Un générateur physique installé chez un Pionnier. Identifié par `install_id` (ex : `INST-2199`). Un Pionnier peut avoir plusieurs installations. |
| **NS (Numéro de Série)** | Identifiant constructeur du générateur (ex : `HR88C23EFR0080`). Une donnée d'enrichissement progressif. |
| **Espace Pionnier** | Page personnelle hébergée sur GitHub Pages (`/pionniers/{pio_id}/`). |
| **Passeport** | Document HTML d'un générateur (`/passeports/{install_id}/`). |
| **Certificat Pionnier** | Reconnaissance officielle de l'appartenance au programme. |
| **Certificat Garantie** | Document attestant la garantie +2 ans (par installation). |
| **Carte Pionnier** | Carte numérique avec QR code. |
| **Badge** | Distinction visuelle Fondateur / Ambassadeur / Super Ambassadeur (PNG généré via Playwright). |
| **eIDAS** | Norme européenne de signature électronique. La signature Ambassadeur produit une attestation eIDAS-compliant. |

---

## 1. Schéma métier global

```
Installation chez le client (vie réelle)
        │
        ▼
Rapport SAV signé (PDF transmis à l'app SAV)
        │
        ▼ webhook LIVRAISON
┌─────────────────────────────────┐
│  Backend Pionniers (FastAPI)    │
└─────────────────────────────────┘
        │
        ├── crée Pionnier (01)
        ├── crée Installation (02)
        ├── crée 5 Documents (06)
        ├── pousse 5 HTML sur GitHub Pages
        └── envoie 1 email de bienvenue (Resend)
        │
        ▼
Le pionnier reçoit l'email et accède à son espace personnel
        │
        ▼
Cycle de vie continu :
   • Signature Ambassadeur (volontaire)
   • Promotion Super Ambassadeur (admin)
   • Maintenances périodiques (SAV)
   • Saisie progressive du NS (futur — Phase 2)
```

---

# CAS MÉTIER 1 — Nouveau client

## 1.1 Étapes opérationnelles

| Étape | Acteur | Action concrète | Lieu |
|---|---|---|---|
| 1 | Technicien Geobuilder | Installe le générateur chez le client (sur site) | Domicile du Pionnier |
| 2 | Technicien | Fait signer le rapport SAV (papier ou tablette) | Sur site |
| 3 | App SAV | Génère le PDF du rapport et le transmet | Cloud SAV |
| 4 | App SAV | Déclenche webhook `POST /api/webhook/intervention` (type LIVRAISON) | Backend |
| 5 | Backend Pionniers | Extrait les données du PDF, génère IDs, écrit dans le Sheet, génère les HTML, pousse sur GitHub Pages, envoie email | Backend |
| 6 | Resend | Délivre l'email de bienvenue | Boîte mail du Pionnier |
| 7 | Pionnier | Reçoit l'email, clique sur le lien Espace Pionnier | Espace Pionnier (web) |

## 1.2 Données créées étape par étape

### Étape 5a — Création du Pionnier (`01_Pionniers`)

| Donnée créée | Source | Obligatoire | Note |
|---|---|---|---|
| `pio_id` | Auto-incrément (`04_Parametres`) | ✅ | Ex : `PIO-1197` |
| `nom` | Extrait du PDF (NLP) | ✅ | MAJUSCULES |
| `prenom` | Extrait du PDF | ✅ | CamelCase |
| `email` | Payload webhook | ✅ | Critique pour envoi email |
| `telephone` | Payload webhook | 🟡 Recommandé | Si dispo |
| `pays` | Payload webhook ou défaut | ✅ | "France" / "Mayotte" / etc. |
| `territoire` | Mapping depuis adresse | 🟡 | "Mayotte" / "Réunion" / "Comores" / etc. |
| `date_entree` | `today()` | ✅ | ISO 8601 |
| `statut` | `"Pionnier"` | ✅ | (au lieu de "En attente" actuellement) |
| `fondateur` | `false` (par défaut) | ✅ | À mettre à jour manuellement après si applicable |
| `ambassadeur` | `false` | ✅ | Modifiable via signature |
| `source_creation` | `"backend_livraison"` | ✅ | Traçabilité |

### Étape 5b — Création de l'Installation (`02_Installations`)

| Donnée créée | Source | Obligatoire |
|---|---|---|
| `install_id` | Auto-incrément | ✅ |
| `pio_id` | FK Pionnier nouvellement créé | ✅ |
| `produit` | Extrait du PDF | ✅ (sinon pas de catalogue) |
| `numero_serie` | Extrait du PDF | 🟡 (vide si pas dans le PDF, sera enrichi via app) |
| `date_installation` | Extrait du PDF | ✅ |
| `date_garantie_fin` | Calculé = `date_installation + garantie_mois` (depuis catalogue) | ✅ |
| `territoire_installation` | Mapping adresse | ✅ |
| `passeport_url` | URL générée vers GitHub Pages | ✅ |
| `report_id` | UUID du rapport (idempotence) | ✅ |

### Étape 5c — Création des Documents (`06_Documents`)

5 lignes créées :

| Type | Cible | URL générée |
|---|---|---|
| PASSEPORT | install_id | `/passeports/{install_id}/index.html` |
| CERTIFICAT_PIONNIER | pio_id | `/certificats/pionnier/{pio_id}.html` |
| CERTIFICAT_GARANTIE | install_id | `/certificats/garantie/{install_id}.html` |
| PORTAIL | pio_id | `/pionniers/{pio_id}/index.html` |
| CARTE | pio_id | `/cartes/{pio_id}.html` |

### Étape 5d — Push GitHub Pages

5 fichiers HTML poussés simultanément via API GitHub.

### Étape 5e — Envoi email via Resend

L'email contient les 5 liens ci-dessus + un CTA "Devenir Ambassadeur".

### Étape 5f — Log d'idempotence (`08_Automations_Log`)

1 ligne `action=livraison`, `report_id=...` → empêche un re-traitement.

## 1.3 Conséquences sur l'application

- ✅ Le Pionnier reçoit son **email de bienvenue** sous quelques secondes
- ✅ Tous les liens fonctionnent immédiatement (5 HTML publiés)
- ✅ Son Passeport affiche : produit, NS (si dispo), photo générateur, dates, statut
- ✅ Son Espace Pionnier affiche : ses installations, ses cartes Ambassadeur/Super verrouillées
- ✅ Son Certificat Garantie affiche la date de fin de garantie automatiquement calculée

## 1.4 Risques de ce parcours

| Risque | Probabilité | Mitigation actuelle |
|---|---|---|
| Doublon (re-déclenchement du webhook) | Moyenne | ✅ Idempotence via `report_id` |
| Email rejeté / spam | Faible | ⚠️ Pas de notification admin si échec |
| Email mal extrait du PDF | Moyenne | 🔴 Aucun contrôle de validité |
| NS absent du PDF | Élevée (cas historique) | ✅ Champ vide accepté, NS enrichi plus tard |
| pio_id collision | Très faible | ✅ Compteur centralisé |

---

# CAS MÉTIER 2 — Ancien client déjà dans `01_Pionniers`

## 2.1 Situation

Le pionnier existe déjà dans `01_Pionniers` (peut-être suite à un import manuel ou une migration historique). Il n'a peut-être pas reçu d'email, peut-être pas d'espace Pionnier généré.

## 2.2 Comment est-il reconnu ?

**Aujourd'hui** : pas de mécanisme automatique. Reconnaissance manuelle par recherche du `pio_id` ou de l'email/nom dans le Sheet.

**Risque** : si le technicien re-crée le Pionnier au lieu de retrouver le `pio_id` existant → doublon.

## 2.3 Comment récupère-t-il son accès ?

Trois options métier :

| Option | Description | Réaliste ? |
|---|---|---|
| A | L'admin retrouve `pio_id` et déclenche manuellement la régénération + envoi email | 🟡 Demande un endpoint admin dédié (`POST /api/admin/regenerate-pionnier/{pio_id}`) à créer |
| B | Lui transmettre directement les URLs (espace, passeport, etc.) par mail manuel | ✅ Possible aujourd'hui mais artisanal |
| C | Endpoint "Réclamer mon accès" public (formulaire email + vérification) | 🟡 À concevoir |

## 2.4 Comment ses données sont-elles complétées ?

- **NS manquant** : phase 2 du plan (workflow "Saisir mon NS" depuis l'espace Pionnier)
- **Email manquant** : édition directe du Sheet par l'admin
- **Statut Fondateur** : édition manuelle par vous (après validation manuelle des 100 fondateurs)
- **Statut Ambassadeur** : signature volontaire du Pionnier via le formulaire dédié

## 2.5 Risques

- 🔴 **Doublon** : si l'app SAV re-déclenche un webhook LIVRAISON avec un email identique → un nouveau `pio_id` est créé. **Aucun contrôle d'unicité d'email aujourd'hui.**
- 🟡 **Données incohérentes** : un ancien client avec un `pio_id` mais sans certificat publié sur GitHub Pages = lien cassé sur tout document généré ultérieurement.

## 2.6 Recommandation métier

**Avant** d'ouvrir un workflow public "Réclamer mon accès", **fiabiliser** la base existante :
1. Recouper `01_Pionniers` avec les anciens emails connus
2. Pour les pionniers historiques sans HTML publié → relancer la génération via un endpoint admin (sans recréer la ligne)
3. Envoyer un email "bienvenue rétroactive" à tous

---

# CAS MÉTIER 3 — Ancien client sans NS connu

## 3.1 Situation

Le Pionnier existe (`pio_id` présent), son installation existe (`install_id` présent), mais `02_Installations.numero_serie` est vide.

## 3.2 Parcours utilisateur proposé (Phase 2)

| Étape | Acteur | Action |
|---|---|---|
| 1 | Pionnier | Accède à son Espace Pionnier |
| 2 | Espace Pionnier | Affiche une carte d'alerte : "📷 Renseignez le N° de série de votre générateur pour activer votre suivi SAV" |
| 3 | Pionnier | Clique sur la carte, ouvre un formulaire |
| 4 | Pionnier | Saisit le NS (avec aide visuelle "où trouver le NS") + photo optionnelle |
| 5 | Pionnier | Clique sur "Envoyer" |
| 6 | Backend | `POST /api/pionnier/saisir-ns` |
| 7 | Backend | Valide le format (regex `HR88…`, `EA60…`, etc.) |
| 8 | Backend | Vérifie l'unicité (NS pas déjà attribué) |
| 9 | Backend | Update `02_Installations.numero_serie` + `source_creation = "ns_via_app"` |
| 10 | Backend | Log dans `08_Automations_Log` |
| 11 | Backend | Régénère le Passeport (avec NS affiché) |
| 12 | Backend | Pousse le nouveau Passeport sur GitHub Pages |
| 13 | Espace Pionnier | Confirmation visuelle + retrait de l'alerte |

## 3.3 Contrôles métier obligatoires

| Contrôle | Règle |
|---|---|
| Format NS | regex : `^(HR88C\d{2}[A-Z]+\d+|EA\d+L\d+[A-Z]+\d+S?|ZL\d+W\d+[A-Z]+\d+S?|HR90[A-Z0-9]+)$` |
| Unicité | Ce NS ne doit pas déjà être présent dans `02_Installations.numero_serie` |
| Cohérence produit | Le préfixe NS doit correspondre au `produit` de l'installation (HR88 = G30, EA60 = Ocean 500, etc.) |
| Photo | Optionnelle, mais si fournie → stockage et lien dans l'installation |

## 3.4 Mise à jour des données

| Onglet | Champ | Avant | Après |
|---|---|---|---|
| `02_Installations` | `numero_serie` | vide | `HR88C23EFR0080` |
| `02_Installations` | `source_creation` | "backend_livraison" | "ns_via_app" |
| `02_Installations` | `photo_generateur_url` | vide ou fallback | URL photo réelle (si fournie) |
| `08_Automations_Log` | nouvelle ligne | — | action=`saisie_ns`, message=`pio=...,install=...` |
| GitHub Pages | passeport HTML | sans NS | avec NS visible |

## 3.5 Impacts sur le Passeport

- Le bloc "Numéro de série" passe de vide → rempli
- Le QR code éventuel pointe vers la fiche complète
- Le suivi SAV devient possible (le webhook SAV pourra retrouver l'install via le NS)

## 3.6 Risques

| Risque | Mitigation |
|---|---|
| NS mal saisi (typo) | Validation format + confirmation visuelle avant submission |
| NS volé / d'un autre Pionnier | Validation unicité (rejet immédiat) |
| Pionnier oublie | Relance email programmée |
| Plusieurs installations sans NS | Le formulaire doit explicitement demander quelle installation est concernée |

---

# CAS MÉTIER 4 — Client avec plusieurs générateurs

## 4.1 Situation

Un Pionnier peut posséder plusieurs générateurs (multi-résidences, gros particulier, etc.).

## 4.2 Modèle de données

```
01_Pionniers
   PIO-1234 — Jean MARTIN
       │
       ├── 02_Installations
       │       INST-2300 — G30, NS=HR88C23EFR0080, date=2023-06-15
       │       INST-2301 — G30, NS=HR88C24AFR0150, date=2024-09-01
       │
       └── 05_Maintenances
               MAINT-3100 — INST-2300, 2024-01-15, MAINTENANCE_MENSUELLE
               MAINT-3101 — INST-2300, 2024-02-15, MAINTENANCE_MENSUELLE
               MAINT-3102 — INST-2301, 2024-10-01, LIVRAISON
```

→ **Relation `1 Pionnier → N Installations → N Maintenances par installation`** déjà supportée par le schéma actuel.

## 4.3 Affichage dans l'Espace Pionnier

**Aujourd'hui** : `portail_pionnier.html` affiche **une seule** installation (la 1ère / la plus récente).

**À adapter** (futur) : carousel ou liste des installations dans la carte "Mes installations".

## 4.4 Gestion des maintenances

Chaque maintenance est rattachée à une **installation précise** via `install_id` (pas via `pio_id`).
→ Pas de risque de confusion entre les générateurs.

## 4.5 Gestion des garanties

Chaque installation a sa propre `date_garantie_fin` (calculée à partir de sa propre `date_installation`).
→ Un Pionnier peut avoir 1 générateur encore sous garantie et 1 autre hors garantie.

## 4.6 Risques

| Risque | Mitigation |
|---|---|
| Génération du Passeport ne se fait que pour la 1ère install | Génération d'un passeport par `install_id` (déjà le cas dans le code) |
| Confusion lors de la saisie du NS via app | Le formulaire doit lister les installations sans NS et demander de choisir |
| 1 Certificat Pionnier pour plusieurs installs | ✅ Logique : 1 Pionnier = 1 Certificat Pionnier, indépendamment du nombre d'installs |
| Email de bienvenue dupliqué à chaque nouvelle install | Aujourd'hui : un email par livraison. À discuter : email unique si Pionnier déjà existant ? |

---

# CAS MÉTIER 5 — Passage Ambassadeur

## 5.1 Conditions d'accès

Aucune condition technique métier (pas de seuil d'ancienneté ni de nb d'installations). C'est **un acte volontaire du Pionnier** :
- Il signe le formulaire Ambassadeur depuis son Espace Pionnier
- Il consent explicitement aux 3 clauses (droit_image, témoignage, visite possible)

## 5.2 Parcours

| Étape | Acteur | Action |
|---|---|---|
| 1 | Pionnier | Clique sur le CTA "Devenir Ambassadeur" depuis email ou espace |
| 2 | Espace | Ouvre `ambassadeur.html` (formulaire) |
| 3 | Pionnier | Coche 3 cases + signe (saisie nom + email de confirmation) |
| 4 | Pionnier | Clique "Confirmer ma signature" |
| 5 | Backend | `POST /api/ambassadeur/signature` |
| 6 | Backend | Génère un hash SHA-256 du payload (eIDAS) |
| 7 | Backend | Capture IP, user-agent, timestamp UTC |
| 8 | Backend | Update `01_Pionniers.ambassadeur=true` + `droit_image/temoignage_autorise/visite_possible` |
| 9 | Backend | Log dans `08_Automations_Log` (action=`signature_eidas`) |
| 10 | Backend | Génère l'**Attestation eIDAS** (HTML imprimable) → push GitHub Pages |
| 11 | Backend | Génère le **Badge Ambassadeur** (HTML pixel-perfect + PNG via Playwright) → push |
| 12 | Backend | Régénère le **Passeport** (la grille 3×1 verrouillée passe à 1/3 déverrouillé) |
| 13 | Espace | Affiche confirmation, carte Ambassadeur déverrouillée |
| 14 | (Optionnel) | Email confirmation envoyé |

## 5.3 Données modifiées

| Onglet | Champ | Avant | Après |
|---|---|---|---|
| `01_Pionniers` | `ambassadeur` | false | true |
| `01_Pionniers` | `droit_image` | false | true |
| `01_Pionniers` | `temoignage_autorise` | false | true |
| `01_Pionniers` | `visite_possible` | false | true/false (selon coche) |
| `08_Automations_Log` | nouvelle ligne | — | action=signature_eidas, contenu hash |

## 5.4 Documents générés

| Document | URL |
|---|---|
| Attestation eIDAS | `/attestations/{pio_id}.html` |
| Badge Ambassadeur (HTML) | `/badges/ambassadeur/{pio_id}.html` |
| Badge Ambassadeur (PNG) | `/badges/ambassadeur/{pio_id}.png` |
| Passeport régénéré | `/passeports/{install_id}/index.html` (overwrite) |

## 5.5 Impacts visuels dans l'app

- ✅ Carte "Ambassadeur" sur l'espace Pionnier : verrouillée → **déverrouillée**
- ✅ Statut affiché : "Pionnier" → "Pionnier — Ambassadeur"
- ✅ Grille badges sur le Passeport : 1/3 verrouillé → **1/3 déverrouillé (le badge Ambassadeur)**

## 5.6 Risques

| Risque | Mitigation |
|---|---|
| Signature non-conforme eIDAS | ✅ Hash SHA-256 + IP + UA + UTC timestamp (conforme) |
| Pionnier change d'avis | ❌ Aujourd'hui pas de "désinscription" Ambassadeur — à concevoir si nécessaire RGPD |
| Doublons signature | ✅ Update idempotent (re-signature = nouvelle ligne log, mêmes flags) |

---

# CAS MÉTIER 6 — Passage Super Ambassadeur

## 6.1 Conditions d'accès

**Décision exclusivement admin** (vous décidez qui est Super). Pas de demande spontanée du Pionnier.

Pré-requis :
- Le Pionnier doit déjà être **Ambassadeur** (`01.ambassadeur=true`)

## 6.2 Parcours

| Étape | Acteur | Action |
|---|---|---|
| 1 | Sébastien (admin) | Sélectionne un Pionnier Ambassadeur méritant |
| 2 | Sébastien | Appelle `POST /api/admin/promote-super` avec `pio_id` |
| 3 | Backend | Vérifie que `01.ambassadeur=true` |
| 4 | Backend | Update `01_Pionniers.communaute_statut = "super_ambassadeur"` |
| 5 | Backend | Log dans `08_Automations_Log` (action=`promote_super`) |
| 6 | Backend | Génère le **Badge Super Ambassadeur** (HTML+PNG) |
| 7 | Backend | Régénère le **Passeport** (grille 2/3 déverrouillée) |
| 8 | Backend | Génère/Mets à jour la **Carte Super** sur l'espace Pionnier |
| 9 | (Optionnel) | Email "Félicitations vous êtes Super Ambassadeur" |

## 6.3 Données modifiées

| Onglet | Champ | Avant | Après |
|---|---|---|---|
| `01_Pionniers` | `communaute_statut` | (vide) | `super_ambassadeur` |
| `08_Automations_Log` | nouvelle ligne | — | action=promote_super |

## 6.4 Badges et cartes

- **Badge Super Ambassadeur** (PNG luxueux pixel-perfect) → `/badges/super/{pio_id}.png`
- **Carte Super Ambassadeur** : visible sur l'espace Pionnier, déverrouillée

## 6.5 Affichage

- Grille Passeport : 2/3 déverrouillés (Ambassadeur ET Super)
- Carte "Super Ambassadeur" : verrouillée → déverrouillée
- Statut affiché : "Pionnier — Super Ambassadeur"

## 6.6 Risques

| Risque | Mitigation |
|---|---|
| Promotion accidentelle | ✅ Endpoint admin uniquement, pas de UI publique |
| Pionnier non-Ambassadeur promu Super | ✅ Contrôle backend (rejet) |
| Démotion ? | ❌ Pas implémenté — possible besoin futur |

---

# CAS MÉTIER 7 — Statut Fondateur

## 7.1 Critères de sélection

**Définition métier** : Les **100 premiers Pionniers historiques** (par date d'installation) ayant contribué à lancer Geobuilder.

**Critères actuels** :
- Date d'installation antérieure à une certaine borne (à confirmer)
- Validation manuelle par vous

**Process** :
1. Constitution d'une liste de candidats potentiels (depuis `00_Fondateurs` qui contient 137 noms historiques)
2. Recoupement avec `01_Pionniers` (matching nom)
3. Sélection manuelle de 100 par vous
4. Mise à jour `01_Pionniers.fondateur=true` pour ces 100

**Aujourd'hui** : 67 lignes sont déjà `fondateur=true` dans `01_Pionniers` (peut-être un import provisoire, à valider).

## 7.2 Données modifiées

| Onglet | Champ | Avant | Après |
|---|---|---|---|
| `01_Pionniers` | `fondateur` | false | true |
| (optionnel) | Log admin | — | À ajouter si traçabilité requise |

## 7.3 Impact sur l'application

- ✅ Le **Passeport** affiche un badge "Fondateur" (luxueux PNG pré-généré)
- ✅ La grille badges du Passeport montre le badge Fondateur en valeur de pré-acquis
- ✅ Le **Certificat Pionnier** mentionne "Membre Fondateur" si applicable
- ✅ Possibilité de déverrouiller une carte "Fondateur" sur l'espace (à concevoir)

## 7.4 Gestion des 100 Fondateurs

**Règle métier proposée** : limite stricte à 100. Si plus de 100 lignes ont `fondateur=true`, un script doit alerter.

**Processus de désignation** :
1. Vous arbitrer la liste depuis l'onglet `00_Fondateurs` (en cours)
2. Une fois validée, report `fondateur=true` dans `01_Pionniers`
3. `00_Fondateurs` peut être supprimé après cela

## 7.5 Risques

| Risque | Mitigation |
|---|---|
| Plus de 100 Fondateurs (saisie erronée) | Script d'alerte / contrôle hebdomadaire |
| Critères non-documentés | Définir formellement les critères (date + ?) |
| Désignation post-mortem (pionnier décédé) | Conserver mais marquer `statut=Inactif` |
| Démotion (faute grave) | À discuter |

---

# 🧭 SYNTHÈSE TRANSVERSE — RISQUES ET CONTRÔLES

## Données obligatoires globales

| Donnée | Pourquoi obligatoire |
|---|---|
| `pio_id` | Clé primaire — sans ça, rien ne marche |
| `email` | Sans email, pas de communication |
| `nom` + `prenom` | Affichés sur tous les documents |
| `pays` ou `territoire` | Adaptation du contenu |
| `produit` (install) | Sans, pas de catalogue → pas de calcul garantie |
| `date_installation` (install) | Sans, pas de calcul garantie |
| `pio_id` (FK install/maintenance) | Sans, orphelin |

## Données facultatives mais utiles

- `telephone` (relances)
- `NS` (sera enrichi en Phase 2)
- `localisation_precise` (visite éventuelle)
- `photo_generateur_url` (rendu plus joli)

## Risques de doublons

| Source | Type de doublon | Mitigation actuelle |
|---|---|---|
| Webhook LIVRAISON re-déclenché | Pionnier + Installation dupliqués | ✅ Idempotence via `report_id` |
| Saisie manuelle Sheet | pio_id collision | ⚠️ Compteur peut être désynchronisé si saisie manuelle |
| Multi-emails du même Pionnier | Doublons par email | ❌ Pas de contrainte d'unicité email |
| Multi-comptes (nom proche) | "ALI HAMIDI" vs "ALI HAMISSI" | ❌ Aucun contrôle automatique |
| NS saisi 2× | Multi-générateurs OU erreur | ✅ Contrôle d'unicité côté Phase 2 |

## Contrôles recommandés (à mettre en place)

| Contrôle | Type | Priorité |
|---|---|---|
| Unicité email dans `01_Pionniers` | Validation backend + audit hebdomadaire | 🔴 |
| Format NS (regex) | Validation au moment de la saisie | 🔴 |
| Cohérence préfixe NS ↔ produit | Validation Phase 2 | 🟡 |
| Audit hebdomadaire orphelins (FK cassées) | Script automatique | 🟡 |
| Audit hebdomadaire doublons NS | Script automatique | 🟡 |
| Limite 100 Fondateurs | Script + alerte | 🟡 |

---

# 🚨 INCOHÉRENCES IDENTIFIÉES ENTRE LE MODÈLE MÉTIER & LE SHEET ACTUEL

| # | Problème | Cas concerné | Impact |
|---|---|---|---|
| 1 | 196 pionniers ont `statut="En attente"` au lieu de `"Pionnier"` | Tous | 🟡 Cosmétique, pas bloquant |
| 2 | Aucun contrôle d'unicité d'email | Cas 1, 2 | 🔴 Risque de doublons silencieux |
| 3 | Pas d'endpoint "Régénérer un Pionnier existant" | Cas 2 | 🟡 Workflow manuel obligatoire |
| 4 | Pas de workflow "Saisir mon NS" (à créer) | Cas 3 | 🔴 Bloque la complétion progressive |
| 5 | Espace Pionnier affiche 1 seule installation | Cas 4 | 🟡 OK aujourd'hui (1 install/pionnier dans 99% des cas) |
| 6 | Pas de gestion désinscription Ambassadeur | Cas 5 | 🟡 RGPD à vérifier |
| 7 | Pas de gestion démotion Super | Cas 6 | 🟢 Peu probable |
| 8 | Pas de limite côté backend pour Fondateurs (max 100) | Cas 7 | 🟡 Contrôle manuel pour l'instant |
| 9 | Structures B2B mélangées avec particuliers dans `01_Pionniers` | Tous | 🔴 À corriger (sortir 5-20 lignes) |
| 10 | 4 `#REF!` dans `02_Installations.pio_id` | Cas 1 | 🔴 Bloque le lookup pour 4 installs |
| 11 | 15 NS dans `01_Pionniers` absents de `02_Installations` | Cas 3 | 🟡 Incohérence de remplissage |

---

# 🔁 ADAPTATIONS NÉCESSAIRES AVANT MIGRATION ODOO

| # | Adaptation | Pourquoi | Quand |
|---|---|---|---|
| 1 | Stabiliser le schéma `01_Pionniers` (16 colonnes définitives) | Mapping clair vers `res.partner` | Avant export |
| 2 | Stabiliser le schéma `02_Installations` (11 colonnes définitives) | Mapping vers modèle custom Odoo | Avant export |
| 3 | Supprimer les onglets morts | Réduire le bruit | Phase 1 |
| 4 | Mettre en place contrôle unicité email | Cohérence base Pionnier | Phase 1 ou Phase 2 |
| 5 | Implémenter workflow "Saisir mon NS" | Compléter les fiches avant migration | Phase 2 |
| 6 | Sortir les 5-20 structures non-particulières de `01_Pionniers` | Périmètre clean | Phase 1 |
| 7 | Documenter la définition exacte d'un "Fondateur" | Migration fidèle vers Odoo | Avant export |
| 8 | Mettre en place les scripts d'export CSV Sheet → Odoo | Migration | Phase 4 |
| 9 | Définir la stratégie email (transactional vs RGPD) | Conformité | Avant ouverture publique |

---

# 📋 RÈGLES MÉTIER OFFICIELLES (à valider)

| # | Règle | Validation requise |
|---|---|---|
| R1 | Un Pionnier est exclusivement un particulier | ✅ Validée |
| R2 | Un Pionnier = 1 ligne dans `01_Pionniers` (jamais 2) | À confirmer |
| R3 | Un Pionnier peut posséder 1 à N générateurs | ✅ |
| R4 | Le `pio_id` est immuable une fois créé | ✅ |
| R5 | Le NS peut être ajouté/modifié après création | ✅ |
| R6 | Le statut Ambassadeur est volontaire et signé eIDAS | ✅ |
| R7 | Le statut Super Ambassadeur est décidé exclusivement par l'admin | ✅ |
| R8 | Le statut Fondateur est limité à 100 personnes | À confirmer |
| R9 | Les structures (B2B) sont hors périmètre du programme | ✅ |
| R10 | La date de garantie = `date_installation + garantie_mois` (depuis catalogue) | ✅ |
| R11 | Tout document généré est public sur GitHub Pages | À confirmer (RGPD) |
| R12 | Le mail est l'identifiant unique fonctionnel (peut être migré pour Odoo) | À valider |

---

# ✅ CONCLUSION

## Ce que ce rapport confirme

1. **Le modèle métier actuel est cohérent** dans son ensemble : 1 Pionnier (particulier) → N Installations → N Maintenances
2. **Les statuts (Fondateur / Ambassadeur / Super)** sont correctement supportés techniquement
3. **L'idempotence est garantie** sur les webhooks principaux

## Ce que ce rapport révèle d'incohérent

1. 🔴 **Aucun contrôle d'unicité email** → risque de doublons silencieux
2. 🔴 **Cas 2 (ancien client) non instrumenté** : pas d'endpoint pour régénérer un Pionnier existant
3. 🔴 **Cas 3 (saisie NS) non implémenté** : à concevoir en Phase 2
4. 🟡 **Cas 4 (multi-générateurs) partiellement supporté côté UI** : l'espace n'affiche qu'une install
5. 🟡 **Statut "Fondateur" sans contrôle de seuil** (max 100)
6. 🟡 **Aucun mécanisme RGPD** (désinscription Ambassadeur, droit à l'oubli)

## Ce qu'il faut prioriser

| Priorité | Action métier |
|---|---|
| 🥇 | Phase 1 (fiabiliser l'existant : statut, #REF!, doublons NS, retirer structures) |
| 🥈 | Implémenter contrôle d'unicité email |
| 🥉 | Implémenter Phase 2 (formulaire "Saisir mon NS") |
| 4 | Implémenter Cas 2 : endpoint régénération Pionnier existant |
| 5 | Documenter la définition formelle des Fondateurs |
| 6 | Implémenter affichage multi-générateurs sur l'espace |
| 7 | Préparer les scripts d'export Odoo |

---

**Aucune écriture effectuée.** Ce rapport est uniquement une analyse métier. À vous de valider chaque règle et d'arbitrer chaque incohérence.
