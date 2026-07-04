#!/usr/bin/env bash
# random-order-cluster-histogram.sh — Phase-0 sweep + post-fix residual probe for
# random-order (pytest-randomly) test pollution. See systematic-debugging §5e
# "Class-3 leak #6 / the meta-rule for making a suite spotless under -p randomly".
#
# Runs a CONTIGUOUS seed range (1..N, the anti-cherry-pick guarantee) single-process
# and prints, per seed: the pass/fail total + a per-FILE cluster histogram of which
# test files failed. The failure COUNT varies by seed but the MECHANISM set converges,
# so diff the histogram before vs after each by-construction fix to read the SHRINKING
# residual — don't chase individual leaker->victim pairs.
#
# Usage:
#   random-order-cluster-histogram.sh <test-dir> [N]
#     <test-dir>  e.g. tests/gateway/
#     N           highest seed (default 8); sweeps 1..N
#
# Env:
#   PYRUN   full python+pytest invocation prefix for venv / hermetic isolation.
#           Default: "python -m pytest". For the Hermes fleet single-process pattern:
#             PYRUN='env -i HOME="$HOME" PATH=/usr/bin:/bin bash -c "ulimit -n 65536; \
#               cd <repo>; PYTHONPATH=\$PWD <repo>/venv/bin/python -m pytest"'
#           (the env -i + ulimit avoids the FD-ceiling false-wall, §5f.)
#   PYTEST_EXTRA   extra pytest args (default: -p no:cacheprovider -o addopts="")
#
# Notes:
#   - Each seed is a FULL single-process run (~minutes); N=8 ≈ 40 min for a 7k-test suite.
#   - A file appearing under one seed but not another is normal (seed-dependent victim).
#   - A file that passes in ISOLATION but fails here = pollution (per §5e), not a product bug.
set -uo pipefail

TEST_DIR="${1:?usage: random-order-cluster-histogram.sh <test-dir> [N]}"
N="${2:-8}"
PYRUN="${PYRUN:-python -m pytest}"
PYTEST_EXTRA="${PYTEST_EXTRA:--p no:cacheprovider -o addopts=\"\"}"

for S in $(seq 1 "$N"); do
  log="$(mktemp -t rand_seed_${S}.XXXXXX.log)"
  # shellcheck disable=SC2086
  eval "$PYRUN \"$TEST_DIR\" -p randomly --randomly-seed=$S --tb=no -q $PYTEST_EXTRA" \
    > "$log" 2>&1
  total="$(grep -E '^[0-9]+ (passed|failed)' "$log" | tail -1)"
  echo "===== seed=$S :: ${total:-<no summary — run errored, see $log>} ====="
  # Per-file cluster histogram (strip the ::test_name and ' - reason' tails).
  grep '^FAILED' "$log" \
    | sed -E 's#FAILED ([^:]+)::.*#\1#' \
    | sort | uniq -c \
    || echo "  (0 failures)"
  rm -f "$log"
done
