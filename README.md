# Diagnostic Technique CCU

Agent IA de diagnostic technique pour le système d'information télécom **CCU** (Commande et Catalogue Unifiés), basé sur les APIs **TMF620** (Product Catalog) et **TMF622** (Product Ordering).

L'agent analyse des incidents techniques en corrélant :
- des logs réseau,
- l'historique client (CRM),
- les tickets d'incidents historiques (Jira/ServiceNow via GraphRAG Neo4j),

pour **diagnostiquer, rapporter et notifier** — **aucune action technique n'est jamais exécutée automatiquement** sur un système réel. Le seul guardrail est un guardrail de **contenu/PII** avant tout envoi externe.

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
ticket_manager
  │
  ▼
remediation_explainer
  │
  ▼
content_guardrail (PII)
  │
  ▼
report_generator (PDF)
  │
  ▼
notifier (email + note Zammad) 
  │
  ▼
END
```

Les trois agents collecteurs (`logs_investigator`, `context_agent`, `rag_ticket_search`) s'exécutent **en parallèle** dans le nœud `collectors` de LangGraph (via `asyncio.gather` / fallback `ThreadPoolExecutor`).

`rag_ticket_search` et `ticket_manager` s'appuient sur **Neo4j GraphRAG** : recherche vectorielle native sur les embeddings des tickets, filtrée par proximité de graphe (même produit / même type de commande).

## Stack technique

- Python 3.11+
- **LangGraph** pour l'orchestration agentique
- **Ollama** en local pour le LLM (`qwen2.5:latest`) et les embeddings (`mxbai-embed-large:latest`), avec fallback/mock LLM pour les tests
- **FastAPI** pour l'API REST
- **Neo4j** (graphe + index vectoriel) pour le GraphRAG des tickets historiques
- **Interface d'embedding abstraite** : Ollama par défaut, extensible à sentence-transformers, OpenAI ou Voyage AI
- **Pydantic** pour tous les schémas de sortie structurés
- **pytest** pour les tests
- **Streamlit** pour l'interface utilisateur (remplace Next.js)

## Structure du projet

```
diagnostic-technique/
├── orchestrator/pipeline.py
├── sub_agents/
│   ├── intake_parser/
│   ├── logs_investigator/
│   ├── context_agent/
│   ├── rag_ticket_search/       # Appelle graph.queries.search_similar_incidents
│   ├── root_cause_reasoner/
│   ├── ticket_manager/            # Mapping/création de tickets via backend abstrait
│   ├── remediation_explainer/   # Texte informatif (pas d'action exécutable)
│   ├── content_guardrail/       # PII sanitizer
│   ├── report_generator/        # Générateur PDF pur Python
│   └── notifier/                # Email + note ticketing
├── graph/                       # GraphRAG Neo4j
│   ├── schema.cypher            # Contraintes + index vectoriel
│   ├── graph_client.py          # Wrapper driver Neo4j avec retry
│   ├── embedding_provider.py    # Interface abstraite d'embedding
│   ├── queries.py               # Requête GraphRAG principale
│   ├── neo4j_style.grass        # Style multi-couleurs pour Neo4j Browser
│   └── ingestion/               # Scripts de seeding des mocks
│       ├── ingest_clients.py
│       ├── ingest_orders.py
│       ├── ingest_tickets.py
│       ├── ingest_logs.py
│       ├── generate_embeddings.py
│       └── run_all.py
├── data/                        # Données brutes et pipeline d'ingestion
│   ├── raw/                     # Fichiers sources CSV/JSON/YAML
│   └── ingestion/               # Pipeline générique de détection/mapping/liaison
│       ├── detect_and_load.py
│       ├── schema_mapper.py
│       ├── entity_linker.py
│       └── run_ingestion.py
├── tools/                       # Clients bas niveau (ticketing, CRM)
│   ├── ticketing/               # Abstraction du backend de ticketing
│   │   ├── base.py              # Interface TicketingBackend
│   │   ├── zammad_backend.py    # Implémentation Zammad
│   │   └── __init__.py          # Factory get_ticketing_backend()
│   ├── ticketing_client.py      # Facade rétrocompatible
│   └── crm_client.py            # Client Postgres CRM
├── services/                    # Webhook receiver + worker Kafka
│   ├── webhook_receiver.py
│   └── worker.py
├── shared/
├── mocks/
├── evaluation/
├── config/settings.py
├── api/                         # FastAPI + routes SSE
│   ├── main.py
│   └── routes/diagnose.py
├── tests/
├── ui/                          # Interface Streamlit legacy (page chat unique)
├── ui_streamlit/                # Application Streamlit multi-pages
│   ├── app.py                   # Page d'accueil
│   ├── shared.py
│   ├── assets/custom.css        # Thème sombre
│   └── pages/
│       ├── 1_💬_Chat.py
│       ├── 2_📊_Dashboard.py
│       ├── 3_🕸️_Graph_Explorer.py
│       ├── 4_🎫_Tickets.py
│       └── 5_⚙️_Settings.py
├── docker/
│   ├── docker-compose.yml
│   └── Dockerfile
├── scripts/
│   ├── seed_graph.sh            # Seed Neo4j en une commande
│   └── seed/                    # Génération de tickets
│       ├── generate_tickets.py
│       └── generate_ccu_tickets.py
├── infra/
│   └── scripts/seed_zammad.py   # Injection des tickets dans Zammad
├── reports/                     # Rapports PDF générés
├── pyproject.toml
└── README.md
```

## Installation

```bash
python -m venv .venv
source .venv/bin/activate  # Windows : .venv\Scripts\activate
pip install -r requirements.txt
```

Un fichier `.env` avec `MOCK_LLM=true` est déjà présent : le projet fonctionne immédiatement sans Ollama. Pour utiliser les modèles locaux, installez [Ollama](https://ollama.com/) et téléchargez les modèles configurés :

```bash
ollama pull qwen2.5:latest
ollama pull mxbai-embed-large:latest
ollama serve
```

### Lancer Neo4j (local uniquement)

Neo4j doit être installé et exécuté **localement** (pas dans Docker). Par défaut, le projet se connecte à `bolt://localhost:7687` avec les credentials `neo4j/password` (modifiable dans `.env`).

