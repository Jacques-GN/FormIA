# Agent de développement

Les consignes de contribution canoniques se trouvent dans [AGENTS.md](./AGENTS.md).

## Orchestration du formulaire

Le parcours d'une demande de formulaire utilise un graphe léger, sans framework
d'agent externe :

- `backend/app/agents/orchestrator.py` construit le graphe et lance ses étapes ;
- `backend/app/agents/state.py` définit l'état partagé entre les étapes ;
- `backend/app/agents/nodes.py` contient une fonction par étape ;
- `backend/app/agents/edges.py` décide de l'étape suivante.

Le flux actuel valide la demande puis appelle le générateur. La génération IA
n'étant pas encore configurée, cette dernière étape reste un point d'extension.
Toute nouvelle étape doit être ajoutée au graphe et à ses transitions, sans
déplacer la logique métier dans les routes HTTP.
