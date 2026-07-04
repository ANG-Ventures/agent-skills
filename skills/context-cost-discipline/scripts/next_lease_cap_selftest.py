#!/usr/bin/env python3
"""Selftest for next_lease_cap.py. Exit 0 = pass. Tests all 4 branches + clamps
with EXPLICIT opts - never asserts the UNTUNED defaults as "correct".
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from next_lease_cap import next_lease_cap, WindowStats, ControllerOpts

fails = []
def check(name, got, want):
    if got != want:
        fails.append("%s: got %r want %r" % (name, got, want))

# Explicit opts so the test does not depend on (untuned) module defaults.
O = ControllerOpts(ramp_up_step=1, ramp_down_step=3, min_floor=2, max_ceiling=16,
                   upstream_429_threshold_per_min=0.5, bounce_rate_starving_threshold=2.0,
                   utilization_ramp_threshold=0.5)
W = lambda b, u, util, stable: WindowStats(bounce_count=b, upstream_429_count=u,
                                           lease_utilization=util, latency_stable=stable,
                                           window_ms=60000.0)  # 1-minute window

# 1. RAMP DOWN on upstream 429s (1 429 in 1 min = 1.0/min > 0.5 threshold)
check("down-429", next_lease_cap(10, W(0, 1, 0.4, True), O), 7)  # 10 - 3
# 1b. RAMP DOWN on latency-unstable even with zero 429s
check("down-latency", next_lease_cap(10, W(0, 0, 0.9, False), O), 7)
# 1c. RAMP DOWN takes priority over starving bounces (the source lesson)
check("down-priority", next_lease_cap(10, W(100, 1, 0.9, True), O), 7)
# 2. RAMP UP fast - starving (bounce 3/min > 2.0), no 429s, stable
check("up-fast", next_lease_cap(8, W(3, 0, 0.9, True), O), 9)  # 8 + 1
# 3. RAMP UP slow - no bounces, no 429s, util 0.7 > 0.5, stable
check("up-slow", next_lease_cap(8, W(0, 0, 0.7, True), O), 9)
# 4. DEADBAND - mixed: some bounces below starving threshold, util below ramp
check("deadband-low-util", next_lease_cap(8, W(1, 0, 0.3, True), O), 8)
# 4b. DEADBAND - util high but bounces nonzero (not 0) -> neither up-slow nor up-fast
check("deadband-mixed", next_lease_cap(8, W(1, 0, 0.9, True), O), 8)
# Clamp: ramp-down cannot go below min_floor
check("clamp-floor", next_lease_cap(3, W(0, 5, 0.1, True), O), 2)  # 3-3=0 -> floor 2
check("clamp-floor2", next_lease_cap(2, W(0, 5, 0.1, True), O), 2)  # already at floor
# Clamp: ramp-up cannot exceed max_ceiling
check("clamp-ceiling", next_lease_cap(16, W(0, 0, 0.9, True), O), 16)  # 16+1 -> ceil 16
check("clamp-ceiling-fast", next_lease_cap(16, W(5, 0, 0.9, True), O), 16)

if fails:
    print("NEXT_LEASE_CAP SELFTEST FAILED (%d):" % len(fails))
    for f in fails: print("  -", f)
    sys.exit(1)
print("next_lease_cap selftest: OK (11 assertions, all 4 branches + clamps)")
sys.exit(0)
