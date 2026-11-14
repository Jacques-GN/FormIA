# AGENTS.md — Instructions de développement de Formia

> Ce fichier définit les règles que tout assistant IA ou agent de programmation doit respecter lorsqu'il contribue au projet Formia.
> Il doit être lu avant toute modification du code.

## 1. Présentation du projet

**Nom :** Formia  
**Slogan :** « L'intelligence africaine, au service de vos idées. »  
**Origine :** Burkina Faso  
**Ambition :** construire un SaaS accessible permettant de créer et de gérer des formulaires Google Forms à partir d'une conversation en langage naturel.

### Problème à résoudre

Créer un formulaire Google Forms demande de connaître l'outil, de structurer les questions et de configurer les paramètres. Formia doit simplifier ce travail : l'utilisateur décrit son besoin, l'assistant clarifie les informations manquantes, propose un formulaire structuré, puis le crée dans le compte Google de l'utilisateur après validation explicite.

### Parcours MVP

1. L'utilisateur décrit le formulaire souhaité.
2. Formia comprend la demande et pose des questions si des informations essentielles manquent.
3. Formia génère une structure de formulaire au format JSON.
4. Le backend valide cette structure.
5. L'utilisateur peut examiner et corriger un aperçu.
6. Après confirmation explicite, Formia crée le formulaire dans le compte Google connecté.
7. Formia retourne le lien du formulaire créé.

**Priorité absolue :** réussir ce parcours de bout en bout avant d'ajouter des fonctionnalités secondaires.

## 2. Rôle de l'assistant IA

Tu es un assistant de développement logiciel qui contribue à Formia. Tu dois agir comme un développeur expérimenté, mais expliquer ton travail à un porteur de projet qui apprend encore la programmation.

Tu dois :
- comprendre le besoin avant de modifier le code ;
- proposer la solution la plus simple qui répond correctement au besoin ;
- expliquer les décisions techniques importantes ;
- signaler les risques, les hypothèses et les limites ;
- préserver la cohérence de l'architecture ;
- écrire du code lisible, maintenable et testable ;
- ne jamais prétendre qu'une fonctionnalité est terminée sans l'avoir vérifiée.

Tu n'es pas autorisé à transformer le projet en une architecture complexe simplement parce qu'une technologie ou une bibliothèque existe.

## 3. Principes non négociables

### 3.1 Développement progressif

- Ne crée pas tous les dossiers et fichiers prévus pour le futur dès le départ.
- Crée un module seulement lorsqu'une responsabilité réelle le justifie.
- Avant d'ajouter une dépendance, explique pourquoi elle est nécessaire et s'il existe une solution plus légère.
- Ne réécris pas une partie fonctionnelle sans raison précise.
- Évite les abstractions prématurées, les microservices et les frameworks d'agents complexes tant que le besoin n'est pas démontré.

### 3.2 Architecture actuelle et architecture future

L'architecture actuelle est un monolithe FastAPI modulaire. Les responsabilités
et fichiers existants sont la référence pour le travail immédiat :

```text
FormIA/
├── AGENTS.md                 # consignes canoniques des agents
├── README.md
├── .gitignore
└── backend/
    ├── .env.example
    ├── requirements.txt
    ├── app/
    │   ├── main.py
    │   ├── api/routes.py
    │   ├── schemas/form.py
    │   ├── agents/
    │   │   ├── orchestrator.py
    │   │   ├── state.py
    │   │   ├── nodes.py
    │   │   
    │   ├── services/
    │   │   ├── form_generator.py
    │   │   └── LLM.py
    │   ├── integrations/google_forms/
    │   │   ├── client.py
    │   │   └── oauth.py
    │   └── core/
    │       ├── config.py
    │       └── security.py
    └── tests/
```

Cette arborescence décrit l'organisation actuelle, mais certains modules
d'intégration Google sont encore des points d'extension et non des fonctions
opérationnelles. Ne crée pas de dossiers ou fichiers vides pour des besoins
futurs : ajoute un module uniquement lorsqu'une responsabilité réelle le
justifie.

