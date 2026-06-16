# LOT 2 — COLLECTE DES NS VIA APPLICATION
## Spécification fonctionnelle et technique prête à développer

---

## 1. UX/UI complète

### 1.1 Emplacement dans l'Espace Pionnier

**Page** : `portail_pionnier.html` (URL : `/pionniers/{pio_id}/index.html`)

**Insertion** : Nouvelle carte **"Identifier mon générateur"** placée **immédiatement sous la carte "Mon installation"**, à un emplacement haute visibilité.

**Conditions d'affichage** :
- Visible **uniquement** si au moins une installation du Pionnier a `numero_serie` vide OU `source_creation != "ns_via_app_valide"`
- Sinon, remplacée par une carte "Mon équipement identifié" en mode "success" (badge ✓)

### 1.2 Écrans

#### Écran A — Carte d'invitation (sur l'espace pionnier)
```
┌────────────────────────────────────────────────┐
│  📷 Identifier mon générateur                  │
│                                                │
│  Aidez-nous à améliorer le suivi de votre      │
│  équipement, garantie et historique de         │
│  maintenance.                                  │
│                                                │
│  [ Renseigner mon N° de série → ]              │
└────────────────────────────────────────────────┘
```

#### Écran B — Formulaire (page dédiée)
URL : `/pionniers/{pio_id}/identifier-generateur.html`

```
Identifier mon générateur

▼ Quelle installation concerne ce numéro de série ?
  ○ Installation du 15/06/2023 — G30 (sans NS)
  ○ Installation du 03/12/2024 — G30 (sans NS)
  [si une seule install : sélectionnée auto, non affichée]

▼ Numéro de série du générateur *
  [____________________]
  ⓘ Le NS est inscrit sur l'étiquette à l'arrière du générateur.
     Format type : HR88C23EFR0080

▼ Photo de l'étiquette du NS * (obligatoire si NS non reconnu)
  [📷 Prendre une photo / Choisir un fichier]

▼ Photo du générateur installé (facultatif)
  [📷 Prendre une photo / Choisir un fichier]

[ Envoyer ma déclaration ]
```

#### Écran C — Confirmation
```
✅ Merci !
Votre déclaration a bien été enregistrée.
Elle sera vérifiée par notre équipe sous 48h.
Vous recevrez un email de confirmation dès qu'elle sera validée.

[ Retour à mon espace ]
```

#### Écran D — État "En attente de validation"
La carte d'invitation devient :
```
┌────────────────────────────────────────────────┐
│  ⏱ Déclaration en cours de vérification        │
│  NS soumis le 15/02/2026                       │
│  En attente de validation Geobuilder           │
└────────────────────────────────────────────────┘
```

#### Écran E — État "Validé"
```
┌────────────────────────────────────────────────┐
│  ✓ Mon générateur identifié                    │
│  N° de série : HR88C23EFR0080                  │
│  Validé le 17/02/2026                          │
└────────────────────────────────────────────────┘
```

#### Écran F — État "Refusé"
```
┌────────────────────────────────────────────────┐
│  ⚠ Déclaration à corriger                      │
│  Motif : Le NS saisi ne correspond pas à       │
│  votre produit. Veuillez vérifier l'étiquette. │
│                                                │
│  [ Refaire ma déclaration ]                    │
└────────────────────────────────────────────────┘
```

### 1.3 Messages d'erreur (validation front)

| Cas | Message |
|---|---|
| NS vide | "Veuillez saisir le numéro de série." |
| NS mauvais format | "Format incorrect. Le NS commence par HR88, EA60, ZL9510W ou HR90." |
| NS trop court | "Le numéro de série semble incomplet." |
| Photo > 5 Mo | "La photo dépasse 5 Mo. Veuillez la compresser." |
| Format photo invalide | "Seuls les formats JPG, PNG, HEIC sont acceptés." |

### 1.4 Messages de validation (front)

| Action | Message |
|---|---|
| Envoi en cours | Spinner + "Envoi en cours…" |
| Envoi réussi | Toast vert "Déclaration enregistrée. Merci !" + redirection écran C |
| Erreur réseau | Toast rouge "Erreur réseau. Veuillez réessayer." |

### 1.5 Responsive mobile

