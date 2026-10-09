.PHONY: help install test lint run up down logs load k8s-deploy k8s-delete

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

install: ## Install dev dependencies
	pip install -r requirements-dev.txt

test: ## Run unit tests
	pytest -q

lint: ## Lint with ruff
	ruff check .

run: ## Run the API locally with autoreload
	uvicorn app.main:app --reload

up: ## Start full stack (API + Prometheus + Grafana)
	docker compose up --build -d

down: ## Stop the stack
	docker compose down

logs: ## Tail stack logs
	docker compose logs -f

load: ## Fire a few scans to populate metrics
	@for u in https://github.com https://example.com https://cloudflare.com; do \
		curl -s "http://localhost:8000/scan?url=$$u" >/dev/null && echo "scanned $$u"; \
	done

k8s-deploy: ## Apply Kubernetes manifests
	kubectl apply -f k8s/

k8s-delete: ## Delete Kubernetes resources
	kubectl delete -f k8s/