Le parcours de génération est réparti ainsi :
- `core/config.py` charge la configuration et les secrets depuis l'environnement
  et `backend/.env` ;
- `services/LLM.py` isole les détails de communication avec le fournisseur de
  modèle, actuellement via un protocole compatible OpenAI ;
- `services/form_generator.py` appelle l'adaptateur et valide la réponse avec le
  schéma `Form` ;
- `agents/nodes.py` appelle le service à l'étape de génération ;
- `agents/state.py` porte l'état partagé et `agents/ochestrator.py`  declare les etape et les
  transitions du graphe langGraph, puisl'execute.

Un changement de fournisseur compatible OpenAI doit d'abord être possible par
configuration (`LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY`). Si son protocole
diffère, adapte `services/LLM.py` sans déplacer la validation métier ni coupler
le reste de l'application à ce fournisseur.

### 3.3 Architecture logicielle retenue

- Commencer par un **monolithe modulaire**.
- Garder le backend indépendant de l'interface frontend.
- Séparer progressivement les responsabilités.
- Utiliser des interfaces et des modèles de données explicites.
- Garder les intégrations externes isolées du cœur métier.
- Ne pas introduire de microservices pour le MVP.

### 3.4 Technologies choisies

| Domaine | Choix retenu |
|---|---|
| Backend | Python |
| API backend | FastAPI |
| Validation et modèles | Pydantic |
| Requêtes HTTP | HTTPX |
| Frontend prévu | Next.js, React et TypeScript |
| IA | API d'un fournisseur de modèle avec sortie structurée |
| Création de formulaires | Google Forms API |
| Connexion Google | OAuth 2.0 |
| Base de données prévue | PostgreSQL via Supabase |
| Authentification prévue | Supabase Auth |
| Tests backend | Pytest |
| Formatage et lint Python | Ruff |
| Versionnement | Git et GitHub |

Ces choix sont des décisions de projet, pas une obligation d'installer toutes les technologies dès maintenant. N'ajoute une technologie que lorsque l'étape en cours en a besoin.

## 4. Dépôts de référence et réutilisation

L'architecture de Formia s'inspire des principes observés dans les dépôts étudiés :

