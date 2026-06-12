# Google Workspace auth flow quirks

Session-derived notes for the installed Hermes Google Workspace skill.

## Installed setup script behavior

The local `scripts/setup.py` in this profile supports only these flags:

- `--check`
- `--check-live`
- `--client-secret PATH`
- `--auth-url`
- `--auth-code CODE`
- `--revoke`
- `--install-deps`

It does not accept `--services` or `--format` even though some older docs mention them.

## Working setup sequence

1. Save the OAuth client JSON:
   `python .../setup.py --client-secret /path/to/client_secret.json`
2. Print the authorization URL:
   `python .../setup.py --auth-url`
3. Open the URL, approve access, and copy the full redirected URL from the browser address bar.
4. Exchange the code:
   `python .../setup.py --auth-code 'http://localhost:1/?code=...'`
5. Verify:
   `python .../setup.py --check`

## Notes

- The auth URL redirects to `http://localhost:1` after approval; that is expected.
- The installed tool requested the full Workspace consent set in this session (Gmail, Calendar, Drive, Contacts, Sheets, Docs).
- When the auth code is pasted back, passing the entire redirected URL works; extracting only the `code=` value also works in many cases, but the full URL is safest.