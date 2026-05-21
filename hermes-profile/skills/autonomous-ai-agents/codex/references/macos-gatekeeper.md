# macOS Gatekeeper / XProtect Blocks Codex CLI

## Issue Context

Multiple open GitHub issues track macOS flagging the Codex native binary as malware:

- [#22135] "codex-aarch64-apple-darwin was not opened because it contains malware" (closed, no fix)
- [#21199] `spawn Unknown system error -88` — binary present but XProtect blocks execution (open)
- [#18985] Codex CLI notarization failure (open)
- [#22194] "Cannot open Codex because of a malware" detected by macOS (open)

## Error Signatures

### ENOENT variant (binary already deleted by XProtect)

```
Error: spawn /Users/.../pnpm/global/5/.pnpm/@openai+codex@0.118.0-darwin-arm64/...
/node_modules/@openai/codex/vendor/aarch64-apple-darwin/codex/codex ENOENT
    at ChildProcess._handle.onexit (node:internal/child_process:285:19)
```

### spawn error variant (binary exists but blocked)

```
Error: spawn Unknown system error -88
    at ChildProcess.spawn (node:internal/child_process:440:11)
```

## Diagnostic Commands

Check if binary exists:
```sh
file /opt/homebrew/lib/node_modules/@openai/codex/node_modules/@openai/codex-darwin-arm64/vendor/aarch64-apple-darwin/codex/codex
```

Check code signing:
```sh
codesign -dv /path/to/codex/binary
# → "code object is not signed at all"
```

Check Gatekeeper assessment:
```sh
spctl --assess --type execute -vv /path/to/codex/binary
# → "invalid or unsupported format for signature"
```

Check quarantine xattr:
```sh
xattr -l /path/to/codex/binary
# → "com.apple.provenance: ..." or "com.apple.quarantine: ..."
```

## Workaround Comparison

| Method | Reliability | Notes |
|--------|-----------|-------|
| GitHub Release + xattr | Best | Binary fresh, not from npm cache |
| xattr on npm install | Good | Must act before XProtect scans |
| Ad-hoc codesign | Moderate | Only works if binary still on disk |
| `spctl --master-disable` | Last resort | Disables all Gatekeeper |

## Root Cause

Apple's notarization service rejects the Codex binary (unsigned binary, no Apple
Developer ID signing). Recent macOS versions (15.x) have stricter enforcement
via XProtect which auto-deletes flagged binaries. OpenAI needs to re-sign and
re-notarize their releases.
