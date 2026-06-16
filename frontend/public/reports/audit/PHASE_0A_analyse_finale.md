# PHASE 0A — RAPPORTS D'ANALYSE FINALE AVANT ÉCRITURE

*Aucune modification. Aucune suppression. Aucune correction.*
*Lecture seule uniquement.*

---

## 1. LES 4 ERREURS `#REF!` dans `02_Installations.pio_id`

| # | install_id | Ligne sheet | Col | Valeur actuelle | nom_client | NS | Produit | Date install |
|---|---|---|---|---|---|---|---|---|
| 1 | **INST-2109** | 111 | `pio_id` | `#REF!` | Mme BEL Stephanie | (vide) | G30 | (vide) |
| 2 | **INST-2120** | 122 | `pio_id` | `#REF!` | Mr BERNARDET | (vide) | G30 | (vide) |
| 3 | **INST-2148** | 150 | `pio_id` | `#REF!` | Bompoint | (vide) | G30 | (vide) |
| 4 | **INST-2149** | 151 | `pio_id` | `#REF!` | Garnier | `HR88C23GFR0419` | G30 | 01/11/2023 |

### Analyse cas par cas

#### INST-2109 — Mme BEL Stephanie
- **Valeur attendue** : `pio_id` pointant vers la fiche `Stephanie Bel`
- **Recherche dans `01_Pionniers`** : **PIO-1028 = Stephanie Bel** (présent)
- **Cause probable** : suppression manuelle ou réorganisation des lignes de `01_Pionniers` ayant cassé la formule de référence
- **Proposition** : remplacer `#REF!` par `PIO-1028`
- **Impact métier** : aucune install valide pour Stephanie Bel actuellement → après correction, ses 2 NS (`HR88C23EFR0082`, `HR88C23EFR0488`) seraient enfin liés
- **Risque** : 🟢 Lookup unique sans ambiguïté

#### INST-2120 — Mr BERNARDET
- **Valeur attendue** : `pio_id` de BERNARDET Didier
- **Recherche** : **PIO-1071 = Didier BERNARDET** (présent — séparé prénom/nom)
- **Cause probable** : Identique cas 1
- **Proposition** : remplacer par `PIO-1071`
- **Impact métier** : aucun NS rattaché à BERNARDET aujourd'hui → installation orpheline réparée
- **Risque** : 🟢

#### INST-2148 — Bompoint
- **Valeur attendue** : `pio_id` de Bompoint
- **Recherche** : **PIO-1116 = Arlette BOMPOINT** (présent, avec NS `HR88C23JFR0700`)
- **Cause probable** : Identique
- **Proposition** : remplacer par `PIO-1116`
- **Impact métier** : Arlette BOMPOINT a déjà une install — celle-ci serait donc une 2ᵉ install OU un doublon (vérifier ligne sheet 150 vs install existante)
- **Risque** : 🟡 Vérifier si vrai 2ᵉ générateur ou doublon — pas d'auto-correction

#### INST-2149 — Garnier
- **Valeur attendue** : `pio_id` de Garnier
- **Recherche** : **PIO-1128 = GARNIER** (présent — un acronyme MAJ sans prénom, classé "à confirmer")
- **NS connu** : `HR88C23GFR0419` (= le NS audité dans le rapport 1 comme "Mr GARNIER, typo HR88C23GRFR0419 normalisée")
- **Cause probable** : Identique
- **Proposition** : remplacer par `PIO-1128`
- **Impact métier** : ✅ install valide réintégrée, NS rattaché correctement
- **Risque** : 🟢

### Synthèse

| install_id | Action recommandée | Risque |
|---|---|---|
| INST-2109 | `pio_id = PIO-1028` | 🟢 |
| INST-2120 | `pio_id = PIO-1071` | 🟢 |
| INST-2148 | `pio_id = PIO-1116` après confirmation que ce n'est pas un doublon | 🟡 |
| INST-2149 | `pio_id = PIO-1128` | 🟢 |

**Aucune écriture proposée à ce stade — uniquement diagnostic.**

---

## 2. LES 3 DOUBLONS NS dans `01_Pionniers`

### Doublon 1 — `HR88C23EFR0120`

| Acteur | pio_id | Identité | Email |
|---|---|---|---|
| Pionnier A | **PIO-1029** | Jonathan Lacombe | jonathan.lacombe.90@gmail.com |
| Pionnier B | **PIO-1136** | Benoit VARLET | varlet.benoit@gmail.com |

