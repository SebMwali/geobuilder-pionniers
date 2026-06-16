# RAPPORT 4 — LISTE EXHAUSTIVE DES ACTIONS & IMPACTS

*Toutes les actions sont conditionnelles à votre validation explicite étape par étape.*

---

## Légende des impacts

| Symbole | Sens |
|---|---|
| 🟢 | Aucun impact utilisateur visible |
| 🟡 | Impact mineur (admin uniquement) |
| 🔴 | Impact visible (espace pionnier, email, GitHub Pages) |
| 🔒 | Réversible immédiat (snapshot disponible) |
| ⛔ | Irréversible sans recréation manuelle |

---

## TABLEAU MAÎTRE — TOUTES LES ACTIONS

### Étape 0 — Préparation

| # | Action | Impact | Réversible | Validation |
|---|---|---|---|---|
| 0.1 | Snapshot JSON des 11 onglets | 🟢 | — | À demander |
| 0.2 | Tag git pré-migration | 🟢 | — | À demander |
| 0.3 | Vérification accès Sheets/GitHub/Resend | 🟢 | — | À demander |

---

### Étape 1 — Nettoyage onglets morts

| # | Action | Onglet | Impact | Réversible |
|---|---|---|---|---|
| 1.1 | Export CSV puis suppression | `03_Medias` | 🟢 (vide) | 🔒 (CSV) |
| 1.2 | Export CSV puis suppression | `07_Produits` | 🟢 (non lu par code) | 🔒 |
| 1.3 | Suppression de l'onglet | `00_Fondateurs` | 🟡 (perte données de travail) | 🔒 |
| 1.4 | Suppression de l'onglet | `Import` | 🟡 | 🔒 |

**Impact backend** : aucun (aucun code ne lit ces onglets).
**Impact frontend** : aucun (UI sur GitHub Pages).

---

### Étape 2 — Correction `#REF!` et orphelins

| # | Action | Cible | Impact | Validation |
|---|---|---|---|---|
| 2.1 | Demander pio_id correct pour INST-2109 | 02_Installations | 🟡 | **À demander cas par cas** |
| 2.2 | Idem INST-2120 | 02 | 🟡 | À demander |
| 2.3 | Idem INST-2148 | 02 | 🟡 | À demander |
| 2.4 | Idem INST-2149 | 02 | 🟡 | À demander |
| 2.5 | Résoudre les 5 installations avec pio_id inexistant | 02 | 🟡 | À demander |
| 2.6 | Résoudre les 3 maintenances avec install_id inexistant | 05 | 🟡 | À demander |
| 2.7 | Résoudre la 1 maintenance avec pio_id inexistant | 05 | 🟡 | À demander |

**Impact backend** : si un pio_id corrigé est ré-attribué, l'espace pionnier ne devra pas être régénéré sauf demande (les fichiers GitHub Pages utilisent install_id, pas pio_id directement).

---

### Étape 3 — Normalisation `01_Pionniers`

| # | Action | Lignes | Impact | Réversible |
|---|---|---|---|---|
| 3.1 | Changer `statut` "En attente" → "Pionnier" | 196 | 🟡 (admin uniquement) | 🔒 |
| 3.2 | MAJUSCULES sur `nom` des 33 DEJA_SEPARE | 33 | 🟡 | 🔒 |
| 3.3 | Dédoublonner les 3 NS doublons (HR88C23EFR0120, HR88C23JFR0849, HR88C23LFR1131) | 3 lignes | 🟡 | 🔒 |
| 3.4 | Marquer `source_creation = "import_2026"` pour les pionniers existants sans source | ~150 | 🟢 | 🔒 |

