.PHONY: setup synth all tune app test reset-demo lint clean

PY=.venv/bin/python

setup:
	python3.11 -m venv .venv && .venv/bin/pip install -r requirements.txt && .venv/bin/pip install -e .

synth:
	$(PY) -m storesignal.synth

all:
	$(PY) -m storesignal.cli all

tune:
	$(PY) -m storesignal.cli tune

app:
	.venv/bin/streamlit run app/Home.py

test:
	.venv/bin/pytest -q

reset-demo:
	rm -f data/processed/tracker.sqlite && $(PY) -m storesignal.cli alerts

lint:
	.venv/bin/ruff check src tests app

clean:
	rm -rf data/interim data/processed reports/briefs reports/figures models/*.joblib
