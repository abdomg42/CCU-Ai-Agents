.PHONY: help install seed seed-tickets seed-zammad test api docker-up docker-down ui ui-build lint

help:
	@echo "Commandes disponibles :"
	@echo "  make install          - Installe les dépendances Python via requirements.txt"
	@echo "  make seed             - Lance le seeding Neo4j (schema + mocks + embeddings)"
	@echo "  make seed-tickets     - Génère les tickets HF + CCU dans mocks/mock_tickets/"
	@echo "  make seed-zammad      - Injecte les tickets mockés dans Zammad"
	@echo "  make test             - Lance pytest"
	@echo "  make api              - Démarre l'API FastAPI en local (port 8000)"
	@echo "  make ui               - Démarre l'interface Streamlit (port 8501)"
	@echo "  make ui-build         - Vérifie que l'app Streamlit se charge sans erreur"
	@echo "  make docker-up        - Démarre toute l'infrastructure via Docker Compose"
	@echo "  make docker-down      - Arrête les conteneurs Docker Compose"

install:
	pip install -r requirements.txt

seed:
	bash scripts/seed_graph.sh

seed-tickets:
	python scripts/seed/generate_tickets.py --count 50
	python scripts/seed/generate_ccu_tickets.py --count 30

seed-zammad:
	python infra/scripts/seed_zammad.py

test:
	pytest tests/ -q

api:
	uvicorn api.main:app --reload

ui:
	streamlit run ui/app.py

ui-build:
	python -c "import streamlit, ui.app"

docker-up:
	cd docker && docker compose up --build

docker-down:
	cd docker && docker compose down
