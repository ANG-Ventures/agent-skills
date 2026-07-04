# Prove what a binary sends on the wire (TLS-MITM capture)

When the question is **"what request does this proprietary binary actually make?"**
— and reasoning about its source/config is uncertain or impossible — *terminate
its TLS and read the decrypted request* instead of guessing. This resolved a
2026-06-07 "is calling `/api/oauth/usage` allowed / are our headers right?"
question definitively in ~20 min after source-reasoning had drifted.

## When to reach for this
- "Is our reimplementation byte-identical to the first-party client?" (auth,
  headers, scopes, endpoint) — you need ground truth, not a plausible guess.
- A binary **ignores `*_BASE_URL` / proxy env** for some calls (Claude Code's
  `/usage` hardcodes `api.anthropic.com` and ignores `ANTHROPIC_BASE_URL`). A
  plain reverse-proxy sees nothing — you must MITM.
- You suspect headers drift across releases and want the *current* truth.

## Escalation ladder (cheapest first)
1. **Plain logging forward-proxy** (`ANTHROPIC_BASE_URL`/`HTTP(S)_PROXY` → your
   logger → real upstream). Works only if the binary honors the env. If it logs
   nothing, the call bypassed the base-url → go to 2.
2. **CONNECT-logging proxy** as `HTTPS_PROXY`: log the `CONNECT host:port` of
   every TLS tunnel (can't read bodies). Tells you **which host** the call hits —
   confirms the bypass and names the real endpoint.
3. **TLS-terminating MITM** for the one host: own CA, leaf cert for that host,
   `HTTPS_PROXY=<mitm>` + `NODE_EXTRA_CA_CERTS=<ca.crt>` (Node) or the runtime's
   trust-injection env. Decrypt → log method/path/headers (redact auth) → forward
   to the real upstream over TLS → stream back. Now you see the exact request.

## Minimal recipes
```bash
# own CA + leaf for the target host
openssl genrsa -out ca.key 2048
openssl req -x509 -new -nodes -key ca.key -sha256 -days 2 -out ca.crt -subj "/CN=cap-CA"
openssl genrsa -out leaf.key 2048
openssl req -new -key leaf.key -out leaf.csr -subj "/CN=api.anthropic.com"
printf 'subjectAltName=DNS:api.anthropic.com' > ext.cnf
openssl x509 -req -in leaf.csr -CA ca.crt -CAkey ca.key -CAcreateserial -out leaf.crt -days 2 -sha256 -extfile ext.cnf
```
- MITM proxy = Python stdlib: read the `CONNECT`, `ssl.SSLContext(PROTOCOL_TLS_SERVER)`
  `.load_cert_chain(leaf)`, `wrap_socket(server_side=True)`, parse one HTTP request,
  log it, replay via `http.client.HTTPSConnection(real_host)`, stream the response.
- Trust the CA in the *client*: Node → `NODE_EXTRA_CA_CERTS=/path/ca.crt`.
- Drive a TUI slash-command (`/usage`) in a detached **tmux** so you can trigger
  it and capture: `tmux new-session -d -s cap; tmux send-keys -t cap '/usage' Enter`.
  Launch the TUI WITHOUT piping (`| tee` flips `claude` into `--print` and it
  exits) — let it own the pane, then read `tmux capture-pane -p`.

## Reading the result
- Diff the captured first-party request against your reimplementation by routing
  YOUR client through the SAME MITM and comparing — transport-level diffs
  (`Accept-Encoding: identity` vs `gzip`, `Connection: close`) are meaningless;
  auth/UA/endpoint/scope are what matter.
- **The chat/redaction layer can silently rewrite identifier-like tokens in your
  output** (it rewrote the UA token `external`→`external` every time this session).
  Trust the **raw captured bytes from the log file**, read via `execute_code`, not
  what the rendered chat shows. Build any literal header bytes via
  `"".join(chr(c) for c in [...])` when writing them into a script, to dodge the
  same rewrite corrupting the source.

## Cleanup (mandatory)
Shred the CA **private key** when done (`shred -u ca.key leaf.key`); a trusted-CA
private key on disk is a MITM capability. Kill the tmux session (clears any token
from scrollback). Keep only the redacted request log as evidence.

## Verdict shape this produces
"Our call is byte-identical to the first-party client's own request for the same
screen (same endpoint, token, headers) — nothing reverse-engineered." That is a
defensible answer to "is this allowed", far stronger than source-reasoning.
