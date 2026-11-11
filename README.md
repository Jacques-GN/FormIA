# FormIA

FormIA vise à créer des formulaires Google Forms à partir d'une demande en
langage naturel. Le backend est un monolithe modulaire construit avec Python,
FastAPI et Pydantic.

## État du projet

### Déjà présent

- L'API FastAPI expose `GET /` et `GET /health`.
- Les schémas Pydantic de formulaire et de question sont définis dans
  `backend/app/schemas/form.py`.
- Un graphe léger valide la demande, puis appelle le service de génération.
- Le service peut envoyer une demande à un fournisseur compatible avec l'API
  OpenAI, puis valider le JSON retourné avec le schéma `Form`.
- Les tests couvrent les routes, les schémas, le graphe et l'adaptateur LLM.

### Pas encore terminé

- Il n'y a pas encore de route HTTP pour soumettre une demande et retourner le
  formulaire généré.
- L'appel réel au LLM nécessite de renseigner la configuration du fournisseur.
- Le flux OAuth complet et la création de formulaires via Google Forms API ne
  sont pas implémentés.

Les modules Google Forms actuels sont des points d'extension : l'application ne
crée pas encore de formulaire dans un compte Google.

## Organisation du backend

```text
backend/app/
├── main.py                         # création de l'application FastAPI
├── api/routes.py                   # routes HTTP
├── schemas/form.py                 # modèles Pydantic Form et Question
├── agents/
│   ├── orchestrator.py             # construit et exécute le graphe
│   ├── state.py                    # état partagé
│   ├── nodes.py                    # étapes du parcours
│   └── edges.py                    # transitions entre étapes
├── services/
│   ├── form_generator.py           # logique de génération et validation
│   └── LLM.py                      # adaptateur HTTP fournisseur compatible OpenAI
├── integrations/google_forms/
│   ├── client.py                   # futur client Google Forms
│   └── oauth.py                    # préparation OAuth, flux à compléter
└── core/
    ├── config.py                   # paramètres d'environnement
    └── security.py                 # utilitaires OAuth state
```

Le graphe appelle `agents/nodes.py`, qui utilise `services/form_generator.py`.
Ce service délègue la communication avec le modèle à `services/LLM.py`. Les
paramètres du fournisseur sont lus par `core/config.py`. Ainsi, un fournisseur
compatible OpenAI peut généralement être changé en modifiant la configuration ;
pour un protocole différent, l'adaptateur `LLM.py` est le point à remplacer.

## Installation et démarrage sous Windows

Depuis la racine du dépôt, créez un environnement virtuel, installez les
dépendances et copiez le modèle de configuration :

```powershell
py -m venv backend\.venv
backend\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
Copy-Item backend\.env.example backend\.env
```

Pour démarrer l'API :

```powershell
uvicorn app.main:app --app-dir backend --reload
```

L'API est disponible sur `http://127.0.0.1:8000`. La documentation interactive
FastAPI se trouve sur `http://127.0.0.1:8000/docs`.

## Configuration du LLM

La génération utilise les variables suivantes dans `backend\.env` :

| Variable | Rôle |
|---|---|
| `LLM_API_KEY` | Clé secrète fournie par le service choisi |
| `LLM_MODEL` | Nom ou identifiant du modèle |
| `LLM_BASE_URL` | URL de base de l'API compatible OpenAI, par exemple `https://fournisseur.example/v1` |

`backend\.env.example` contient uniquement des valeurs vides ou fictives.
Complétez le fichier local `backend\.env` ; ne mettez jamais de clé réelle dans
le code, le README ou Git. La route HTTP de génération n'étant pas encore
disponible, la configuration du fournisseur ne rend pas à elle seule le
parcours accessible via l'API.

## Tests

Depuis la racine du dépôt :

```powershell
python -m pytest backend\tests
```

Les tests n'appellent pas un fournisseur LLM réel ; les échanges réseau sont
simulés afin de tester le format de la requête et la validation de la réponse.