Avec Neo4j Desktop / Neo4j local démarré :

```bash
# Assurez-vous que le venv est activé (PowerShell : .venv\Scripts\activate)
bash scripts/seed_graph.sh
```

> `scripts/seed_graph.sh` détecte automatiquement `.venv/Scripts/python.exe` sous Windows ou `.venv/bin/python` sous Linux/macOS.

Si vous préférez lancer l'API dans Docker tout en gardant Neo4j local et Ollama local :

```bash
cd docker
docker compose up --build api
```

Dans ce cas, l'API se connecte à Neo4j via `host.docker.internal:7687` et à Ollama via `host.docker.internal:11434`. Elle est disponible sur `http://127.0.0.1:8000`.

## Lancer l'API

Après avoir seedé Neo4j :

```bash
uvicorn api.main:app --reload
```

L'API est disponible sur `http://127.0.0.1:8000`.

## Tester l'API

Utilisez le fichier `body.json` créé à la racine ou composez votre propre requête :

```bash
curl -X POST "http://127.0.0.1:8000/diagnose" \
  -H "Content-Type: application/json" \
  -d @body.json
```

Réponse : diagnostic structuré complet avec `parsed_incident`, `logs`, `customer_context`, `similar_tickets`, `root_cause`, `remediation`, `risk_level`, `validation_status`, et `traces`.

Pour une sortie plus lisible dans le terminal avec `curl` :

```bash
curl -X POST "http://127.0.0.1:8000/diagnose/text" \
  -H "Content-Type: application/json" \
  -d @body.json
```

## Lancer les tests

```bash
pytest tests/ -q
```

Les tests `test_graph_ingestion.py` et `test_rag.py` nécessitent Neo4j accessible. Ils seedent le graphe automatiquement et vérifient les compteurs de nœuds/relations et la recherche de tickets similaires.

## Visualisation dans Neo4j Browser / Neo4j Desktop

Pour afficher les nœuds avec des couleurs différentes selon leur label, appliquez le style GRASS fourni. Cela fonctionne à l'identique dans Neo4j Browser (navigateur) et dans l'interface graphique de Neo4j Desktop.

1. Ouvrez votre instance dans Neo4j Browser (`http://localhost:7474`) ou dans Neo4j Desktop.
2. Exécutez une requête affichant des nœuds, par exemple :
   ```cypher
   MATCH (n)-[r]->(m) RETURN n, r, m LIMIT 100
   ```
