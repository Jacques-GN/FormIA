# FormIA

FormIA crée des formulaires Google Forms à partir d'une demande en langage
naturel, grâce à un agent conversationnel. Le backend est un monolithe
modulaire construit avec Python, FastAPI, Pydantic et LangGraph.

## État du projet

### Déjà présent

- `POST /forms/chat` : l'agent converse, pose des questions de clarification si
  la demande est incomplète, génère un formulaire, puis le modifie à la demande
  dans la même session.
- L'agent est un graphe LangGraph (analyser, clarifier, générer) avec relance
  automatique si le LLM produit un formulaire invalide (2 tentatives maximum).
- La mémoire d'une conversation est conservée par `session_id`, en RAM
  (`InMemorySaver`) : elle est perdue au redémarrage du serveur.
- Les schémas Pydantic `Form`, `Question` et `RequestAnalysis` valident chaque
  formulaire généré (5 types : texte court, paragraphe, choix unique, cases à
  cocher, liste déroulante).
- Un adaptateur HTTP appelle tout fournisseur compatible avec l'API OpenAI.
- `GET /auth/google/login` et `GET /auth/google/callback` : connexion OAuth 2.0
  à Google, avec un paramètre `state` à usage unique. Le jeton d'accès (valable
  environ 1 heure) est gardé en RAM, jamais renvoyé au client ni au LLM.
- `POST /forms/confirm` : crée le formulaire dans le compte Google après
  confirmation de l'empreinte SHA-256 de la version exacte. Une empreinte
  périmée est refusée (HTTP 409) et le contenu créé est toujours la copie du
  serveur, jamais celle envoyée par le client.
- Le client Google Forms traduit les 5 types de questions et crée le formulaire
  en deux appels (création vide, puis description et questions).
- La création est idempotente par empreinte : une seconde confirmation renvoie
  le résultat déjà obtenu sans rappeler Google. Après un échec partiel, la
  confirmation reprend sur le même formulaire en ne recréant que les questions
  absentes.
- Un module centralisé d'exceptions (`core/exceptions.py`) convertit les erreurs
  métier en réponses uniformes `{code, message}`, sans détail interne. Les
  appels LLM sont relancés sur 429/5xx avec attente croissante et jitter.
- L'historique envoyé au LLM est borné (20 messages, brief initial conservé) et
  chaque appel journalise durée, modèle, statut et tokens, jamais le contenu.
- Les tests (62) simulent le LLM et Google : aucun appel réseau réel.

### Pas encore terminé

- Aucun test d'intégration réel contre Google (OAuth et création) : la suite
  automatisée ne prouve pas encore le parcours complet chez Google.
- Le registre d'idempotence est en RAM : il ne survit pas au redémarrage et
  n'est pas partagé entre processus.
- La confirmation n'est pas encore reliée à une version numérotée et historisée
  du formulaire.
- Authentification FormIA, propriété des ressources, jeton Google durable
  (refresh token chiffré) et persistance PostgreSQL : la mémoire et les jetons
  sont en RAM.
- Le frontend.

## Organisation du backend

```text
backend/
├── app/
│   ├── main.py                     # application FastAPI
│   ├── api/routes.py               # routes HTTP, empreinte et confirmation
│   ├── schemas/form.py             # Form, Question, QuestionType, RequestAnalysis
│   ├── agents/
│   │   ├── orchestrator.py         # graphe LangGraph, mémoire, traiter_message()
│   │   ├── state.py                # état partagé du graphe
│   │   └── nodes.py                # étapes : analyser, clarifier, générer
│   ├── services/
│   │   ├── form_generator.py       # consignes (prompts) et validation des réponses
│   │   └── LLM.py                  # adaptateur HTTP compatible OpenAI
│   ├── integrations/google_forms/
│   │   ├── client.py               # traduction Form -> Google Forms et création
│   │   ├── creation_store.py       # suivi idempotent des créations, en RAM
│   │   ├── oauth.py                # URL de consentement et échange du code
│   │   └── token_store.py          # « state » OAuth et jetons d'accès, en RAM
│   └── core/
│       ├── config.py               # paramètres d'environnement
│       ├── exceptions.py           # erreurs métier et codes HTTP
│       ├── retry.py                # relances contrôlées sur 429/5xx
│       └── security.py             # génération du « state » OAuth
└── tests/                          # LLM et Google simulés
```

Le fil d'une requête : `routes.py` appelle `orchestrator.traiter_message()`, qui
exécute le graphe. Les étapes de `nodes.py` délèguent à `form_generator.py`, qui
envoie les messages via `LLM.py` et valide la réponse avec les schémas. Pour la
création, `routes.py` vérifie l'empreinte, récupère le jeton dans `token_store.py`
et appelle `client.create_form()`.

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
Attention : redémarrer le serveur efface la mémoire des conversations et les
jetons Google en RAM.

