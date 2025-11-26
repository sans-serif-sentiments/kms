PYTHON ?= python3
HOST ?= 127.0.0.1
PORT ?= 8300
APP ?= app.api.routes:app
VENV ?= .venv
VENV_BIN ?= $(VENV)/bin
UVICORN ?= $(VENV_BIN)/uvicorn
UI_DIR ?= frontend

# Local model paths (avoid network pulls)
EMBED_MODEL ?= $(CURDIR)/models/bge-small-en
RERANKER_MODEL ?= $(CURDIR)/models/bge-reranker-base
MODEL_ENVS = INDEX__EMBED_MODEL=$(EMBED_MODEL) INDEX__RERANKER_MODEL=$(RERANKER_MODEL)

.PHONY: venv install format lint test run index eval sync ui-install ui-build ui-dev update-kb qa

venv:
	@[ -d $(VENV) ] || $(PYTHON) -m venv $(VENV)

install:
	make venv
	$(VENV_BIN)/pip install --upgrade pip
	$(VENV_BIN)/pip install -r requirements.txt

format:
	$(PYTHON) -m black app tests

lint:
	$(PYTHON) -m ruff check app tests

index:
	$(MODEL_ENVS) $(PYTHON) scripts/initial_index.py

run: venv
	$(MODEL_ENVS) $(UVICORN) $(APP) --host $(HOST) --port $(PORT)

test:
	$(PYTHON) -m pytest -q

eval:
	$(MODEL_ENVS) $(PYTHON) -m app.eval.evaluator

sync:
	curl -X POST http://localhost:$(PORT)/sync

ui-install:
	cd $(UI_DIR) && npm install

ui-build:
	cd $(UI_DIR) && npm run build

ui-dev:
	cd $(UI_DIR) && npm run dev -- --host 127.0.0.1 --port 5173

update-kb:
	$(PYTHON) scripts/fix_frontmatter.py
	$(MAKE) sync

qa:
	$(MODEL_ENVS) $(PYTHON) -m app.eval.evaluator
	$(MODEL_ENVS) $(PYTHON) scripts/kb_lint.py
