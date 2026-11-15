# FormIA

FormIA crée des formulaires Google Forms à partir d'une demande en langage
naturel, grâce à un agent conversationnel. Le backend est un monolithe
modulaire construit avec Python, FastAPI, Pydantic et LangGraph.

## État du projet

### Déjà présent

- Une route `POST /forms/chat` permet de converser avec l'agent : il pose des
  questions de clarification si la demande est incomplète, génère un
  formulaire, puis le modifie à la demande dans la même session.
- L'agent est un graphe LangGraph (analyser, clarifier, générer, valider) avec
  relance automatique si le LLM produit un formulaire invalide.
- La mémoire d'une conversation est conservée par `session_id`, en RAM.
- Les schémas Pydantic `Form` et `Question` valident chaque formulaire généré.
- Un adaptateur HTTP appelle tout fournisseur compatible avec l'API OpenAI.
- Les tests (30) simulent le LLM : aucun appel réseau réel.

### Pas encore terminé

- La création du formulaire dans un compte Google (OAuth, Google Forms API).
- L'aperçu et la confirmation explicite avant création.
- La gestion centralisée des erreurs (module dédié prévu).
- Authentification, comptes utilisateurs et mémoire persistante : la mémoire
  actuelle est perdue au redémarrage du serveur.
- Le frontend.

Les modules `integrations/google_forms/` sont des points d'extension : l'application
ne crée pas encore de formulaire dans un compte Google.

## Organisation du backend

```text
backend/
├── app/
│   ├── main.py                     # création de l'application FastAPI
│   ├── api/routes.py               # routes HTTP (/, /health, /forms/chat)
│   ├── schemas/form.py             # Form, Question, RequestAnalysis
│   ├── agents/
│   │   ├── orchestrator.py         # graphe LangGraph, mémoire, traiter_message()
│   │   ├── state.py                # état partagé du graphe
│   │   └── nodes.py                # étapes : analyser, clarifier, générer
│   ├── services/
│   │   ├── form_generator.py       # consignes (prompts) et validation des réponses
│   │   └── LLM.py                  # adaptateur HTTP compatible OpenAI
│   ├── integrations/google_forms/
│   │   ├── client.py               # futur client Google Forms
│   │   └── oauth.py                # préparation OAuth, flux à compléter
│   └── core/
│       ├── config.py               # paramètres d'environnement
│       └── security.py             # utilitaires OAuth state
└── tests/                          # conftest.py bloque tout appel réel au LLM
```

Le fil d'une requête : `routes.py` appelle `orchestrator.traiter_message()`, qui
exécute le graphe. Les étapes de `nodes.py` délèguent à `form_generator.py`, qui
envoie les messages via `LLM.py` et valide la réponse avec les schémas.

## Installation et démarrage sous Windows

Depuis la racine du dépôt :

```powershell
py -m venv backend\.venv
backend\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
Copy-Item backend\.env.example backend\.env
```

Démarrage de l'API (depuis la racine) :

```powershell
uvicorn app.main:app --app-dir backend --reload
```

La documentation interactive est sur `http://127.0.0.1:8000/docs`.
Attention : redémarrer le serveur efface la mémoire des conversations.

## Utiliser l'agent

Premier message (sans `session_id`) :

```json
{"message": "Je veux un formulaire d'inscription à un tournoi de football"}
```

La réponse contient un `session_id` et un `status` :

- `clarification` : l'agent pose des questions (liste `questions`) ;
- `form_ready` : le formulaire est dans `form` ;
- `failed` : la génération a échoué.

Pour répondre ou demander une modification, renvoyez le même `session_id`.

## Configuration du LLM

Variables de `backend\.env` :

| Variable | Rôle |
|---|---|
| `LLM_API_KEY` | Clé secrète fournie par le service choisi |
| `LLM_MODEL` | Nom exact du modèle |
| `LLM_BASE_URL` | URL de base de l'API compatible OpenAI |

Tout fournisseur compatible fonctionne en changeant ces trois valeurs. Groq a
été validé en développement. Ne mettez jamais de clé réelle dans le code, le
README ou Git, et redémarrez le serveur après toute modification du `.env`.

## Tests

Depuis le dossier `backend` :

```powershell
python -m pytest tests
```

Les tests simulent le LLM. `tests/conftest.py` vide la configuration du
fournisseur pour qu'aucun test n'atteigne un vrai service.