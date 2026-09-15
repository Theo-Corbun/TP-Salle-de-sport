# API Salle de Sport

## Sujet fil rouge
Sujet n° 3 - Salle de sport

## Stack
Langage : Python 3.12+   /   Framework HTTP : FastAPI   /   Client HTTP : Insomnia

## Prérequis
- Python installé avec `pip`
- DB Browser for SQLite (pour visualiser les tables)

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

### 4. Initialiser la base de données (si non présente)
```powershell
python -c "import sqlite3; con = sqlite3.connect('Salle-de-sport.db'); cur = con.cursor(); cur.executescript(open('kits/salle-de-sport/schema.sql', encoding='utf-8').read()); cur.executescript(open('kits/salle-de-sport/seed.sql', encoding='utf-8').read()); con.close()"
```

### 5. Démarrer l'API
```powershell
python -m uvicorn src.main:app --reload
```

- **URL de base** : `http://localhost:8000`