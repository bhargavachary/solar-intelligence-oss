# Contributing to SolarIntelligence

Thank you for contributing to SolarIntelligence. We welcome contributions that maintain code quality, ensure physical data integrity, and keep dependencies minimal.

---

## Operating Principles

1. **Zero-Dependency Frontend:** The web visualizer (`index.html`) must remain zero-build, runnable by simply serving static files or opening the HTML directly.
2. **Offline Simulation First:** Contributors do not need Waaree inverter hardware to develop or test. Use `MockWaareeAPIClient` and `--mock` mode for all development work.
3. **Data Provenance:** Always clearly distinguish between directly measured sensor telemetry and modeled or estimated metrics (e.g. standard tariff savings or seasonal forecasts).
4. **Schema Integrity:** The output format of `data/dashboard.json` must strictly conform to Schema v5.0. Do not alter top-level keys without auditing `index.html`.
5. **No Credentials in Git:** Real inverter credentials and session tokens must never be committed.

---

## Local Development Workflow

```bash
# Clone the repository
git clone https://github.com/bhargavachary/solar-intelligence.git
cd solar-intelligence

# Install Python requirements
pip install -r requirements.txt

# Run syntax checks
make lint

# Run the test suite
make test

# Run an offline demonstration update (dry-run)
make demo

# Launch local dashboard server
make serve
```

---

## Testing Requirements

Before opening a Pull Request:
1. Ensure all tests pass:
   ```bash
   python3 -m unittest discover -s tests -v
   ```
2. Verify Python bytecode compilation:
   ```bash
   make lint
   ```
3. Test pipeline dry-run with mock data:
   ```bash
   python3 update_data.py --mock --dry-run
   ```
4. If adding new calculation logic or schema fields, add unit tests in `tests/test_calculations.py` or `tests/test_data_schema.py`.

---

## Pull Request Guidelines

1. Create a clean feature branch:
   ```bash
   git checkout -b feat/your-improvement
   ```
2. Ensure commit messages describe the architectural or engineering reason for the change.
3. Fill out the Pull Request template completely.
