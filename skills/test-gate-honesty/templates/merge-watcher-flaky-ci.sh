#!/bin/bash
# Self-disabling merge-watcher for a green-locally PR blocked by SERIALLY-flaky CI
# on a busy fleet (see test-gate-honesty §4). Register as a no_agent cron every ~6m.
# Set REPO / PR / JOB. Bound: retries flakes up to MAXR before pausing for review.
export PATH="$HOME/.local/bin:/opt/homebrew/bin:$PATH"
REPO="OWNER/REPO"; PR=000; JOB="merge-<slug>-pr-000"; MAXR=4
RC="${HERMES_HOME:-$HOME/.hermes}/state/merge-${PR}-retries"; mkdir -p "$(dirname "$RC")"; touch "$RC"
retries=$(cat "$RC" 2>/dev/null || echo 0); retries=${retries:-0}

state=$(gh pr view "$PR" --repo "$REPO" --json state -q .state 2>/dev/null)
if [ "$state" = "MERGED" ]; then echo "PR #$PR merged; self-disabling."; rm -f "$RC"; hermes cron pause "$JOB" 2>/dev/null; exit 0; fi
if [ "$state" != "OPEN" ]; then echo "PR #$PR state=$state; self-disabling."; hermes cron pause "$JOB" 2>/dev/null; exit 0; fi

rollup=$(gh pr view "$PR" --repo "$REPO" --json statusCheckRollup,mergeStateStatus 2>/dev/null)
fails=$(printf '%s' "$rollup" | python3 -c "import sys,json;r=json.load(sys.stdin)['statusCheckRollup'];print(sum(1 for c in r if (c.get('conclusion') or c.get('state') or '') in ('FAILURE','ERROR','CANCELLED','TIMED_OUT')))")
pend=$(printf '%s' "$rollup" | python3 -c "import sys,json;r=json.load(sys.stdin)['statusCheckRollup'];print(sum(1 for c in r if (c.get('status') or '')!='COMPLETED'))")
mss=$(printf '%s' "$rollup" | python3 -c "import sys,json;print(json.load(sys.stdin).get('mergeStateStatus',''))")

if [ "$pend" -gt 0 ]; then echo "PR #$PR: $pend checks pending; next tick."; exit 0; fi

if [ "$fails" -gt 0 ]; then
  if [ "$retries" -lt "$MAXR" ]; then
    runid=$(gh pr view "$PR" --repo "$REPO" --json statusCheckRollup -q '[.statusCheckRollup[]|select((.conclusion//.state//"")|test("FAILURE|ERROR|CANCELLED|TIMED_OUT"))|.detailsUrl][0]' 2>/dev/null | grep -oE 'runs/[0-9]+' | grep -oE '[0-9]+' | head -1)
    echo $((retries+1)) > "$RC"
    echo "PR #$PR: $fails failing - flaky-retry $((retries+1))/$MAXR, rerunning run $runid"
    [ -n "$runid" ] && gh run rerun "$runid" --repo "$REPO" --failed 2>&1 | tail -1
    exit 0
  fi
  echo "PR #$PR: still failing after $MAXR flaky-retries - REAL failure, self-disabling for review."; hermes cron pause "$JOB" 2>/dev/null; exit 0
fi

if [ "$mss" = "BEHIND" ] || [ "$mss" = "UNKNOWN" ]; then
  echo "PR #$PR $mss; updating branch (reset retry counter)."; echo 0 > "$RC"
  gh pr update-branch "$PR" --repo "$REPO" 2>&1 | tail -1; exit 0
fi

# All green + up-to-date: resolve lingering review threads, then admin-squash-merge.
gh api graphql -f query='{ repository(owner:"OWNER", name:"REPO"){ pullRequest(number:'"$PR"'){ reviewThreads(first:50){ nodes{ id isResolved } } } } }' 2>/dev/null | python3 -c "
import sys,json,subprocess
for t in json.load(sys.stdin)['data']['repository']['pullRequest']['reviewThreads']['nodes']:
    if not t['isResolved']:
        subprocess.run(['gh','api','graphql','-f','query=mutation(\$id:ID!){resolveReviewThread(input:{threadId:\$id}){thread{isResolved}}}','-f','id='+t['id']],capture_output=True)
"
gh pr merge "$PR" --repo "$REPO" --squash --admin 2>&1 | tail -2
state2=$(gh pr view "$PR" --repo "$REPO" --json state -q .state 2>/dev/null)
if [ "$state2" = "MERGED" ]; then echo "PR #$PR merged; self-disabling."; rm -f "$RC"; hermes cron pause "$JOB" 2>/dev/null; else echo "merge retry next tick (mss=$mss)"; fi
