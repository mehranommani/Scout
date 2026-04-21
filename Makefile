.PHONY: setup infra backend frontend test health stop

# ── First-time setup ──────────────────────────────────────────────────────────
setup:
	bash setup.sh

# ── Infrastructure ────────────────────────────────────────────────────────────
infra:
	docker compose up -d

infra-stop:
	docker compose down

# ── Backend ───────────────────────────────────────────────────────────────────
backend:
	cd backend && source .venv/bin/activate && uvicorn main:app --reload --port 8000

# ── Frontend ──────────────────────────────────────────────────────────────────
frontend:
	cd frontend && npm run dev

# ── Tests ─────────────────────────────────────────────────────────────────────
test:
	cd tests && python3 -m pytest -v

# ── Health check ──────────────────────────────────────────────────────────────
health:
	@curl -s http://localhost:8000/api/health | python3 -m json.tool

# ── Langfuse evaluator setup (one-time) ──────────────────────────────────────
evals:
	bash backend/setup_langfuse_evals.sh
