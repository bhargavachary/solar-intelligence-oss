.PHONY: help test lint demo serve clean

PYTHON ?= python3

help:
	@echo "SolarIntelligence — Developer Commands"
	@echo "======================================"
	@echo "  make test      Run unit test suite (42 tests)"
	@echo "  make lint      Compile-check all Python modules"
	@echo "  make demo      Run update pipeline with simulated telemetry (dry-run)"
	@echo "  make serve     Start local HTTP server on :8080 to view dashboard"
	@echo "  make clean     Clean python bytecode artifacts"

test:
	$(PYTHON) -m unittest discover -s tests -v

lint:
	$(PYTHON) -m py_compile waaree_api_client.py scraper_api.py update_data.py
	$(PYTHON) -m py_compile tests/*.py

demo:
	$(PYTHON) update_data.py --mock --dry-run

serve:
	@echo "Starting dashboard server at http://localhost:8080 ... (Ctrl+C to stop)"
	$(PYTHON) -m http.server 8080

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