- Champs en pleine largeur sur écrans < 768 px
- Bouton photo : déclenche directement l'appareil photo natif via `capture="environment"` sur input file
- Boutons "Envoyer" en sticky bottom sur mobile
- Champ NS avec clavier en majuscules (`autocapitalize="characters"`)

---

## 2. Architecture backend

### 2.1 Endpoints à créer

#### `POST /api/pionnier/saisir-ns`
**Authentification** : aucune (URL signée via `pio_id` dans l'URL — pas idéal mais cohérent avec l'existant)

**Payload** :
```json
{
  "pio_id": "PIO-1042",
  "install_id": "INST-2042",
  "numero_serie": "HR88C23EFR0080",
  "photo_etiquette_base64": "data:image/jpeg;base64,...",
  "photo_generateur_base64": "data:image/jpeg;base64,..."  // optionnel
}
```

**Réponses** :
- `201 Created` : `{ "demande_id": "NSD-001", "statut": "pending_validation" }`
- `400 Bad Request` : `{ "error": "Format NS invalide" }`
- `409 Conflict` : `{ "error": "Ce NS est déjà attribué", "details": {...} }`
- `422 Unprocessable` : `{ "error": "Préfixe NS incompatible avec le produit" }`

#### `GET /api/pionnier/{pio_id}/ns-status`
**But** : front interroge l'état de la déclaration pour afficher écran D/E/F

**Réponse** :
```json
{
  "installations": [
    {
      "install_id": "INST-2042",
      "produit": "G30",
      "date_installation": "2023-06-15",
      "numero_serie": "HR88C23EFR0080",
      "ns_status": "validated"  // ou "pending" / "rejected" / "missing"
    }
  ]
}
```

#### `GET /api/admin/ns-pending`
**Auth** : admin (header `X-Admin-Token`)
**Retourne** : toutes les demandes en attente

#### `POST /api/admin/ns-validate/{demande_id}`
**Payload** :
```json
{ "action": "validate" }  // ou "reject"
{ "action": "reject", "motif": "Photo illisible" }
```

### 2.2 Modèles de données

#### Nouvelle ressource : `10_NS_Declarations` (nouvel onglet)
| Colonne | Type | Note |
|---|---|---|
| `demande_id` | PK auto-incrément | `NSD-001` |
| `pio_id` | FK → 01 | |
| `install_id` | FK → 02 | |
| `numero_serie_declare` | TEXT | |
| `photo_etiquette_url` | URL GitHub | |
| `photo_generateur_url` | URL GitHub | |
| `date_soumission` | ISO 8601 | |
| `ip_soumission` | TEXT | |
| `statut` | enum | `pending` / `validated` / `rejected` |
| `validateur` | TEXT | qui a validé |
| `date_validation` | ISO | |
| `motif_refus` | TEXT | si rejet |

### 2.3 Validations backend (par ordre)

1. **Format NS** : regex `^(HR88C\d{2}[A-Z]+\d+|EA\d+L\d+[A-Z]+\d+S?|ZL\d+W\d+[A-Z]+\d+S?|HR90[A-Z0-9]+|EA\d+E\d+[A-Z]+\d+S?)$`
2. **Cohérence produit ↔ préfixe** : mapping `{ "G30": ["HR88"], "Ocean 500": ["EA60", "EA60L"], "Ocean 1000": ["EA100"] }` — si mismatch → 422
3. **Unicité NS** : vérification dans `02_Installations.numero_serie` + dans `10_NS_Declarations` (pending non encore rejetées) → conflit = 409
4. **Existence pio_id + install_id** : la combinaison doit être valide → 404 sinon
5. **Photo obligatoire** : si NS jamais vu et pas de match catalogue → photo obligatoire → 422 sinon
6. **Taille photo** : ≤ 5 Mo
7. **Rate limiting** : max 5 tentatives/heure par `pio_id`

### 2.4 Workflow d'approbation

