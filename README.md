# FormIA

FormIA aide à créer des formulaires à partir d'une demande en langage naturel.
Le backend est construit avec FastAPI et Pydantic.

## État actuel

- L'API expose `/` et `/health`.
- Les schémas Pydantic valident les formulaires et leurs questions.
- L'orchestration suit un petit graphe : validation de la demande, puis appel
  au service de génération. Le graphe est réparti entre `state.py` (état
  partagé), `nodes.py` (étapes), `edges.py` (transitions) et
  `orchestrator.py` (construction et exécution).
- La génération par IA, OAuth Google et la création Google Forms restent à
  implémenter. Les modules correspondants sont des points d'extension, pas des
  fonctionnalités opérationnelles.

Arborescence de l'orchestration :

```text
backend/app/agents/
├── orchestrator.py   # construit et lance le graphe
├── state.py          # l'état partagé
├── nodes.py          # une fonction par étape
└── edges.py          # les décisions entre étapes
```

## Démarrer le backend sous Windows

Depuis la racine du dépôt, créez un environnement virtuel et installez les
dépendances :

```powershell
py -m venv backend\.venv
backend\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
Copy-Item backend\.env.example backend\.env
uvicorn app.main:app --app-dir backend --reload
```

L'API est disponible sur `http://127.0.0.1:8000` et sa documentation
interactive sur `http://127.0.0.1:8000/docs`.

## Tests

```powershell
python -m pytest backend\tests
```

Les paramètres locaux se placent dans `backend\.env`. Ce fichier est ignoré par
Git ; ne partagez et ne versionnez jamais de secrets.
