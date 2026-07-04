# claude-api-proxy: missing `~/.claude/.credentials.json` despite Claude Code login

## Symptom

Forge/OpenClaw/Hermes requests through `claude-api-proxy` fail with:

```text
LLM error error: ENOENT: no such file or directory, open '/Users/.../.claude/.credentials.json'
```

Direct reproduction:

```bash
curl -i http://127.0.0.1:18801/v1/messages \
  -H 'content-type: application/json' \
  -H 'anthropic-version: 2023-06-01' \
  -d '{"model":"claude-haiku-4-5","max_tokens":1,"messages":[{"role":"user","content":"ping"}]}'
```

## Root-cause shape

Claude Code can be logged in and healthy while no credentials file exists:

```bash
claude auth status
# loggedIn: true, authMethod: claude.ai, subscriptionType: max

ls -l ~/.claude/.credentials.json ~/.claude/credentials.json
# both missing
```

Newer Claude Code stores the live OAuth blob in macOS Keychain. The proxy may have Keychain fallback at startup/health but still hard-read `config.credsPath` on request-time token loading. If request-time code does:

```js
parseCredentialBlob(fs.readFileSync(credsPath, 'utf8'), credsPath)
```

then a missing file throws before Keychain fallback can run.

## Durable fix pattern

Do not require the file to exist before considering Keychain. Use a helper that returns `null` for missing/empty files and only throws on malformed existing files or unexpected I/O errors:

```js
function readCredentialFileOAuth(credsPath) {
  if (!credsPath || credsPath === 'env') return null;
  try {
    if (!fs.existsSync(credsPath) || fs.statSync(credsPath).size === 0) return null;
    return parseCredentialBlob(fs.readFileSync(credsPath, 'utf8'), credsPath);
  } catch (e) {
    if (e && e.code === 'ENOENT') return null;
    throw e;
  }
}
```

Then both sync health/startup token paths and async request token paths should use:

```js
const fileOauth = readCredentialFileOAuth(credsPath);
const keychainOauth = readMacKeychainOAuth();
const oauth = chooseOAuthCredential(fileOauth, keychainOauth);
```

## Regression test

Add a test that sets a Keychain override, passes a definitely missing credential path, and asserts request-time token loading returns the Keychain token instead of throwing `ENOENT`:

```js
test('missing credentials file falls back to macOS Keychain instead of ENOENT', async () => {
  proxy._setKeychainOverrideForTesting({
    accessToken: 'keychain-token',
    refreshToken: 'keychain-refresh',
    expiresAt: Date.now() + 60 * 60 * 1000,
    subscriptionType: 'max',
  });

  const tok = await proxy.getTokenAsync('/tmp/definitely-missing-claude-credentials.json');
  assert.strictEqual(tok.accessToken, 'keychain-token');
  assert.strictEqual(tok.subscriptionType, 'max');
});
```

## Verification ladder

1. Reproduce original 500 with direct curl before patch if possible.
2. Run the targeted OAuth/token test file.
3. Run the full suite if time permits.
4. Restart the launchd service.
5. Check `/health` is `ok`, not just HTTP 200.
6. Send a real `/v1/messages` request using a model from `/v1/models`; stale model aliases can produce unrelated 404s.
7. Check launchd `runs`, `pid`, `last exit code`, and recent logs for `ENOENT`/crash signatures.

## Pitfall

A passing `claude auth status` does **not** prove a file exists. Treat Claude Code auth as two credential sources: file and Keychain. Debug provider state separately from proxy credential-source drift.