# Adversarial CLI / library dogfood — the bug classes a "12 PASS, ship it" run hides (2026-06-12)

When the deliverable is a **CLI or library** (not a web app — that's the `dogfood` skill), the "let's try
to break it" pass has its own recurring high-value catches. This came out of hardening a web-scraping
stealth-tools system that was already green: a deliberate adversarial round found **3 real bugs + 1 parity
bug** that the happy-path smoke + a 3-pass Opus review had all missed.

## 1. URL/path inputs to a tool that DRIVES a browser or subprocess = SSRF / local-file-read surface
The highest-severity catch. `cf_harvest.py <url>` handed any string straight to the stealth browser.
Probing `file:///etc/&#8203;passwd` → the browser **fetched it (200)** — a local-file-read / SSRF primitive.
`data:` and `ftp://` likewise reached the engine. Fix = a **scheme allowlist at the entry point**:
```python
def validate_url(url):
    p = urlparse(url)
    if p.scheme not in ("http", "https"): return f"refused scheme '{p.scheme}'"
    if not p.netloc: return "missing host"
    return ""
```
Rule: **any tool that accepts a URL/path and feeds it to a browser, `subprocess`, file open, or an
SSR fetch must allowlist the scheme/shape BEFORE the dangerous call.** Lock it with a parametrized
regression test (`file://`, `data:`, `ftp://`, `not-a-url`, `https://`-no-host → all rejected, exit 2).

## 2. Garbage input → raw library traceback instead of a clean error
`cf_harvest not-a-url` → an unhandled `patchright._impl._errors.Error` dumped a traceback to stderr (rc=1,
empty stdout). A CLI must wrap the risky call and emit a **graceful, structured** failure (rc=3, JSON
`{"error": "..."}`), not leak the dependency's internals. Test: garbage input yields a clean rc + parseable
error, never a traceback.

## 3. A "verification" check that conflates two distinct conditions
The cf_harvest binding proof read `httpbin`'s `cookies` field (always `null` there) instead of the `Cookie`
**request header** — so it reported "cookie not transmitted" when it *was*. Building the proof found the bug
*in the proof*. Lesson: when a check asserts a property of the wire, **probe the actual wire format first**
(`print(r.text)` of the echo) rather than assuming the field name. A green-but-wrong verifier is worse than none.

## 4. FAIL-vs-SKIP parity — a missing-prerequisite must be SKIP, a broken-tool must be FAIL
Running the smoke under a decoy `HERMES_HOME` (no venv) revealed inconsistent semantics: `curl_cffi` correctly
**SKIPped** ("venv absent") but nodriver/scrapling/seleniumbase **FAILed** — because those blocks called
`"$PY" -c "import X"` directly without a `[ -x "$PY" ]` venv-presence guard first. A harness that FAILs on
"tool not installed" cries wolf; one that SKIPs on "tool broke" hides a real regression. **Rule: guard each
tool block on prerequisite-presence → SKIP if absent; only run the import/launch check (→ FAIL on break)
when the prerequisite exists.** This is the smoke-harness analog of the field-presence-matrix probe.

## 5. The negative-control that a weak target can't satisfy → build a DETERMINISTIC, target-independent proof
cf_harvest's UA-binding negative control (mismatched UA must fail) couldn't fire because the test target
(nowsecure.nl) doesn't enforce UA-binding *or even require the cookie* — so "binding works" was unprovable
from that target. Don't ship an informational-only control and call it proven. Instead build a
**mechanism proof that doesn't depend on a third party enforcing anything**: `--prove-binding-offline` hits
an echo endpoint (httpbin) and asserts the replay session *transmits* the exact UA + cookie on the wire and
that a mismatched UA is provably different. The target-independent proof is the gateable one; the live-target
behavior is WARN. (General rule: when a live target can't discriminate your positive/negative case, move the
proof to a deterministic harness you control.)

## 6. Self-audit the spec's ACs AFTER you've declared done — declaring done is not evidence of done
Before the dogfood round, a grep of the spec's `AC-*` lines against what shipped found **4 ACs under-built**
(a gate spec'd but only run manually, an import-only check where the AC said launch-gate, a recurring check
never wired, a parity case never demonstrated) — all hidden behind a green smoke and a closeout summary.
**Mechanize the audit:** `grep -nE 'AC-[A-Z0-9-]+' spec.md` → for each, point at the concrete artifact/line
that satisfies it; any AC you can't point at is a gap. Do this as a closeout step, not on the user's prompt.

## 7. Two same-typed args where one is TRUSTED and one is UNTRUSTED → make them keyword-only (anti-inversion)
A function `build_extraction_messages(envelope, task)` took two strings positionally: `envelope` = untrusted
scraped DATA, `task` = the trusted instruction. They are trivially invertible — a future caller writing
`build_extraction_messages(task, content)` silently puts **untrusted scraped content into the instruction
slot**, the exact prompt-injection the function exists to prevent. A green unit suite won't catch it (the
test that found it had the args reversed and *still passed* structurally). The fix isn't documentation, it's
making the inversion **impossible**: change the signature to keyword-only.
```python
def build_extraction_messages(*, envelope: str, task: str, schema=None) -> list: ...
```
Now `build_extraction_messages("data", "task")` raises `TypeError` instead of silently mislabeling trust.
**Rule: when a function takes two (or more) args of the same type where at least one is untrusted/attacker-
controlled and another is a trusted instruction/config, make them keyword-only so a positional inversion is
a crash, not a silent security breach.** Lock it with a regression that asserts the positional call raises
`TypeError` and the keyword call still works; sweep every call site to kwargs in the same diff (only the
test was positional — real callers already used kwargs, so the change is clean). This is cheaper and more
durable than a doc comment warning "don't invert these," which the next session won't read.