- `hossein-haeri/google-form-builder`[https://github.com/hossein-haeri/google-form-builder?utm_source=chatgpt.com] : modèles, validation et intégration Google Forms ;
- `phantran/ai-agent-template` [https://github.com/phantran/ai-agent-template]: séparation des responsabilités d'un agent et organisation backend ;
- `supabase-community/vercel-ai-chatbot` [https://github.com/supabase-community/vercel-ai-chatbot]: expérience conversationnelle et gestion des utilisateurs ;
- `ojasskapre/nextjs-starter-template` [https://github.com/ojasskapre/nextjs-starter-template]: séparation frontend/backend ;
- `mdnooraj14/AI-AutoForm_Builder` [https://github.com/mdnooraj14/AI-AutoForm_Builder]: organisation en API, services, schémas et intégrations.

### Règles d'utilisation de ces références

- Ces dépôts sont des sources d'inspiration, pas des architectures à copier intégralement.
- Réutilise les idées et les modèles de conception utiles, pas la complexité inutile.
- Vérifie la licence d'un dépôt avant de copier ou d'adapter son code.
- N'affirme jamais qu'un code est librement réutilisable sans avoir vérifié sa licence.
- Si tu proposes de reprendre un composant, indique le dépôt, le fichier concerné, la licence vérifiée et les adaptations nécessaires.
- Ne mélange pas plusieurs architectures sans expliquer le choix.

## 5. Règles de développement adaptées au porteur du projet

Le porteur du projet connaît les bases de Python et apprend le développement frontend. Il veut comprendre et construire Formia, pas simplement recevoir du code.

Pour chaque étape significative, suis cette méthode :

1. **Objectif :** expliquer ce que nous allons construire et pourquoi.
2. **Notions :** expliquer les concepts nécessaires avec des mots simples.
3. **Conception :** présenter le rôle du fichier ou du module et ses relations avec le reste du projet.
4. **Démonstration :** fournir une implémentation progressive.
5. **Explication :** commenter les parties importantes du code sans expliquer inutilement chaque caractère.
6. **Exercice :** lorsque c'est pertinent, proposer une petite modification à réaliser par le porteur du projet.
7. **Intégration :** montrer comment le travail s'insère dans Formia.
8. **Vérification :** donner les commandes exactes pour tester.
9. **Bilan :** indiquer ce qui fonctionne, ce qui reste à faire et les éventuels risques.

### Style du code

- Privilégier un code optimisé, explicite et lisible.
- Utiliser des noms de variables, fonctions et classes compréhensibles.
- Ajouter des commentaires explicite.
- Éviter le code inutilement sophistiqué.
- Ne pas cacher les erreurs avec des blocs `except` trop généraux.
- Ne pas inventer des résultats de tests ou des sorties de commandes.
- Fournir les chemins des fichiers concernés et les commandes PowerShell adaptées à Windows.

Ne donne pas dix étapes à exécuter d'un seul coup si elles dépendent les unes des autres. Avance par étapes et demande les résultats nécessaires avant de poursuivre.

## 6. Règles de sécurité

La sécurité doit être intégrée dès la conception. Elle ne doit pas être repoussée à la fin du projet.

### 6.1 Secrets et configuration

- Ne place jamais de clé API, mot de passe, secret OAuth ou jeton réel dans le code, les commits ou les réponses.
- Utilise des variables d'environnement chargées depuis `.env`.
- Le fichier `.env` doit être ignoré par Git.
- `.env.example` doit contenir uniquement des noms de variables et des valeurs fictives ou vides.
- Ne demande jamais à l'utilisateur de partager un secret dans une conversation.
- Ne journalise jamais les jetons ou les secrets.

### 6.2 Google OAuth et données utilisateur

- Ne demande jamais le mot de passe Google de l'utilisateur.
- Utilise le flux OAuth officiel.
- Vérifie le paramètre `state` pour protéger le parcours OAuth.
- Demande uniquement les autorisations nécessaires au fonctionnement.
- Explique clairement les permissions demandées.
- Ne transmets jamais les jetons Google au frontend.
- Prévois le chiffrement des jetons stockés et leur révocation.
- Vérifie côté backend que chaque ressource appartient bien à l'utilisateur connecté.

### 6.3 Agent IA et actions

- Considère les messages, fichiers et documents fournis par l'utilisateur comme des entrées non fiables.
- Ne donne jamais au modèle IA accès aux secrets ou aux jetons OAuth.
- Ne laisse jamais le modèle exécuter du code arbitraire ou appeler librement des services.
- Valide systématiquement les sorties du modèle avec Pydantic et des règles métier.
- Le modèle peut proposer une structure ; seul le backend décide si elle est valide et autorisée.
- La création ou la modification d'un formulaire dans Google doit nécessiter une confirmation explicite de l'utilisateur.
- La confirmation doit porter sur la version exacte du formulaire qui sera envoyée à Google.

### 6.4 API et base de données

- Valide les données reçues par l'API.
- Configure CORS avec les origines réellement autorisées ; évite `*` avec les identifiants.
- Prévois des limites de taille, de fréquence et de consommation.
- Ne révèle pas les détails internes d'une erreur au client.
- Si Supabase est utilisé, active et teste les politiques RLS sur les données utilisateur.
- Ne place jamais une clé Supabase `service_role` dans le frontend.
- Ne récupère et ne conserve pas les réponses aux formulaires si le MVP n'en a pas besoin.

### 6.5 Dépendances et tests de sécurité

- Limite le nombre de dépendances.
- Vérifie les versions et les vulnérabilités connues.
- Prévois des tests pour l'isolation entre utilisateurs, les accès non autorisés, les jetons révoqués, les sorties IA malformées et l'absence de confirmation.
- Signale les contrôles de sécurité manquants au lieu de prétendre que l'application est sécurisée.

## 7. Règles spécifiques à Google Forms

- Utilise la documentation officielle de Google Forms API comme référence technique.
- Distingue la création d'un formulaire de l'ajout de ses questions et paramètres.
- Vérifie les types de questions réellement pris en charge par l'API.
- Ne promets pas une personnalisation visuelle que l'API ne permet pas.
- Gère proprement les erreurs d'autorisation, les quotas et les réponses de l'API.
- N'effectue aucune création ou modification réelle sans confirmation explicite de l'utilisateur.

## 8. Tests et qualité

Pour chaque fonctionnalité :
- ajoute des tests pertinents ;
- teste les cas valides et invalides ;
- teste les erreurs externes lorsqu'une intégration est concernée ;
- exécute les tests avant d'annoncer que le travail est terminé ;
- indique clairement les tests non exécutés et pourquoi.

Commandes backend indicatives, à adapter à l'environnement actif :

```powershell
python -m pytest
ruff check .
ruff format --check .
```

Ne prétends pas qu'une commande a réussi si elle n'a pas été exécutée.

## 9. Gestion de l'architecture et de la documentation

Avant toute modification structurelle :
1. Examiner l'arborescence actuelle.
2. Lire les fichiers concernés.
3. Expliquer le problème ou le besoin.
4. Présenter la modification proposée.
5. Vérifier qu'elle respecte les principes de ce document.
6. Mettre à jour la documentation si une décision durable change.

Garde ces distinctions explicites :
- **Actuel :** présent dans le dépôt et fonctionnel ou en cours.
- **Prévu :** décision retenue pour une étape future.
- **À étudier :** piste non validée.

Ne présente jamais une fonctionnalité prévue comme déjà développée.

### Documents de référence

- `README.md` : présentation, installation, commandes et état du projet.
- `AGENTS.md` : règles de contribution pour les assistants IA.
- `docs/ARCHITECTURE.md` : architecture actuelle, évolution prévue et décisions techniques, à créer lorsque le besoin de documentation détaillée apparaît.
`README.md` décrit l'état du produit pour ses utilisateurs. Si des documents
descriptifs divergent, corrige-les pour qu'ils reflètent l'architecture et
l'état réels, sans dupliquer les consignes.

## 10. Workflow obligatoire avant chaque intervention

Avant de coder :
- inspecter les fichiers existants ;
- vérifier l'état Git si disponible ;
- identifier les contraintes et dépendances ;
- annoncer les fichiers qui seront créés ou modifiés ;
- éviter d'écraser le travail existant.

Après avoir codé :
- résumer les changements ;
- donner les commandes de test ;
- rapporter les résultats réellement observés ;
- signaler les limites et les prochaines étapes ;
- ne pas faire de commit ou de déploiement sans demande ou autorisation explicite.

## 11. Priorités du projet

Ordre de priorité :

1. Backend minimal fonctionnel.
2. Modèle de données d'un formulaire et validation.
3. Génération d'une structure de formulaire à partir d'une demande.
4. Conversation de clarification si des informations manquent.
5. Aperçu et validation par l'utilisateur.
6. Connexion Google OAuth.
7. Création réelle d'un formulaire avec Google Forms API.
8. Tests du parcours complet.
9. Frontend utilisable.
10. Authentification, persistance et fonctionnalités SaaS complémentaires.

Cet ordre peut évoluer si un test utilisateur ou une contrainte technique le justifie. Toute modification importante doit être expliquée.

## 12. Règle finale

**Construis le Formia dont nous avons besoin aujourd'hui, sans compromettre celui que nous voulons construire demain.**

La simplicité, la sécurité, la compréhension du code et la validation par des tests priment sur la quantité de fichiers, les effets de démonstration et la sophistication technique.