**Impact backend** : aucun (statut n'est pas utilisé en condition métier).

---

### Étape 4 — Création `09_Clients_B2B`

| # | Action | Volume | Impact | Réversible |
|---|---|---|---|---|
| 4.1 | Créer l'onglet `09_Clients_B2B` | 1 onglet | 🟢 | 🔒 |
| 4.2 | Ajouter compteur dans `04_Parametres` | 1 cellule | 🟢 | 🔒 |
| 4.3 | Lister les structures dans `01_Pionniers` actuelles | ~5-20 | 🟡 (rapport) | — |
| 4.4 | Déplacer les structures `01 → 09` (INSERT 09, DELETE 01) | ~5-20 | 🔴 (changement de pio_id) | 🔒 |
| 4.5 | Créer 130 nouvelles structures B2B depuis le parc | 130 | 🟡 | 🔒 |
| 4.6 | Ajouter colonne `client_b2b_id` à `02_Installations` | 1 colonne | 🟢 | 🔒 |
| 4.7 | Pour chaque installation appartenant à une structure : remplacer `pio_id` par `client_b2b_id` | ~30-50 | 🟡 | 🔒 |

**Impact backend** : 🔴 si une structure avait un espace pionnier publié, il faudra :
- Soit supprimer l'espace publié
- Soit créer une variante "espace client B2B" simplifiée
**Décision à prendre** avec vous.

**Impact frontend** : 🔴 les URLs `/pionniers/{pio_id}/` des structures déjà publiées deviendraient orphelines.

---

### Étape 5 — Création `03_Ambassadeurs`

| # | Action | Volume | Impact | Réversible |
|---|---|---|---|---|
| 5.1 | Renommer `03_Medias` → `03_Ambassadeurs` | 1 onglet | 🟢 (était vide) | 🔒 |
| 5.2 | Recréer les colonnes selon Rapport 2 | 13 colonnes | 🟢 | 🔒 |
| 5.3 | Migrer signatures depuis `08_Automations_Log` | 1-N | 🟡 | 🔒 |
| 5.4 | Déplacer `droit_image / temoignage / visite` de 01 vers 03 | 197 lignes lues | 🟡 | 🔒 |
| 5.5 | Modifier code `/api/ambassadeur/signature` | code | 🟡 (besoin nouveau déploiement) | 🔒 (git revert) |

**Impact backend** : 🟡 modif code, mais signature continue de marcher.

---

### Étape 6 — Import du parc complet dans `02_Installations`

| # | Action | Volume | Impact | Réversible |
|---|---|---|---|---|
| 6.1 | Corriger les 8 NS suspects (typos) | 8 | 🟡 (besoin votre arbitrage) | 🔒 |
| 6.2 | INSERT 450 nouvelles installations | 450 lignes | 🔴 | 🔒 (filtre par `source_creation`) |
| 6.3 | Pour chaque install particulier sans match nom → créer le pionnier | ~10-15 nouveaux PIO | 🔴 | 🔒 |
| 6.4 | Mettre à jour `01_Pionniers.NS` pour refléter les nouvelles installations | ~80 lignes | 🟡 | 🔒 |

**Impact backend** : ⚠️ ralentissement temporaire des lectures (sheets plus gros).
**Impact frontend** : 🟢 (rien n'est publié sur GitHub Pages tant que vous ne déclenchez pas la génération).

---

### Étape 7 — Import historique SAV

| # | Action | Volume | Impact | Réversible |
|---|---|---|---|---|
| 7.1 | INSERT 91 lignes Lot A dans `05_Maintenances` | 91 | 🟡 | 🔒 (filtre par `source`) |
| 7.2 | Skip 16 lignes Lot B (en attente arbitrage) | 0 | 🟢 | — |
| 7.3 | Flag les lignes avec `date_intervention` non-date en `statut = "A_PLANIFIER"` | 7 | 🟢 | 🔒 |

**Impact backend** : 🟢 (lecture seule côté front, historique enrichi côté admin).

---

### Étape 8 — Mise à jour code backend

| # | Action | Fichier | Impact | Réversible |
|---|---|---|---|---|
| 8.1 | Modifier webhook LIVRAISON pour router particulier vs B2B | `server.py` | 🔴 (nouveau code en prod) | 🔒 (git) |
| 8.2 | Modifier webhook SAV pour gérer B2B | `server.py` | 🔴 | 🔒 |
| 8.3 | Modifier `/api/ambassadeur/signature` pour écrire dans `03_Ambassadeurs` | `server.py` | 🔴 | 🔒 |
| 8.4 | Ajouter compteurs `client_b2b_id`, `signature_id` dans `04_Parametres` | code + sheet | 🟡 | 🔒 |
| 8.5 | Ajouter `templates/portail_b2b.html` (espace client B2B simplifié) | nouveau | 🟢 | 🔒 |
| 8.6 | Mettre à jour les fixtures de tests | `tests/` | 🟢 | 🔒 |
| 8.7 | Lancer suite complète tests | — | 🟢 | — |
| 8.8 | Déploiement | — | 🔴 | 🔒 |

---

## 📊 Estimation des volumes finaux

| Onglet | Avant | Après migration | Variation |
|---|---|---|---|
| 00_Fondateurs | 138 | **0 (supprimé)** | ⬇️ |
| 01_Pionniers | 150 remplies | ~85-100 (purement particuliers) | ⬇️ ~30% |
| 02_Installations | 156 remplies | **~511** (parc complet) | ⬆️ ×3.3 |
| 03_Medias → 03_Ambassadeurs | 0 | 1-5 (signatures actuelles) | ⬆️ |
| 04_Parametres | 15 | 17 (+2 compteurs) | ⬆️ |
| 05_Maintenances | 126 | ~217 (+91 historique) | ⬆️ ×1.7 |
| 06_Documents | 5 | ~5 (intacte sauf si régen) | = |
| 07_Catalog | 9 | 9 | = |
| 07_Produits | 7 | **0 (supprimé)** | ⬇️ |
| 08_Automations_Log | 7 | ~120+ (logs migration) | ⬆️ |
| 09_Clients_B2B (nouveau) | — | **~130-140** | nouveau |
| Import | 118 | **0 (supprimé)** | ⬇️ |

**Total onglets** : 11 → **10** (suppression nette de 4, création nette de 1 + renommage 1).

---

## ⚠️ Risques identifiés

| Risque | Probabilité | Sévérité | Mitigation |
|---|---|---|---|
| Erreur de classification particulier/B2B | Moyenne | Moyen | Validation cas par cas étape 4 |
| Doublon NS lors de l'import parc | Faible | Élevé | Pré-vérification + idempotence |
| Pio_id collision (multi-générateurs) | Faible | Moyen | Logique 1 pionnier = N installations |
| Email envoyés en double si re-import | Faible | Faible | Pas d'envoi auto lors de l'import |
| GitHub Pages cassé si refactor | Moyenne | Élevé | Pas de régen massive sans demande |
| Tests backend cassés | Faible | Élevé | Lancer tests après chaque étape |
| Espace pionnier B2B inadapté | Élevée | Moyen | Créer template `portail_b2b.html` simplifié |
| Confusion utilisateur sur les statuts | Moyenne | Faible | Documenter dans `/app/memory/PRD.md` |

---

## ✋ Points de validation obligatoires AVANT exécution

1. ✅ **Étape 1** (suppression onglets morts) : confirmer 03_Medias, 07_Produits, 00_Fondateurs, Import bien archivés
2. ✅ **Étape 2** (orphelins/REF) : arbitrer cas par cas — 8 décisions au minimum
3. ✅ **Étape 3** (normalisation) : confirmer changement statut "En attente" → "Pionnier"
4. ✅ **Étape 4** (B2B) : VALIDER LA LISTE complète des 130 structures B2B AVANT déplacement (rapport CSV)
5. ✅ **Étape 5** (Ambassadeurs) : confirmer migration des flags droit_image
6. ✅ **Étape 6** (parc) : VALIDER LA CORRECTION DES 8 TYPOS NS + LA LISTE DES 10-15 NOUVEAUX PIONNIERS
7. ✅ **Étape 7** (SAV) : confirmer périmètre Lot A
8. ✅ **Étape 8** (code) : valider après tests

---

## 🎁 Bonus — Quick wins possibles AVANT migration

Si vous voulez voir des résultats immédiats sans déclencher la migration complète, vous pouvez valider isolément :

| Quick win | Effort | Impact | Réversible |
|---|---|---|---|
| Corriger les 4 `#REF!` dans 02_Installations | 5 min | 🟢 | 🔒 |
| Renommer statut "En attente" → "Pionnier" sur 196 lignes | 5 min | 🟡 | 🔒 |
| Dédoublonner les 3 NS doublons dans 01_Pionniers | 5 min | 🟡 | 🔒 |
| Supprimer onglets morts (03_Medias, 07_Produits) | 5 min | 🟢 | 🔒 |

Ces 4 actions sont **indépendantes** et peuvent être faites avant ou pendant la migration.

---

## 📥 Récapitulatif des livrables disponibles

| Document | Statut | Lien |
|---|---|---|
| RAPPORT 1 — Audit existant | ✅ Produit | `RAPPORT_1_audit_existant.md` |
| RAPPORT 2 — Architecture cible | ✅ Produit | `RAPPORT_2_architecture_cible.md` |
| RAPPORT 3 — Plan migration | ✅ Produit | `RAPPORT_3_plan_migration.md` |
| RAPPORT 4 — Actions & impacts | ✅ Produit | `RAPPORT_4_actions_impacts.md` |
| Annexes JSON | ✅ Produites | `01_cartographie.json`, `02_relations.json` |

---

## 🚦 État d'avancement

| Phase | Statut |
|---|---|
| Audit existant | ✅ **Terminé** |
| Architecture cible | ✅ **Proposée — à valider** |
| Plan migration | ✅ **Proposé — à valider** |
| Actions détaillées | ✅ **Listées — à valider** |
| **Exécution** | ⏸️ **EN ATTENTE DE VALIDATION** |

**Aucune écriture n'a été effectuée.**
**L'audit reste 100 % en lecture seule jusqu'à votre validation.**