## 8. Concurrency double-send — prove it with a REAL-PROCESS race + a lock-neuter negative control
A queue/flush/worker that does **read-pending → act → mark-done** without atomically claiming rows is a
latent double-delivery bug: two overlapping runs (a scheduled tick overrunning its interval, or a manual
run racing the timer) each read the same pending rows and act on them. The thread-based concurrency test
(in-process `ThreadPoolExecutor`) is necessary but **not sufficient** — the production failure is separate
OS PROCESSES (launchd/systemd fired the entrypoint twice). Write the e2e as **N real subprocesses racing
the actual CLI entrypoint** against one shared DB, with the side-effect sink **env-injected to a fake**
(`CRONOBS_NOTIFY_PY=<fake that appends every delivery to a log>`), then assert every row was delivered
**exactly once** across all processes (count occurrences of each row-id; any id seen >1 is a double-send).
Real catch (2026-06-12): 5 concurrent flushers each delivered all 40 rows → 5× page-storm; the in-process
test had passed.

**The negative-control that makes the e2e a real gate:** temporarily NEUTER the guard (comment out the
`flock` acquire / make it a no-op), run the e2e, confirm it now **FAILS** (N× dupes), then restore and
confirm it passes. An e2e you haven't watched fail against the unguarded code is an assertion, not a proof.
Keep the neuter as a documented one-liner in the test header so the next session can re-run it.

## 9. The concurrency guard itself: per-resource `fcntl.flock`, non-blocking, crash-safe, critical-path-exempt
The fix for §8 is a **per-resource (per-DB) advisory lock** around the whole read-act-mark critical section,
with four load-bearing properties:
- **`fcntl.flock(fd, LOCK_EX | LOCK_NB)`** (non-blocking): if another run holds it, **no-op and return a
  `{skipped:'locked'}` sentinel** rather than blocking/queueing — the next scheduled tick covers the work.
  Blocking would just serialize the storm; skipping eliminates it.
- **Crash-safe:** the OS releases `flock` automatically when the holder dies, so a killed run leaves **no
  stuck lock** (vs a lockfile-with-PID you must reap). Derive the lockfile from the resource
  (`<db>.flush.lock`) so distinct DBs don't contend but every actor on the SAME DB shares one lock.
- **Critical path exempt:** the highest-severity path (a `critical` alert / deadman) must NOT be gated by
  this lock — route it to an independent inline send so a held flush lock can never starve it. Prove it:
  hold the lock, fire a critical, assert it still delivers.
- **Refactor shape:** split `public_fn()` (acquire lock → call `_core()`) from `_core()` (the original
  body), with a `_locked=False` escape hatch for a caller that already holds it. Regression tests:
  concurrent-no-double-send, busy-returns-skipped, lock-released-after-normal-run.

**Multi-host footgun:** if the same code runs its own timer on >1 host (a Mac launchd + a Linux systemd
`--user` flush), a fix to the locked function must be **deployed + re-tested on EVERY host** — a patch on
one leaves the others exposed. `git pull` + re-run that host's suite after any change.

## 10. HTML generator that renders user-controlled strings = stored-XSS surface — escape every field, fixed-lookup the attributes
Any generator that interpolates job names / error text / labels into an HTML dashboard (here: crons.ace) is
a stored-XSS surface if it renders attacker-or-operator-controlled strings unescaped. Probe by seeding a job
whose `name`/`error`/`badge` carry `<script>alert(1)</script>`, `"><img src=x onerror=...>`, and a
`</style><script>` style-breakout, then drive the REAL model-builder (not a hand-built model) and assert the
raw payloads appear ONLY in escaped form (`&lt;script&gt;`) and never live. Two rules the probe enforces:
every user field goes through `html.escape`, and any value interpolated into an **attribute context**
(`style="background:{color}"`) must come from a **fixed server-side lookup table**, never user data — a
hostile `badge` then falls back to the safe default instead of breaking out of the attribute. JSON artifact
must also `json.dumps` cleanly.

