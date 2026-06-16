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

## Historique de la règle

- 16/06/2026 — Règle formalisée à la demande de l'utilisateur après constat que `append_row` empilait les nouvelles fiches en bas de la zone vide (lignes 198+ au lieu de 151+). Réordonnancement effectué et fonction utilitaire à intégrer dans `SheetsService`.