- **Installation 02 trouvée** : `INST-2029` → rattachée à `PIO-1029` (Lacombe), nom_client = "Lacombe"
- **Maintenances** : 2 lignes liées à cette installation
- **Hypothèse** : cas du cluster Lacombe/VARLET du rapport SAV (rapport 7). L'installation est physiquement chez VARLET, mais l'installateur (Lacombe) a été indiqué dans `nom_client`. Le NS a probablement été dupliqué dans `01_Pionniers` lors du remplissage Phase 1.
- **Recommandation** :
  - **Conserver** le NS chez **PIO-1136 (Benoit VARLET)** s'il est bien le titulaire de l'installation
  - **Retirer** le NS de PIO-1029 (Lacombe) — c'est l'installateur, pas le client
  - **Vérifier** auprès de Bacar/Assani avant correction
- **Risque** : 🟡 Arbitrage humain obligatoire

### Doublon 2 — `HR88C23JFR0849`

| Acteur | pio_id | Identité | Email |
|---|---|---|---|
| Pionnier A | **PIO-1104** | Inchati MOUSSA | inchati.ti@gmail.com |
| Pionnier B | **PIO-1132** | Moussa RACHIDI | Moussa.rachidi@orange.fr |

- **Installation 02** : `INST-2103` → `PIO-1104` (Inchati MOUSSA), nom_client = "MOUSSA Inchati"
- **Maintenances** : 0
- **Hypothèse** : confusion entre "Moussa" (prénom de Inchati) et "Moussa Rachidi" (nom différent). Le NS a probablement été collé par erreur sur PIO-1132 lors du remplissage.
- **Recommandation** :
  - **Conserver** le NS chez **PIO-1104 Inchati MOUSSA** (cohérent avec `nom_client` et `install_id`)
  - **Retirer** le NS de PIO-1132 Moussa RACHIDI
- **Risque** : 🟢 Clair

### Doublon 3 — `HR88C23LFR1131`

| Acteur | pio_id | Identité | Email |
|---|---|---|---|
| Pionnier A | **PIO-1130** | Sylvain LE DU | ledusylvain@hotmail.fr |
| Pionnier B | **PIO-1152** | RAFFARD (sans prénom) | maxraf87@gmail.com |

- **Installation 02** : `INST-2151` → rattachée à `PIO-1152` (RAFFARD), nom_client = "RAFFARD"
- **Maintenances** : 0
- **Hypothèse** : confusion entre LE DU et RAFFARD lors du remplissage Phase 1
- **Recommandation** :
  - **Conserver** le NS chez **PIO-1152 RAFFARD** (cohérent avec `install_id`)
  - **Retirer** le NS de PIO-1130 LE DU
  - Confirmer en interrogeant le rapport SAV original
- **Risque** : 🟢 Clair sur la base de l'installation

### Synthèse doublons

| NS | À CONSERVER | À RETIRER | Maintenances impactées | Niveau de confiance |
|---|---|---|---|---|
| HR88C23EFR0120 | PIO-1136 (VARLET) | PIO-1029 (Lacombe) | 2 (à reverifier) | 🟡 |
| HR88C23JFR0849 | PIO-1104 (Inchati MOUSSA) | PIO-1132 (Moussa RACHIDI) | 0 | 🟢 |
| HR88C23LFR1131 | PIO-1152 (RAFFARD) | PIO-1130 (LE DU) | 0 | 🟢 |

---

## 3. LES 196 STATUTS `"En attente"`

### 3.1 Distribution

| Métrique | Valeur |
|---|---|
| Total `statut="En attente"` | **196** |
| Total `statut="Pionnier"` | **1** (PIO-1196 Sandrine MARTIN) |

### 3.2 Origine

| `source_creation` | Lignes |
|---|---|
| `Import` | **195** |
| (vide) | **1** |

