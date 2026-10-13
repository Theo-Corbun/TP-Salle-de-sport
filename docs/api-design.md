# Conception de l'API - Salle de Sport

## 1. Ressources et collections
- **cours** (`id`, `type`, `coach_id`) -> type d'activité sportive proposée
- **creneaux** (`id`, `cours_id`, `debut`, `fin`) -> sous-ressource de cours, séance planifiée
- **adherents** (`id`, `nom`, `email`, `telephone`) -> membre inscrit à la salle
- **reservations** (`id`, `creneau_id`, `adherent_id`, `statut`, `cree_le`) -> réservation d'un créneau par un adhérent

## 2. Matrice des opérations (URI x Verbe x Statuts)

| Opération | Méthode + URI | Succès | Erreurs prévues |
|---|---|---|---|
| Lister les cours | `GET /cours` | `200` | - |
| Lire un cours | `GET /cours/{id}` | `200` | `404` |
| Créer un cours | `POST /cours` | `201` + `Location` | `400`, `422` |
| Remplacer un cours | `PUT /cours/{id}` | `200` | `400`, `404`, `422` |
| Supprimer un cours | `DELETE /cours/{id}` | `204` | `404` |
| Lister les créneaux d'un cours | `GET /cours/{id}/creneaux` | `200` | `404` |
| Planifier un créneau pour un cours | `POST /cours/{id}/creneaux` | `201` + `Location` | `404`, `422` |
| Lister les réservations | `GET /reservations` | `200` | - |
| Réserver une place sur un créneau | `POST /creneaux/{id}/reservations` | `201` + `Location` | `404`, `409`, `422` |
| Annuler une réservation | `PATCH /reservations/{id}` | `200` | `404`, `422` |

## 3. Choix de conception justifiés
1. **Sous-ressource `/cours/{id}/creneaux`** : Un créneau horaire dépend directement de la discipline sportive dispensée ; son cycle de vie est lié au cours parent.
2. **Création via `/creneaux/{id}/reservations`** : L'acte de réservation cible un créneau précis. La réponse renvoie un code `201 Created` avec un en-tête `Location: /reservations/{id}` désignant l'URI propre de la réservation créée.
3. **Annulation via `PATCH /reservations/{id}`** : L'annulation consiste à modifier l'attribut `statut` à `"annulee"` plutôt que d'utiliser un verbe dans l'URL (`/annuler`) ou un `DELETE`, ce qui préserve l'historique d'occupation.

## 4. Format de réponse des collections (Enveloppe)

Toutes les collections paginées retournent un objet JSON respectant cette structure uniforme :

```json
{
  "data": [],
  "pagination": {
    "offset": 0,
    "limit": 20,
    "total": 45
  },
  "links": {
    "next": "/cours?offset=20&limit=20",
    "prev": null
  }
}

## 5. Gestion des erreurs et format Problem Details (RFC 9457)

En cas d'erreur cliente ou métier, l'API renvoie un corps JSON standardisé :

```json
{
  "type": "about:blank",
  "title": "Conflict",
  "status": 409,
  "detail": "Un adhérent avec cet email existe déjà.",
  "instance": "/adherents"
}

## 6. Sous-ressources et Actions Métier (TP 4)

### 6.1 Hiérarchie des sous-ressources
- `GET /cours/{cours_id}/creneaux` : Liste l'ensemble des créneaux horaires associés à un cours précis.
- `POST /cours/{cours_id}/creneaux` : Crée un créneau directement rattaché à ce cours.

### 6.2 Action métier de réservation
- `POST /creneaux/{creneau_id}/reservations` : Inscription d'un adhérent à une séance donnée.
  - Règles d'intégrité :
    - Le créneau doit exister (sinon `404 Not Found`).
    - L'adhérent doit exister (sinon `404 Not Found`).
    - Un adhérent ne peut pas réserver deux fois le même créneau (`409 Conflict`).

    ## 7. Cache HTTP et Négociation de Contenu (TP 5)

### 7.1 Cache conditionnel (ETag & 304 Not Modified)
- Sur les routes de consultation unitaire (`GET /cours/{cours_id}`, `GET /adherents/{adherent_id}`) :
  - En-tête de réponse `ETag` : hash MD5 représentant la version de la ressource.
  - En-tête de réponse `Cache-Control: private, max-age=60`.
  - Si le client transmet l'en-tête `If-None-Match` correspondant à l'ETag courant : le serveur répond immédiatement avec `304 Not Modified` (sans corps de réponse).

### 7.2 Négociation de contenu (Accept & 406 Not Acceptable)
- L'API supporte nativement `application/json` et `*/*`.
- Si le client demande un type MIME incompatible via l'en-tête `Accept` (ex. `application/xml`) :
  - Le serveur retourne une erreur `406 Not Acceptable` au format RFC 9457 `Problem Details`.

  ## 8. Sécurité et Contrôle de Débit (TP 6)

### 8.1 Authentification par clé API (`X-API-Key`)
- **Lecture (`GET`)** : Publique, aucune clé requise pour consulter les cours, créneaux et adhérents.
- **Écriture (`POST`, `PATCH`, `DELETE`)** : Sécurisée, requiert l'en-tête HTTP `X-API-Key: gym_secret_key_2026`.
- **En cas d'échec** : Retourne `401 Unauthorized` au format RFC 9457 :
  ```json
  {
    "type": "about:blank",
    "title": "Unauthorized",
    "status": 401,
    "detail": "Clé API manquante ou invalide.",
    "instance": "/cours"
  }