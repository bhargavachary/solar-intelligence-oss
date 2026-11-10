# Security Policy

SolarIntelligence processes solar generation telemetry and interacts with the Waaree / FoxESS Cloud REST API. The security of credential handling and data storage is taken seriously.

---

## Supported Versions

| Version | Supported |
|---|---|
| `main` (Schema v5.0) | Yes |
| < Schema v5.0 | No |

---

## Credential Safety & Boundaries

1. **No Credentials in Version Control:**
   - `credentials.json`, `.waaree_token.json`, and all token caches are strictly `.gitignore`d.
   - GitHub Actions workflows pass credentials exclusively via secure repository secrets (`WAAREE_CREDENTIALS`) directly through environment variables in memory, without writing credentials to disk on CI runners.

2. **Read-Only Telemetry:**
   - SolarIntelligence interacts exclusively with read-only telemetry endpoints (`/c/v0/device/list`, `/generic/v0/plant/history/report`). It does not send write or control commands to inverter hardware or grid interconnects.

3. **Atomic File Operations:**
   - All output file writes (`dashboard.json`, `energy_history.csv`, and daily energy logs) use atomic temporary file replacement (`os.replace`) to prevent corrupted states on process interruption.

---

## Reporting a Security Vulnerability

If you identify a security issue, sensitive credential exposure, or insecure API interaction:
- Please report it responsibly via email to **`contact@bhargavachary.com`** or via the contact form at [`https://bhargav.work/contact/`](https://bhargav.work/contact/).
- Do not open a public GitHub issue for sensitive security or credential vulnerabilities.
- We acknowledge security reports within 48 hours and work with you to coordinate a timely resolution.
