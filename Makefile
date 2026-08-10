.PHONY: help install seed test api docker-up docker-down lint

help:
	@echo "Commandes disponibles :"
	@echo "  make install      - Installe les dépendances via requirements.txt"
	@echo "  make seed         - Lance le seeding Neo4j (schema + mocks + embeddings)"
	@echo "  make test         - Lance pytest"
	@echo "  make api          - Démarre l'API FastAPI en local"
	@echo "  make docker-up    - Démarre l'API via Docker Compose (Neo4j local requis)"
	@echo "  make docker-down  - Arrête les conteneurs Docker Compose"

install:
	pip install -r requirements.txt

seed:
	bash scripts/seed_graph.sh

test:
	pytest tests/ -q

api:
	uvicorn api.main:app --reload

docker-up:
	cd docker && docker compose up --build api

docker-down:
	cd docker && docker compose down
