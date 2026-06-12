# Google Workspace auth quirks (joblandagent-dev)

This profile's installed `setup.py` supports only:
- `--check`
- `--client-secret PATH`
- `--auth-url`
- `--auth-code CODE`
- `--revoke`
- `--install-deps`

Notably:
- `--services` is not accepted here.
- `--format json` is not accepted here.
- `--auth-url` emits a full Workspace consent URL (Gmail + Calendar + Drive + Contacts + Sheets + Docs).

Observed flow:
1. Save client secret:
   `python .../setup.py --client-secret /path/to/client_secret.json`
2. Get auth URL:
   `python .../setup.py --auth-url`
3. Open URL, approve, and copy the full redirected URL from the browser.
4. Exchange code:
   `python .../setup.py --auth-code 'http://localhost:1/?code=...'`
5. Verify:
   `python .../setup.py --check`

The localhost:1 redirect is expected; the browser often errors after approval. The important part is the full redirected URL/callback value.