```
Pionnier soumet
    ↓
Backend valide format/unicité/cohérence
    ↓
[OK] → INSERT 10_NS_Declarations (statut=pending)
    ↓ Upload photos sur GitHub Pages (/uploads/ns-declarations/{demande_id}/)
    ↓ LOG 08_Automations_Log (action=ns_declaration_pending)
    ↓ Email admin "Nouvelle déclaration NS"
    ↓
Admin reçoit notification et accède à /api/admin/ns-pending
    ↓
Admin valide ou rejette
    ↓
[VALIDATE] → Update 02_Installations.numero_serie + photo
           → Update 10_NS_Declarations.statut = validated
           → Régénération Passeport + Espace pionnier
           → LOG 08_Automations_Log
           → Email Pionnier "NS validé"
[REJECT]  → Update 10_NS_Declarations.statut = rejected + motif
          → LOG 08_Automations_Log
          → Email Pionnier "NS à corriger"
```

---

## 3. Workflow de validation Geobuilder

### 3.1 Où arrivent les demandes ?

- **Stockage** : onglet `10_NS_Declarations`
- **Notification** : email automatique à `admin@geobuilder.fr` (configurable) à chaque soumission
- **Console admin** : URL dédiée `/admin/ns-pending.html` (nouvelle interface Web — peut être un endpoint backend qui renvoie un HTML simple OU une page React si vous voulez)

### 3.2 Comment sont-elles validées ?

L'admin (vous ou un délégué) :
1. Ouvre `/admin/ns-pending.html`
2. Voit la liste des demandes en attente avec : photo étiquette, photo générateur, NS déclaré, identité Pionnier
3. Compare visuellement la photo et le NS
4. Clique sur **Valider** → trigger `POST /api/admin/ns-validate/{id}` avec `action=validate`
5. Ou clique sur **Refuser** → saisit un motif, trigger même endpoint avec `action=reject`

### 3.3 Comment sont-elles refusées ?

Motifs standardisés (radio button + champ libre) :
- "Photo illisible"
- "NS ne correspond pas à l'étiquette"
- "Préfixe NS incompatible avec le produit"
- "NS déjà attribué à un autre pionnier"
- "Autre" (champ libre)

### 3.4 Historisation

**Toutes les opérations** sont tracées :
- Dans `10_NS_Declarations` (statut + motif + date_validation + validateur)
- Dans `08_Automations_Log` (1 ligne par event : `ns_declaration_pending`, `ns_validated`, `ns_rejected`)
- Snapshot des photos conservé sur GitHub Pages (jamais supprimé même après rejet)

---

## 4. Impacts sur les onglets existants

### 4.1 Nouveau onglet `10_NS_Declarations`
À créer dans le Sheet. Schéma cf. §2.2.

### 4.2 `01_Pionniers`
**Aucune colonne ajoutée**. Les NS continuent d'exister uniquement dans `02_Installations`.

### 4.3 `02_Installations`
**1 colonne à ajouter** : `source_ns` (TEXT) — valeur `"webhook_livraison"` (legacy) ou `"ns_via_app"` (nouveau)
**Mise à jour à la validation** : `numero_serie`, `source_ns`, `photo_generateur_url` (si photo générateur fournie)

### 4.4 `06_Documents`
**Aucun impact direct**. À la régénération post-validation, la ligne Passeport est mise à jour (`date_generation` rafraîchie).

### 4.5 `08_Automations_Log`
**Nouveaux types d'actions** :
- `ns_declaration_submitted` (pionnier)
- `ns_declaration_validated` (admin)
- `ns_declaration_rejected` (admin)
- `ns_regeneration_passeport` (post-validation)

### 4.6 `04_Parametres`
**1 compteur à ajouter** : `demande_id` (séquence pour `NSD-001`, `NSD-002`, etc.)

---

## 5. Régénération automatique post-validation

### 5.1 Séquence

```python
def on_ns_validation_success(demande_id):
    decl = read_declaration(demande_id)
    install = read_installation(decl.install_id)
    
    # 1. Update installation
    update_installation(
        install_id=decl.install_id,
        numero_serie=decl.numero_serie_declare,
        source_ns="ns_via_app",
        photo_generateur_url=decl.photo_generateur_url or install.photo_generateur_url
    )
    
    # 2. Update declaration
    update_declaration(
        demande_id=demande_id,
        statut="validated",
        date_validation=now_utc(),
        validateur=admin_email
    )
    
    # 3. Régénérer Passeport (avec NS affiché)
    regenerate_passeport(install_id=decl.install_id)
    
    # 4. Régénérer Portail (carte "Mon installation" mise à jour)
    regenerate_portail(pio_id=decl.pio_id)
    
    # 5. Push GitHub Pages (les 2 HTML modifiés)
    push_github_pages([passeport_path, portail_path])
    
    # 6. Log
    log_event("ns_declaration_validated", pio_id=decl.pio_id, install_id=decl.install_id)
    log_event("ns_regeneration_passeport", pio_id=decl.pio_id)
    
    # 7. Email Pionnier
    send_email_ns_validated(decl.pio_id)
```

