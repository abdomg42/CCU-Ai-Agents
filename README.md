# Diagnostic Technique CCU

Agent IA de diagnostic technique pour le système d'information télécom **CCU** (Commande et Catalogue Unifiés), basé sur les APIs **TMF620** (Product Catalog) et **TMF622** (Product Ordering).

L'agent analyse des incidents techniques en corrélant :
- des logs réseau,
- l'historique client (CRM),
- les tickets d'incidents historiques (Jira/ServiceNow),

pour proposer un diagnostic et une action corrective. **Aucune action n'est exécutée automatiquement** : le pipeline s'arrête toujours à "action proposée" et passe par un guardrail de validation finale.

## Architecture

```
START
  │
  ▼
intake_parser
  │
  ▼
[ logs_investigator  │  context_agent  │  rag_ticket_search ]
  │                    │                 │
  └────────────────────┴─────────────────┘
  │
  ▼
root_cause_reasoner
  │
  ▼
remediation_planner
  │
  ▼
guardrail_validator
  │
  ▼
END
```

Les trois agents collecteurs (`logs_investigator`, `context_agent`, `rag_ticket_search`) s'exécutent **en parallèle** dans le nœud `collectors` de LangGraph (via `asyncio.gather` / fallback `ThreadPoolExecutor`).

## Stack technique

- Python 3.11+
- **LangGraph** pour l'orchestration agentique
- **Ollama** en local (avec fallback/mock LLM pour les tests)
- **FastAPI** pour l'API REST
- **ChromaDB** (embarqué) pour le RAG des tickets historiques
- **Pydantic** pour tous les schémas de sortie structurés
- **pytest** pour les tests

## Structure du projet

```
diagnostic-technique/
├── orchestrator/pipeline.py
├── sub_agents/
│   ├── intake_parser/          (prompt.py, agent.py, schemas.py)
│   ├── logs_investigator/
│   ├── context_agent/
│   ├── rag_ticket_search/
│   ├── root_cause_reasoner/
│   ├── remediation_planner/
│   └── guardrail_validator/
├── shared/
│   ├── state.py                # État partagé du graphe
│   ├── audit_logger.py         # Traces JSON
│   └── llm_client.py           # Client Ollama + fallback mock
├── mocks/                      # Données mockées (logs, CRM, commandes, tickets)
├── evaluation/golden_incidents/# Cas d'évaluation + eval_runner.py
├── config/settings.py
├── api/main.py                 # FastAPI (POST /diagnose)
├── tests/
├── docker/docker-compose.yml
├── pyproject.toml
└── README.md
```

## Installation

```bash
cd diagnostic-technique
python -m venv .venv
source .venv/bin/activate  # Windows : .venv\Scripts\activate
pip install -e ".[dev]"
```

Un fichier `.env` avec `MOCK_LLM=true` est déjà présent : le projet fonctionne immédiatement sans Ollama. Pour utiliser un vrai modèle local, installez [Ollama](https://ollama.com/) et téléchargez un modèle compatible JSON mode, par exemple `qwen2.5`.

### Lancer Ollama (optionnel)

```bash
ollama pull qwen2.5
ollama serve
```

### Lancer ChromaDB via Docker (optionnel)

```bash
cd docker
docker compose up -d
```

Par défaut le projet utilise ChromaDB embarqué en local (`data/chroma/`).

## Lancer l'API

```bash
uvicorn api.main:app --reload
```

L'API est disponible sur `http://127.0.0.1:8000`.

## Tester l'API

```bash
curl -X POST "http://127.0.0.1:8000/diagnose" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Coupure fibre client Dupont SARL",
    "description": "Le client Dupont SARL (acc-12345) signale une coupure Internet sur son service svc-fiber-12345. La commande ord-2026-001 est bloquée en provisioning CPE.",
    "priority": "P2"
  }'
```

Réponse : diagnostic structuré complet avec `parsed_incident`, `logs`, `customer_context`, `similar_tickets`, `root_cause`, `remediation`, `risk_level`, `validation_status`, et `traces`.

## Lancer les tests

```bash
pytest tests/
```

En mode `MOCK_LLM=true`, les tests s'exécutent sans dépendance externe.

## Lancer l'évaluation golden

```bash
python -m evaluation.golden_incidents.eval_runner
```

Le runner rejoue les 5 cas mockés et affiche un rapport pass/fail + accuracy globale. Le processus retourne un exit code 0 si tous les cas passent.

## Configuration

Un fichier `.env` est fourni avec `MOCK_LLM=true` pour permettre une exécution locale sans Ollama. Pour utiliser un vrai modèle local, modifiez `.env` :

```env
MOCK_LLM=false
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5
```

Selon votre shell, vous pouvez aussi surcharger la variable :

- Bash / Git Bash : `export MOCK_LLM=true`
- Windows CMD : `set MOCK_LLM=true`
- PowerShell : `$env:MOCK_LLM="true"`

Puis lancer les tests ou l'évaluation :

```bash
pytest tests/
python -m evaluation.golden_incidents.eval_runner
```

## Notes de conception

- **Refus d'hallucination** : `root_cause_reasoner` retourne `cause="indéterminée"` et `confidence="faible"` s'il ne peut citer aucune source.
- **Guardrail** : `guardrail_validator` classe les actions en `Faible/Moyen/Critique` selon `action_whitelist.yaml` et refuse toute action hors whitelist.
- **Pas d'exécution automatique** : le champ `remediation.remediation.note_execution` rappelle explicitement qu'aucune action n'est exécutée automatiquement.
