# Google Workspace OAuth setup quirks

Observed in the installed Hermes profile:

- `setup.py --client-secret PATH` must be run before `--auth-url` / `--auth-code`.
- This installed `setup.py` version does not accept `--services` or `--format` flags.
- `setup.py --auth-url` prints the raw authorization URL to stdout and also performs any missing dependency install step.
- The generated auth flow currently grants the full Workspace scope set defined by the installed script (Gmail, Calendar, Drive, Contacts, Sheets, Docs).
- After approval, the redirect to `http://localhost:1` is expected; the user should paste the full redirected URL back into `--auth-code`.
- `setup.py --check` confirms the token is valid at the profile-local path under `~/.hermes/profiles/<profile>/google_token.json`.

Recommended flow:

```bash
python "$HERMES_HOME/skills/productivity/google-workspace/scripts/setup.py" --client-secret /path/to/client_secret.json
python "$HERMES_HOME/skills/productivity/google-workspace/scripts/setup.py" --auth-url
python "$HERMES_HOME/skills/productivity/google-workspace/scripts/setup.py" --auth-code 'http://localhost:1/?code=...&state=...'
python "$HERMES_HOME/skills/productivity/google-workspace/scripts/setup.py" --check
```
