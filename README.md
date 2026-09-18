# API Salle de Sport

## Sujet fil rouge
Sujet n° 3 - Salle de sport

## Stack
Langage : Python 3.12+   /   Framework HTTP : FastAPI   /   Client HTTP : Insomnia

## Stratégie de pagination
Pagination par offset (`offset`, `limit`) avec enveloppe de réponse (`data`, `pagination`, `links`) et tri stable sur `(type, id)` pour garantir la cohérence des pages.

## Lancer le projet

### 1. Cloner le projet et se positionner dans le dossier
```powershell
cd TP-Salle-de-sport
```

### 2. Créer et activer l'environnement virtuel
```powershell
python -m venv venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\venv\Scripts\Activate.ps1
```

### 3. Installer les dépendances
```powershell
pip install fastapi "uvicorn[standard]" sqlmodel
```

### 4. Démarrer l'API
```powershell
python -m uvicorn src.main:app --reload
```

- **URL de base** : `http://localhost:8000`