3. Ouvrez le panneau **Style** (icône de pinceau en haut à gauche du résultat, ou bouton "Style").
4. Cliquez sur **Import / Load Style** et sélectionnez `graph/neo4j_style.grass`.

Ou copiez-collez le contenu du fichier dans la barre de commande Neo4j Browser précédé de `:style`.

Couleurs utilisées :
- `Client` — bleu
- `Subscription` — vert
- `Product` — orange
- `Order` — violet
- `LogEvent` — rouge
- `Ticket` — jaune

## Lancer l'évaluation golden

```bash
python -m evaluation.golden_incidents.eval_runner
```

Le runner rejoue les 5 cas mockés et affiche un rapport pass/fail + accuracy globale. Le processus retourne un exit code 0 si tous les cas passent.

## Pipeline d'ingestion générique (`data/ingestion`)

Le pipeline détecte automatiquement les fichiers placés dans `data/raw/`, les mappe vers le schéma cible du graphe, puis crée des liens synthétiques déterministes entre sources indépendantes.

```bash
python -m data.ingestion.run_ingestion
```

Mode dry-run (détection/mapping/liaison sans écrire dans Neo4j/Postgres) :

```bash
python -m data.ingestion.run_ingestion --dry-run
```

Modules :

- `detect_and_load.py` — scanne `data/raw/` et charge CSV/JSON/YAML avec le bon parser.
- `schema_mapper.py` — mapping explicite vers `Client`, `Ticket`, `LogEvent`, `Product`. Les champs manquants restent `null` et sont loggués.
- `entity_linker.py` — liens synthétiques traçables :
  - `client_id` par hash déterministe du `ticket_id` modulo le nombre de clients CRM.
  - `order_id` au format `ORD-XXXXX`.
  - logs dont la sévérité correspond à la priorité du ticket.
  - produit dérivé des specs TM Forum et de la catégorie.
- `run_ingestion.py` — orchestration idempotente, écrit dans Neo4j et Postgres, affiche le rapport final.

## Abstraction du backend de ticketing (`tools/ticketing`)

Le backend est configurable via `TICKETING_BACKEND` (défaut `zammad`). Seule l'interface `TicketingBackend` est utilisée par les `sub_agents`.

```python
from tools.ticketing import get_ticketing_backend

backend = get_ticketing_backend()
backend.create_ticket(title=..., body=...)
backend.search_tickets("query")
backend.add_note(ticket_id, body)
backend.get_ticket(ticket_id)
```

Implémentations :

- `tools.ticketing.zammad_backend.ZammadBackend`

Variables d'environnement Zammad :

```env
TICKETING_BACKEND=zammad
ZAMMAD_URL=http://localhost:3000
ZAMMAD_TOKEN=your-token
ZAMMAD_DEFAULT_GROUP=Users
```

## Interface Streamlit multi-pages (`ui_streamlit`)

Application native multi-pages avec navigation automatique par préfixe numérique.

```bash
streamlit run ui_streamlit/app.py
```

Pages accessibles :

| Page | URL auto | Description |
|---|---|---|
| Accueil | `/` | Redirection vers les pages |
| 💬 Chat | `/Chat` | Diagnostic conversationnel existant |
| 📊 Dashboard | `/Dashboard` | KPIs Neo4j/Postgres avec Plotly |
| 🕸️ Graph Explorer | `/Graph_Explorer` | Sous-graphe interactif streamlit-agraph |
| 🎫 Tickets | `/Tickets` | Liste filtrée via backend ticketing |
| ⚙️ Settings | `/Settings` | Backend actif, statut ingestion, relance |

Le thème sombre est appliqué via `ui_streamlit/assets/custom.css` chargé dans chaque page.

## Messaging Kafka

Docker Compose lance Zookeeper et Kafka (`kafka:9092`). En local, les services utilisent `localhost:9092`.

```bash
python services/webhook_receiver.py  # uvicorn services.webhook_receiver:app --port 9000
python services/worker.py
```

Variables d'environnement Kafka :

```env
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_TOPIC=ccu-incidents
KAFKA_GROUP_ID=ccu-worker
```

## Configuration

Variables d'environnement disponibles (voir `.env.example`) :

```env
MOCK_LLM=true

# Ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:latest

# Neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password
NEO4J_DATABASE=neo4j

# Embeddings (Ollama par défaut)
EMBEDDING_PROVIDER=ollama
EMBEDDING_MODEL=mxbai-embed-large:latest
VECTOR_INDEX_DIM=1024
VECTOR_SIMILARITY_THRESHOLD=0.75
```