→ **195/196 lignes ont été créées par un import historique** (l'onglet `Import` ou un script de migration manuel).

### 3.3 Date d'entrée

| | Valeur |
|---|---|
| `date_entree` renseignée | **0 / 196** (!) |
| Ces lignes n'ont aucune trace temporelle |

### 3.4 Comparaison avec `"Pionnier"`

| Pionnier ref | Champs présents |
|---|---|
| **PIO-1196** Sandrine MARTIN | `source_creation = "backend_livraison"`, `date_entree = "2026-06-15T09:07:30..."` |
| **195 imports** | `source_creation = "Import"`, `date_entree = vide` |

### 3.5 Usage du statut dans le code

| Valeur | Présence dans le code backend |
|---|---|
| `"En attente"` | ❌ **ZÉRO occurrence** — le code n'utilise jamais cette valeur en condition métier |
| `"Pionnier"` | ✅ 3 occurrences — toujours en écriture (lors de la création) : `server.py:614` et `server.py:1481` |

### 3.6 Conclusion

| Question | Réponse |
|---|---|
| Quelle règle a généré `"En attente"` ? | Une migration historique a importé 195 pionniers avec ce statut par défaut, sans `date_entree` |
| À quelle date ces lignes ont été créées ? | **Inconnue** — `date_entree` est vide partout |
| Ce statut est-il encore utilisé par le code ? | **Non** — le backend écrit uniquement `"Pionnier"` à la création |
| Différence métier entre les deux ? | **Aucune logique active** — la valeur n'est pas lue dans le code de production. Pure étiquette héritée de l'import |

**Recommandation** : la migration `"En attente"` → `"Pionnier"` est **techniquement sans risque** car aucun chemin de code ne dépend de la valeur. L'impact est uniquement visuel/cosmétique côté admin.

---

## 4. LES 17 STRUCTURES — ANALYSE D'IMPACT MÉTIER

### 4.1 Tableau de qualification

| pio_id | Nom | Catégorie | Insts | NS | Maints | Docs | Qualification proposée |
|---|---|---|---|---|---|---|---|
| **PIO-1012** | Hippocampe plongée | Entreprise | 1 (INST-2012) | `HR88C23JFR0266` | **1** | 0 | 🔴 **Structure confirmée** |
| **PIO-1014** | Atelier Mahorais d'architecture | Entreprise | 1 (INST-2014) | `HR88C23GFR070` | **5** | 0 | 🔴 **Structure confirmée** |
| **PIO-1017** | Patricia Marceaux | Administration | 1 (INST-2017) | (vide) | 0 | 0 | 🟡 **À confirmer** (nom de particulier, mais classée Administration ?) |
| **PIO-1018** | Association unono wa matso | Administration | 1 (INST-2018) | `HR88C23EFR0029` | **5** | 0 | 🔴 **Structure confirmée** |
| **PIO-1086** | Foundi distribution | Entreprise | 1 (INST-2085) | `HR88C23JFR0704` | **1** | 0 | 🔴 **Structure confirmée** |
| **PIO-1076** | CIRAD Antenne de Mayotte | Mot-clé | 1 (INST-2075) | `HR88C25DAZ0026` | **2** | 0 | 🔴 **Structure confirmée** (institut public) |
| **PIO-1078** | CRECHE Les enfants des Margouillats | Mot-clé | 1 (INST-2077) | `HR88C24AFR0089` | **2** | 0 | 🔴 **Structure confirmée** (crèche associative) |
| **PIO-1079** | Cabinet Infirmier Triquet François | Mot-clé | 1 (INST-2078) | `HR88C23GFR0414` | **3** | 0 | 🟡 **À confirmer** (profession libérale = particulier exerçant ?) |
| **PIO-1087** | France Alzheimer Mayotte | Mot-clé | 1 (INST-2086) | `HR88C23LFR1077` | **2** | 0 | 🔴 **Structure confirmée** (association) |
| **PIO-1091** | HELILAGON | Mot-clé | 1 (INST-2090) | (vide) | **3** | 0 | 🔴 **Structure confirmée** (compagnie hélicoptère) |
| **PIO-1106** | Mayotte Clotures et Jardins Fraisse | Mot-clé | 1 (INST-2105) | `HR88C23EFR003` | 0 | 0 | 🔴 **Structure confirmée** (entreprise) |
| **PIO-1135** | SARL VETO | Mot-clé | 1 (INST-2134) | (vide) | 0 | 0 | 🔴 **Structure confirmée** (SARL) |
| **PIO-1142** | ROCS | Mot-clé | 1 (INST-2141) | (vide) | 0 | 0 | 🔴 **Structure confirmée** (entreprise — vue dans le parc) |
| **PIO-1143** | SAS MATIS | Mot-clé | 1 (INST-2142) | (vide) | 0 | 0 | 🔴 **Structure confirmée** (SAS) |
| **PIO-1144** | SOS OXYGENE | Mot-clé | 1 (INST-2143) | (vide) | 0 | 0 | 🔴 **Structure confirmée** (entreprise médicale) |
| **PIO-1146** | Gaëlle TOURON | Mot-clé | 1 (INST-2145) | (vide) | 0 | 0 | 🟡 **À confirmer** — "TOURON" évoque la marque BAOBAB/TOURON mais "Gaëlle" peut être un prénom personnel |
| **PIO-1151** | Tetrama exploitation | Mot-clé | 1 (INST-2150) | `EA60L23JFR1010S` | 0 | 0 | 🔴 **Structure confirmée** (entreprise) |

### 4.2 Synthèse de qualification

| Qualification | Nombre | pio_id concernés |
|---|---|---|
| 🔴 **Structure confirmée** | **14** | 1012, 1014, 1018, 1086, 1076, 1078, 1087, 1091, 1106, 1135, 1142, 1143, 1144, 1151 |
| 🟡 **À confirmer** | **3** | 1017 (Patricia Marceaux), 1079 (Cabinet Infirmier), 1146 (Gaëlle TOURON) |
| ✅ Particulier confirmé | 0 dans ce lot | — |

### 4.3 Risques métier en cas de retrait

#### Risques techniques généraux
- ⚠️ **Toutes les 17 structures ont 1 installation** dans `02_Installations`
- ⚠️ **8 structures ont des maintenances** rattachées (total 24 maintenances) → retrait casserait l'historique SAV de ces 8 entités
- ✅ **Aucun document HTML** publié sur GitHub Pages pour ces 17 lignes (`06_Documents` vide)

#### Risques spécifiques

| Pionnier | Maintenances | Risque retrait |
|---|---|---|
| PIO-1014 Atelier Mahorais | 5 | 🟡 Perte historique 5 interventions |
| PIO-1018 Association unono | 5 | 🟡 Perte historique 5 interventions |
| PIO-1079 Cabinet Infirmier | 3 | 🟡 Perte historique 3 interventions |
| PIO-1091 HELILAGON | 3 | 🟡 Perte historique 3 interventions |
| PIO-1076 CIRAD | 2 | 🟡 |
| PIO-1078 CRECHE | 2 | 🟡 |
| PIO-1087 France Alzheimer | 2 | 🟡 |
| PIO-1012 Hippocampe plongée | 1 | 🟢 |
| PIO-1086 Foundi distribution | 1 | 🟢 |

#### Recommandation forte

**Ne PAS supprimer les lignes**. À la place :
- Marquer `statut = "Hors_perimetre_pionnier"` ou `"Structure"`
- Conserver `02_Installations` + `05_Maintenances` rattachées (intégrité historique préservée)
- L'app filtrera côté affichage si nécessaire
- Lors de la migration Odoo, ces lignes iront naturellement dans `res.partner` avec `is_company=True` (au lieu d'être perdues)

---

## 📋 SYNTHÈSE PHASE 0A

| Sujet | Risque | Décision recommandée |
|---|---|---|
| **4 `#REF!`** | 3🟢 + 1🟡 | Correction sûre pour 3 ; INST-2148 nécessite confirmation manuelle |
| **3 NS doublons** | 1🟡 + 2🟢 | Conserver 2 NS (PIO-1104, PIO-1152) ; arbitrer PIO-1029 vs PIO-1136 |
| **196 statuts "En attente"** | 🟢 | Renommage technique sans risque (zéro logique métier) |
| **17 structures** | 🟡 | Ne pas supprimer, marquer un nouveau statut, conserver les historiques |

📁 Données complètes : [`PHASE_0A_data.json`](https://pioneer-ecosystem.preview.emergentagent.com/reports/audit/PHASE_0A_data.json)

---

## ✅ Ce qui est AUTORISÉ après validation Phase 0A (= Phase 0B)

1. ✅ **Snapshot complet** des onglets (sauvegarde JSON intégrale)
2. ✅ **Vérification des dépendances backend** (tests pytest)
3. ✅ **Suppression de `03_Medias`** (zéro ligne, zéro référence code)
4. ✅ **Suppression de `07_Produits`** (zéro référence code détectée — le grep statique du Rapport 5 le confirme)

## ❌ Ce qui n'est PAS autorisé à ce stade

- ❌ Modification des statuts (`"En attente"` → `"Pionnier"`)
- ❌ Déplacement des structures
- ❌ Fusion de pionniers
- ❌ Correction des NS doublons
- ❌ Réassignation des pio_id (#REF!)

---

**Aucune écriture effectuée.** L'audit Phase 0A est complet.

**Votre prochaine décision** :
- a. ✅ Valider la Phase 0A et passer à la **Phase 0B** (snapshot + suppression `03_Medias` + `07_Produits` UNIQUEMENT)
- b. 🔍 Approfondir un point spécifique (un cas `#REF!`, un doublon, une structure ambiguë)
- c. ✏️ Arbitrer les 3 cas "À confirmer" des structures (PIO-1017, PIO-1079, PIO-1146)