### 5.2 Mise à jour pionnier

Pas de modification de `01_Pionniers` directement. L'enrichissement passe par `02_Installations.numero_serie` qui sera lu lors de la prochaine génération.

---

## 6. Sécurité

### 6.1 Contrôle de format NS
- Regex stricte (voir §2.3)
- Côté front ET côté back

### 6.2 Détection des doublons
- Vérification d'unicité côté backend avant insertion en `pending`
- Vérification également contre les autres `pending` non rejetées
- Si conflit → `409 Conflict` avec le `pio_id` propriétaire actuel masqué (raisons RGPD)

### 6.3 Conflit de propriété
- Si 2 pionniers déclarent le même NS dans une fenêtre de 48h → la deuxième déclaration est mise en `pending_conflict`
- L'admin doit arbitrer manuellement
- Aucune attribution automatique

### 6.4 Validation humaine obligatoire
- **Aucune écriture automatique** dans `02_Installations.numero_serie` sans validation admin
- Photos conservées même après rejet (preuve)
- Audit complet dans `08_Automations_Log`

### 6.5 Rate limiting
- 5 soumissions max par heure par `pio_id`
- 1 soumission max par heure par même NS

### 6.6 Stockage photos
- Upload sur GitHub Pages dans `/uploads/ns-declarations/{demande_id}/`
- Format : `etiquette.jpg`, `generateur.jpg`
- Visibilité : URLs publiques mais non indexées (robots.txt)

---

## 📦 Livrables pour le développement

| Composant | Fichier(s) à créer | Effort estimé |
|---|---|---|
| Onglet `10_NS_Declarations` | Création manuelle dans Sheet | 5 min |
| Colonne `source_ns` dans `02_Installations` | Ajout manuel | 2 min |
| Compteur `demande_id` dans `04_Parametres` | Ajout manuel | 2 min |
| Template HTML formulaire | `/app/backend/templates/identifier_generateur.html` | 0.5 j |
| Endpoint POST saisir-ns | `/app/backend/server.py` | 0.5 j |
| Endpoint GET ns-status | `/app/backend/server.py` | 0.5 j |
| Endpoint admin list + validate | `/app/backend/server.py` | 0.5 j |
| Page admin HTML | `/app/backend/templates/admin_ns_pending.html` | 0.5 j |
| Logique de régénération | `/app/backend/services/regen.py` | 0.5 j |
| Adaptation `portail_pionnier.html` (carte) | Existant à modifier | 0.5 j |
| Tests pytest | `/app/backend/tests/test_ns_*.py` | 0.5 j |
| Email templates (3) | `/app/backend/templates/emails/ns_*.html` | 0.5 j |

**Total estimé : 4-5 jours développement.**

---

## ✅ Prêt à exécuter

Cette spec est complète et autosuffisante pour démarrer le LOT 2 immédiatement.

Étapes de démarrage proposées :
1. **Créer onglet `10_NS_Declarations`** dans le Sheet (manuel — je vous donne le schéma exact)
2. **Ajouter colonne `source_ns`** dans `02_Installations`
3. **Ajouter compteur `demande_id`** dans `04_Parametres`
4. Puis dev backend dans l'ordre : endpoint POST → endpoint admin → templates HTML → tests

📁 Document de spec : `/app/frontend/public/reports/audit/LOT_2_SPEC_NS_COLLECTE.md`

**Confirmez-vous le démarrage du développement ?**
- a. ✅ OK, créer les 3 éléments Sheet d'abord (onglet + colonne + compteur), puis dev backend
- b. ✏️ Ajuster la spec (UX, validations, autre…)
- c. 🔍 Préciser un point spécifique
