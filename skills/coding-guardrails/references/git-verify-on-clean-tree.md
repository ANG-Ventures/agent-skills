# Verifying "is this failure mine?" without corrupting the working tree

## The footgun (seen 2026-06-24)
To prove a red test was pre-existing, the instinct is:
`git stash push <files>` → run on clean HEAD → `git stash pop`.

This is unsafe when an **old, unrelated stash already sits at `stash@{0}`**. The pop (or a
collision during the stash/unstash dance) can apply the WRONG stash, leaving conflict markers
in a file you never touched. Real incident: stashing `router_dispatch.py` + an untracked new
file to re-run a test selection produced a phantom `UU` merge conflict on an unrelated
`deploy/.../FLASH-LOG.md`, and the pre-existing "mac-local flash artifacts" stash was silently
"kept" (`The stash entry is kept in case you need it again`). Nothing was lost, but the tree
was dirtied and it cost a careful recovery.

## Safe ways to verify-on-clean, in order of preference
1. **Run the suspect test IN ISOLATION with your changes present.**
   `pytest path/to/test_x.py::test_y -q`
   - Passes alone but fails under a broad `-k` / full-suite run → the failure is
     **test-ordering pollution / shared-state leak across files**, NOT your code.
   - This is extremely common with API-drift fixtures. Example this session: pipecat's
     `TranscriptionFrame.__init__()` now requires `user_id` + `timestamp`; an old test that
     constructs it without them fails only when collected alongside the modules that trip the
     drift — 19 failures on clean HEAD under the broad selection, 1 with my changes, 0 in
     isolation. The math itself proved my code was innocent.
2. **Copy aside + checkout HEAD.**
   `cp file /tmp/mine.py && git checkout HEAD -- file && pytest … ; mv /tmp/mine.py file`
   For untracked new files, just `mv` them out and back — `git checkout` won't touch them.
3. **Throwaway worktree** (cleanest; never touches your working tree):
   `git worktree add /tmp/clean HEAD && (cd /tmp/clean && pytest …) ; git worktree remove /tmp/clean`

## Recovery if you already hit it
- `git checkout HEAD -- <conflicted-file>` (then `git reset -q HEAD <file>` if it staged) to
  drop the bad partial apply and restore the committed version.
- `git stash list` to confirm the old stash is still present — verify nothing was lost before
  moving on.
- Re-grep your own changed files for the change markers you expect (e.g.
  `grep -c "MY_NEW_SYMBOL" file`) to confirm your edits survived intact.

## Related deploy-sync check (same session, same family)
Before fast-forwarding a remote checkout that has uncommitted local edits, prove the local
edits are a **strict subset** of what you're pulling, so the discard loses nothing:
- Read the remote working file: `ssh host 'cat path/file' > /tmp/remote.py`
- Diff against your committed HEAD version: `git show HEAD:path/file > /tmp/head.py;
  diff /tmp/remote.py /tmp/head.py | grep '^<'` — lines ONLY in the remote ("<") are the loss
  risk. If the only "<" lines are exactly the ones your new commit *wraps/replaces*, it's safe.
- NB: `git show :file` reads the **index**, not the working tree — to capture uncommitted
  on-disk edits you must read the actual file, not the staged blob.