## 11. Git-automation that loops over filenames: non-ASCII names C-quote → silent coverage drop + SECRET LEAK
The highest-severity catch of the 2026-06-12 home-autocommit dogfood, and a class that hits ANY shell/script
that parses `git status` / `git diff` filename output. **`git status --porcelain` and
`git diff --cached --name-only` C-QUOTE non-ASCII paths**: `scripts/sécret.sh` is emitted as the literal
string `"scripts/s\303\251cret.sh"` (with surrounding quotes and backslash-octal escapes). A script that
takes that quoted string and feeds it back to git **silently mismatches the real on-disk path**:
- **Coverage gap:** `git add -- "<quoted>"` matches nothing → the file is **silently never committed**, no
  error, no alert — the exact silent-failure an autocommit guard exists to prevent.
- **SECURITY (worst class):** a staged-set secret-scanner doing `git show :"<quoted>"` reads **nothing** →
  the scan finds no secret → **a secret in a non-ASCII-named file commits and pushes to origin.** Proven
  live: a `ghp_…` token in `scripts/sécret.sh` reached origin past a scanner that worked perfectly for
  ASCII names. Emoji / em-dashes / accents in agent-authored filenames make this realistic, not exotic.

**Fix — read filename output NUL-delimited (`-z`), which emits RAW UNQUOTED bytes:**
```bash
# dirty set
DIRTY=()
while IFS= read -r -d '' rec; do
  [ -z "$rec" ] && continue
  [ "$expect_old" = 1 ] && { expect_old=0; continue; }   # consume a rename's source record
  xy="${rec:0:2}"; path="${rec:3}"
  case "$xy" in R*|C*) expect_old=1;; esac                # R/C: next record is the OLD path
  DIRTY+=("$path")
done < <(git status --porcelain -uall -z -- "$dir")
# staged set
STAGED=(); while IFS= read -r -d '' p; do STAGED+=("$p"); done < <(git diff --cached --name-only -z)
```
Then convert **every** downstream consumer (denylist grep, `git show :path` secret-scan, area summary,
blob-SHA verify, `git reset -- path`) to iterate the array, never a newline-joined `$S` string. **Rename
records under `-z`:** a rename is two NUL records — the `R`/`C` record (dest path) followed by a bare record
(source path) you must CONSUME, or you double-count the old name as a new file. Lock with two regressions:
**(coverage)** a non-ASCII filename must commit, and **(critical, RED-provable)** a secret in a non-ASCII
filename must be scanned + held (rc≠0, never on origin) — the critical one LEAKS to origin against the
pre-`-z` code, which is what makes it a real gate. **Rule: any git-automation that loops over filenames
from porcelain/diff output MUST use `-z` + `read -r -d ''`; the quoted ASCII-only form is a latent
coverage-drop and secret-bypass.**

The same dogfood round also CONFIRMED-ROBUST (no fix, but worth knowing the probes pass): N real concurrent
guard processes → exactly 1 commit + `git fsck` clean (an atomic `mkdir` lock layered over git's own
`index.lock` is doubly safe; the §8 lock-neuter negative control is undramatic here precisely because git
self-protects the index); shell-metacharacter filenames (backtick/`$(...)`/`;`/`&`/`|`/spaces) commit as
literal bytes with **no command injection** (`/tmp/PWNED` never created) when every git invocation quotes
its `"$path"`; DRY_RUN purity (no HEAD/index/worktree mutation, report written OUTSIDE the repo); and a TIGHT
secret-scan exemption regex (`(^|/)tests/.*/fixtures/` — decoys `tests/fixtures-evil/` and `scripts/fixtures/`
correctly do NOT match, so the carve-out can't be abused to smuggle a secret). When you can't make a negative
control fail because a SECOND independent guard already prevents the failure, that's a robustness finding to
record, not a missing test to force.

## The meta-lesson
A 3-pass Opus spec review (APPROVE) + a green happy-path smoke proved the *design* and the *happy path* —
neither touched malformed input, prerequisite-absence, verifier-correctness, AC completeness, or
trust-boundary arg-ordering. The adversarial CLI dogfood is a SEPARATE, mandatory pass for any shipped tool,
and it pays out fast (here: 4 fixes + a 23-test regression suite + ruff/shellcheck gate, all from one round
of trying to break it). Wire the resulting e2e suite back INTO the standing smoke as a gating step so the
regressions can't return.

## Bonus discipline: ground-truth the repo before spec'ing "what's left"
When asked to "spec and build the remaining work," check the git log / on-disk state FIRST — a prior session
may have already built and pushed it (`git log --oneline`, grep the artifacts). Writing a spec for code that's
already green on disk is theater. Confirm the gap is real before producing scope.
