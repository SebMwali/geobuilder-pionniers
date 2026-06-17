# Règles d'écriture dans le Google Sheet — Geobuilder Pionniers

Document de référence pour tout ajout de données dans le sheet "La Famille des Pionniers".
**Toute écriture future DOIT respecter ces règles.**

---

## R1 — Ajout de nouvelles lignes

### ❌ Interdit
- Utiliser `worksheet.append_row()` qui empile en bas de toute la feuille (souvent au-delà de la zone formatée).

### ✅ Obligatoire
- Les nouvelles lignes (pionniers, installations, etc.) sont insérées **immédiatement à la suite de la dernière ligne pleine existante**, dans la zone déjà formatée (dropdowns, couleurs, polices).
- Utiliser `worksheet.update(range, values)` qui n'écrase QUE les valeurs (le formatage des cellules destination — dropdowns, couleurs — est conservé).

### Algorithme
```python
1. Lire toutes les valeurs de l'onglet : ws.get_all_values()
2. Trouver l'index de la dernière ligne où col A est non vide
3. Insérer les nouvelles valeurs à partir de (dernière_ligne + 1)
4. Utiliser update(range, values) — JAMAIS append_row()
```

---

## R2 — Mise en forme à préserver

Lors de toute écriture, **doivent être préservés** :
- Police et taille (Arial 10pt uniformisé au 16/06/2026 sur 01_Pionniers et 02_Installations)
- Couleurs de fond
- Bordures
- Dropdowns / data validation
- Gel des lignes ou colonnes
- Mise en forme conditionnelle

### Méthodes sûres
- `ws.update(range, values, value_input_option="USER_ENTERED")` → valeurs uniquement
- `ws.batch_clear([range])` → efface valeurs, garde formatage

### Méthodes à éviter
- `ws.append_row()` → ajoute sans formatage en fin de feuille
- `ws.clear()` → efface tout y compris formatage
- Suppression/réinsertion de lignes → perd dropdowns dans certains cas

---

## R3 — Mises à jour ciblées

Pour modifier une cellule unique :
- ✅ `ws.update_cell(row, col, value)` ou via `SheetsService.update_cell()`
- ✅ Préserve totalement le formatage

---

## R4 — Suppressions

- Supprimer une ligne avec `ws.delete_rows(i)` :
  - Décale toutes les lignes du dessous vers le haut
  - Le formatage suit les lignes (Google Sheets gère)
  - Les data validations conservent leur plage relative
  - ⚠️ Vérifier qu'aucune formule externe ne pointe sur la ligne supprimée (sinon `#REF!`)

---

## R5 — Idempotence

Tout script d'écriture doit être **idempotent** :
- Vérifier l'état actuel avant d'écrire
- Skip si la valeur cible est déjà présente
- Détecter les doublons par clé métier (NS, pio_id, install_id, email)

---

## R6 — Quotas API Google Sheets

- Limite : 60 reads/minute/user
- Stratégie : cache local en mémoire pour les lectures massives
- Pause 1.5-2s entre les writes consécutifs
- Retry exponentiel sur 429 (déjà implémenté dans `SheetsService`)

---

## R7 — Convention "à la suite" — Implementation

Pour respecter la R1, une fonction utilitaire est à utiliser :

```python
def append_in_formatted_zone(svc, tab_key, rows_data, n_cols):
    """Ajoute des lignes juste après la dernière ligne pleine,
    en préservant le formatage de la zone destination."""
    ws = svc.get_worksheet(tab_key)
    all_vals = ws.get_all_values()
    last_filled = max(i for i, r in enumerate(all_vals, 1) if r and r[0].strip())
    start = last_filled + 1
    end = start + len(rows_data) - 1
    end_col = chr(ord('A') + n_cols - 1)
    dest = f"A{start}:{end_col}{end}"
    padded = [(r + [""] * n_cols)[:n_cols] for r in rows_data]
    ws.update(dest, padded, value_input_option="USER_ENTERED")
```

---

## R8 — Sémantique des recommandations utilisateur

Quand l'utilisateur fournit une **liste de recommandations** ou de **suggestions**
(ex: "Sandrine conseille ces personnes pour les fondateurs"), c'est **toujours
un AJOUT à l'existant**, **JAMAIS un remplacement**.

### ❌ Mauvaise interprétation (à ne JAMAIS faire)
- Synchroniser strictement = effacer ce qui n'est pas dans la liste
- "Liste cible" = "remplace tout"

### ✅ Bonne interprétation
- Liste fournie par utilisateur = **delta à ajouter** sur la base existante
- Toute suppression doit être **explicite** ("supprime X", "exclus Y", "décoche Z")
- En cas de doute → demander confirmation avant suppression

### Origine de la règle
- 16/06/2026 — Erreur : décochage de 62 fondateurs préexistants quand Sandrine
  voulait juste ajouter 23 nouvelles personnes. Rectifié immédiatement.


---

## R9 — JAMAIS de formule sur les colonnes `pio_id` et `install_id`

### ❌ Interdit
- Utiliser une formule type `="INST-"&(ROW()+1998)` ou `=PIO-` + ROW() pour générer les IDs.
- Pourquoi ? Toute suppression de ligne au-dessus **décale la formule** et change l'install_id /
  pio_id de toutes les lignes en-dessous. Conséquence : désalignement sheet ↔ fichiers GH Pages.

### ✅ Obligatoire
- Les colonnes `pio_id` (01_Pionniers) et `install_id` (02_Installations) doivent contenir
  des **valeurs statiques** (strings simples, type "INST-2147").
- Le compteur est géré centralement via `services/counter_service.py` qui lit/écrit
  dans `04_Parametres` avec un Lock thread-safe.
- Pour figer une colonne en formule existante en valeur statique :
  utiliser le script `/app/backend/scripts/freeze_install_ids.py`.

### Origine
- 17/06/2026 — Suite à la suppression de 6 lignes du Groupe B (PIO-1012, 1057, 1070,
  1076, 1078, 1086), les install_ids de 142 pionniers se sont décalés (effet domino
  des formules), désalignant la sheet de tous les fichiers HTML existants sur GH Pages.
  Fix : script `freeze_install_ids.py` qui restaure les install_id ORIGINAUX
  (pré-suppression) en valeurs statiques.


---

## R10 — Idempotence du webhook livraison

### Règle
Le webhook `POST /api/webhook/livraison` est **idempotent** sur 2 champs :
1. **Primary** : `report_id` (col W de 02_Installations) → si déjà présent, retour HTTP 200
   avec les URLs existantes (pas de duplicate).
2. **Secondary** : `numero_serie` → si déjà présent dans 02_Installations, retour idempotent
   également (au cas où le SAV oublierait `report_id`).

### Validation forte du payload
- `email` doit matcher `^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$` (ou liste séparée par `;`/`,`)
- `telephone` doit matcher `^[+0-9\s().-]{6,30}$` (si présent)
- Toute violation → HTTP 422 avec message explicite

### Origine
- 17/06/2026 — Renforcement post-audit : ajout idempotence numero_serie + validation email/phone
  pour éviter les anomalies type `;+262...` ou `07 70 / +33...` qui sont passées en base
  pendant la phase d'import historique de Mayotte.


---

## Historique de la règle

- 16/06/2026 — Règle formalisée à la demande de l'utilisateur après constat que `append_row` empilait les nouvelles fiches en bas de la zone vide (lignes 198+ au lieu de 151+). Réordonnancement effectué et fonction utilitaire à intégrer dans `SheetsService`.
