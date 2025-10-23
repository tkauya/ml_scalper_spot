PYTHON=python3
VENV=.venv

.PHONY: setup run api train test lint fmt

setup:
$(PYTHON) -m venv $(VENV)
$(VENV)/bin/pip install --upgrade pip
$(VENV)/bin/pip install -r requirements.txt

run:
$(PYTHON) -m src.main

api:
uvicorn status_api:app --reload

train:
$(PYTHON) train_ml.py

test:
pytest

lint:
ruff check src tests status_api.py train_ml.py

fmt:
black src tests status_api.py train_ml.py
isort src tests status_api.py train_ml.py
