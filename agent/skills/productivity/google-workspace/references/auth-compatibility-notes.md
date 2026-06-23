# Google Workspace auth compatibility notes

Observed in this profile:

- `scripts/setup.py --help` exposes only:
  - `--check`
  - `--check-live`
  - `--client-secret PATH`
  - `--auth-url`
  - `--auth-code CODE`
  - `--revoke`
  - `--install-deps`
- The installed `setup.py` does not accept the documented `--services` or `--format` flags.
- `--auth-url` may auto-install Google API dependencies on first run.
- The resulting consent URL requested a broad Workspace grant:
  - Gmail readonly/send/modify
  - Calendar
  - Drive
  - Contacts readonly
  - Sheets
  - Docs
- The working flow was:
  1. `--client-secret /path/to/client_secret.json`
  2. `--auth-url`
  3. user approves in browser
  4. user pastes the full redirected `http://localhost:1/?code=...` URL back
  5. `--auth-code 'PASTED_URL_OR_CODE'`
  6. `--check`

Keep this file updated when the local auth tool behavior changes.