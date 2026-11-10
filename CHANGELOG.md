# Changelog

All notable changes to SolarIntelligence will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added
- **API Client Exception Resilience:** Wrapped network drops (`requests.exceptions.RequestException`) and malformed JSON responses in `waaree_api_client.py` into structured `WaareeAPIError` exceptions.
- **Resilience Unit Tests:** Added unit tests in `tests/test_api_client.py` asserting proper error translation on network drops, HTTP 503 errors, and invalid server payloads (expanding test suite from 42 to 45 passing tests).
- **Open Source Governance Documentation:** Added comprehensive `CONTRIBUTING.md`, `SECURITY.md`, PR template, and GitHub issue templates.

### Security
- **CI Secret Memory Hardening:** Updated `.github/workflows/solar_update.yml` to inject `WAAREE_CREDENTIALS` directly into pipeline memory via environment variables, eliminating temporary physical credential files on CI runners.
- **CI Minimal Permissions:** Added explicit `permissions: contents: read` to `.github/workflows/ci.yml`.

---

## [5.0.0] - 2026-11-08

### Added
- Standardized Schema v5.0 payload format for `data/dashboard.json`.
- Full mock API client pipeline (`--mock`) enabling complete offline development without Waaree hardware.
- Developer `Makefile` with targets: `test`, `lint`, `demo`, `serve`, `clean`.
- Continuous integration matrix across Python 3.9 through 3.12.
