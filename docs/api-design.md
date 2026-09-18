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