Pour basculer vers un autre provider d'embedding (sentence-transformers, OpenAI, Voyage AI), implémentez `EmbeddingProvider` dans `graph/embedding_provider.py` et changez `EMBEDDING_PROVIDER` / `EMBEDDING_MODEL` / `VECTOR_INDEX_DIM` en conséquence.

## Commandes utiles

```bash
pip install -r requirements.txt
bash scripts/seed_graph.sh            # Seed Neo4j local (schema + mocks + embeddings)
pytest tests/ -q                        # Nécessite Neo4j local lancé
uvicorn api.main:app --reload           # API FastAPI locale
streamlit run ui_streamlit/app.py       # Interface Streamlit

cd docker && docker compose up --build api    # API seule dans Docker (Neo4j local requis)
cd docker && docker compose down              # Arrêter les conteneurs
```

## Notes de conception

- **GraphRAG** : `rag_ticket_search` utilise `graph/queries.search_similar_incidents` qui combine l'index vectoriel Neo4j et un filtre de proximité de graphe (même produit / même commande).
- **Seuil de similarité** : configurable via `VECTOR_SIMILARITY_THRESHOLD` (défaut 0.75). Aucun résultat sous ce seuil n'est retourné.
- **Refus d'hallucination** : `root_cause_reasoner` retourne `cause="indéterminée"` et `confidence="faible"` s'il ne peut citer aucune source.
- **Guardrail** : `guardrail_validator` classe les actions en `Faible/Moyen/Critique` selon `action_whitelist.yaml` et refuse toute action hors whitelist.
- **Pas d'exécution automatique** : le pipeline s'arrête à "action proposée" et ne déclenche jamais d'action corrective automatiquement.

## Lancement complet depuis zéro

### 1. Variables d'environnement

Copier `.env.example` en `.env` et ajuster si besoin :

```bash
cp .env.example .env
```

Points importants :
- `MOCK_LLM=true` pour démarrer sans Ollama (mode déterministe/fallback).
- `ZAMMAD_TOKEN` : token API Zammad (à créer dans l'UI Zammad une fois démarré).
- `ANTHROPIC_API_KEY` : facultatif, pour générer les tickets CCU via Claude (fallback déterministe sinon).

### 2. Démarrer l'infrastructure (recommandé)

Le plus simple est Docker Compose :

```bash
cd docker
docker compose up --build
```

Cela démarre : API FastAPI (8000), Zammad (3000), Splunk (18000/8088), Prism (4010), Zookeeper + Kafka. Neo4j doit être démarré séparément sur l'hôte.

> Le rapport PDF est généré directement en Python sans dépendance à WeasyPrint ou aux librairies GTK/Pango.

### 3. Seed des données

Dans un autre terminal (avec l'API et Neo4j démarrés) :

```bash
# Seed Neo4j (clients, commandes, logs, tickets + embeddings)
bash scripts/seed_graph.sh

# Générer des tickets mockés
python scripts/seed/generate_tickets.py --count 50
python scripts/seed/generate_ccu_tickets.py --count 30

# Injecter les tickets dans Zammad (une fois Zammad healthy)
python infra/scripts/seed_zammad.py
```

### 4. Démarrer l'interface utilisateur (sans Docker)

```bash
# Terminal 1 : backend
uvicorn api.main:app --reload

# Terminal 2 : frontend Streamlit
streamlit run ui_streamlit/app.py
```

Ouvrir http://localhost:8501.

## Scénario de test de bout en bout

1. Démarrer l'interface Streamlit : http://localhost:8501.
2. Saisir un message en langage naturel, par exemple :
   > "Client acc-12345, service svc-fiber-12345, commande ord-2026-001. Coupure Internet fibre."
3. Observer dans le chat :
   - le message utilisateur,
   - la trace agent (intake → collectors → root_cause → ticket_manager → remediation_explainer → content_guardrail → report_generator → notifier),
   - le badge de mapping : "New ticket created (#TICK-CCU-XXXX)",
   - la carte de rapport avec le bouton "Download PDF report" et le badge "Email sent to ...".
4. Vérifier la réception de l'email de notification dans la boîte des destinataires configurés (`REPORT_RECIPIENTS`).
5. Vérifier dans Zammad (http://localhost:3000) que le nouveau ticket contient une note interne "Full report sent by email".