## Parcours d'utilisation

1. Premier message (sans `session_id`) :

   ```json
   {"message": "Je veux un formulaire d'inscription à un tournoi de football"}
   ```

   La réponse contient un `session_id` et un `status` :

   - `clarification` : l'agent pose des questions (liste `questions`) ;
   - `form_ready` : le formulaire est dans `form`, avec son `form_hash` ;
   - `failed` : la génération a échoué.

2. Pour répondre ou demander une modification, renvoyez le même `session_id`.

3. Avant la création, connectez Google :

   ```text
   GET /auth/google/login?session_id=<session_id>
   ```

   Google revient sur `/auth/google/callback`. Le jeton n'est jamais exposé au
   client.

4. Après relecture, confirmez la version exacte :

   ```json
   {"session_id": "<session_id>", "form_hash": "<form_hash>"}
   ```

   La réponse contient `form_id`, `responder_url` et `edit_url`.

## Configuration

Variables de `backend\.env` :

| Variable | Rôle |
|---|---|
| `APP_NAME` | Nom affiché de l'application |
| `LLM_API_KEY` | Clé secrète fournie par le service choisi |
| `LLM_MODEL` | Nom exact du modèle |
| `LLM_BASE_URL` | URL de base de l'API compatible OpenAI |
| `GOOGLE_CLIENT_ID` | Identifiant client OAuth Google |
| `GOOGLE_CLIENT_SECRET` | Secret client OAuth Google |
| `GOOGLE_REDIRECT_URI` | URI de retour, par défaut `http://127.0.0.1:8000/auth/google/callback` |

Tout fournisseur compatible fonctionne en changeant les trois variables `LLM_*`.
Groq a été validé en développement. Ne mettez jamais de clé réelle dans le code,
le README ou Git, et redémarrez le serveur après toute modification du `.env`.

L'autorisation Google demandée est le scope `forms.body` (création et
modification de formulaires). Aucun refresh token n'est demandé pour l'instant :
après environ une heure, il faut se reconnecter.

## Tests

Depuis le dossier `backend` :

```powershell
python -m pytest tests
```

Les tests simulent le LLM et Google : `tests/conftest.py` vide la configuration
des fournisseurs et isole les registres pour qu'aucun test n'atteigne un vrai
service. La suite couvre notamment :

- la conversation, les schémas et le graphe de l'agent ;
- l'adaptateur LLM (requête compatible OpenAI, relances, erreurs de config) ;
- le client Google Forms (les 5 types, reprise sans doublon, échec partiel) ;
- `/forms/confirm` : 404, 401, 409, succès, double confirmation et reprise ;
- OAuth : `state` à usage unique et expiré, URL de consentement, échange du code ;
- le registre d'idempotence et les relances 429/5xx.

En revanche, aucun test ne contacte réellement Google : le parcours complet chez
Google reste à vérifier manuellement.

## Compatibilité Google Forms

| Type FormIA | Élément Google Forms | Création par l'API |
|---|---|---|
| `short_text` | `textQuestion` (`paragraph: false`) | Oui |
| `paragraph` | `textQuestion` (`paragraph: true`) | Oui |
| `multiple_choice` | `choiceQuestion` type `RADIO` | Oui |
| `checkboxes` | `choiceQuestion` type `CHECKBOX` | Oui |
| `dropdown` | `choiceQuestion` type `DROP_DOWN` | Oui |
| Import de fichier | `fileUploadQuestion` | Non (non pris en charge par l'API) |

`documentTitle` peut être défini à la création mais ne peut pas être modifié par
`batchUpdate` : FormIA ne le change donc qu'à la création.

## Limites connues

- La question Google Forms « Importer un fichier » n'est pas prise en charge par
  l'API Forms : FormIA ne la propose pas.
- Le schéma ne gère ni sections, ni description par question, ni échelle, ni
  date, ni validation conditionnelle.
- Toute la mémoire (conversations, « state » OAuth, jetons Google, registre des
  créations) est locale au processus : pas de partage entre plusieurs workers,
  perte au redémarrage.
- L'idempotence de `/forms/confirm` n'est garantie que dans le processus courant :
  après un redémarrage, le registre est vide et une confirmation peut créer un
  nouveau formulaire.
- Les jetons Google sont associés à un `session_id`, pas encore à un utilisateur
  authentifié : la propriété des ressources relève du Bloc C.
