# macOS iCloud "dataless" placeholder → EDEADLK on file read (looks like a tool/code bug, is a storage bug)

**Symptom (the trap):** every attempt to READ a file in a directory under `~/Documents`,
`~/Desktop`, or anywhere covered by iCloud's "Desktop & Documents in iCloud" — via `read_file`,
`cat`, Python `open()`, *any* reader — fails with:

```
Resource deadlock avoided (os error 11)        # cat / shell
OSError: [Errno 11] Resource deadlock avoided   # Python open()
```

`read_file` may instead return **empty content** for a file that `ls` clearly shows as multi-KB
(it silently swallows the deadlock). The file *looks* present (`ls -la` shows the real byte size),
which makes you suspect a permission bug, a cache bug, or a flaky tool. **It is none of those.**

**Root cause:** the file is an APFS **dataless placeholder** — iCloud has evicted the file's
content to the cloud to save local disk and left only a stub on disk. The on-access "materialize
from iCloud" download is deadlocking (commonly while `bird`/`brctl` is mid-sync, or offline) instead
of transparently fetching, so the open() never completes and the kernel returns `EDEADLK`.

**The 5-second confirm** — check the file flags; a dataless file is the tell:

```bash
stat -f "%N flags=%Sf" ~/Documents/SOME/DIR/*
# A healthy local file:    flags=-
# An evicted placeholder:  flags=compressed,dataless     <-- this is the bug
```

(`dataless` is the load-bearing flag; `compressed` alone is fine.)

**The fix — force iCloud to materialize the content, then read:**

```bash
cd ~/Documents/SOME/DIR
brctl download "FILENAME"          # pull ONE file down from iCloud (per-file)
# or pull a whole dir:  find . -type f -exec brctl download {} \;

# poll until the dataless flag clears (download can be near-instant or take seconds):
for i in $(seq 6); do
  [ "$(stat -f '%Sf' FILENAME | grep -c dataless)" = 0 ] && { echo materialized; break; }
  brctl download FILENAME; sleep 3
done
stat -f "%N flags=%Sf" *           # confirm flags went compressed,dataless -> -
```

`brctl status` shows the live sync state (`downloader{… downloading:0.0% …}` lines = a fetch is
in flight). Once `flags=-`, the file reads normally with any tool.

## Pitfalls
- **`read_file`'s dedup cache poisons itself.** If `read_file` ran against the file while it was
  still dataless, it cached the empty/partial result; a re-read after materializing returns
  `"unchanged since last read"` with the OLD (empty) content. Work around it by reading via
  `execute_code`/`open()` (or `cat`) after the download, not `read_file`.
- **Don't theorize about permissions/ACLs/quarantine first.** `EDEADLK` + a non-zero `ls` size is
  the dataless signature; check the `stat` flags BEFORE chasing chmod/xattr/`com.apple.quarantine`.
- **It's per-file, not per-dir.** Materializing one file does not pull its siblings — `brctl
  download` each file you need, or sweep the dir with the `find … -exec` form above.
- **This is an environment/storage STATE, not a durable tool defect.** The reader tools work fine;
  the file's bytes were just elsewhere. Never conclude "`read_file`/`cat` is broken on this box."

## General rule
A file-read that fails with `Resource deadlock avoided` / `EDEADLK` (or reads as empty despite a
real `ls` size) on macOS is almost always an iCloud-evicted dataless placeholder, not a code or
permission bug. Confirm with `stat -f %Sf` (look for `dataless`), fix with `brctl download`, then
read. Same class as §1's "read the error message" — the errno *is* the diagnosis once you know it.
