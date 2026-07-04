#!/usr/bin/env python3
"""
next_lease_cap - AIMD adaptive concurrency-cap controller for subagent fan-out.

Ported (stdlib-only, Python 3.7+) from gbrain/src/core/minions/lease-cap-
controller.ts:97 (nextLeaseCap), MIT, Garry Tan. PURE function, zero I/O.

STATUS: TESTED-BUT-UNWIRED. Our single-orchestrator fan-out does not yet
produce a ControllerWindowStats (no extractor for upstream-429 count, lease
bounces, utilization, or latency stability). This ships as the POLICY +
a verified pure function; the signal source is P5 (fleet-doctor) or a future
fan-out telemetry hook. The doctrine (ramp DOWN only on upstream pushback) is
usable by a human/agent reasoning about fan-out TODAY even without the loop.

CRITICAL lesson (preserved from the source): shrink the cap ONLY on UPSTREAM
pushback (429s / latency-unstable), NEVER on internal queue bounces. Internal
bounces mean workers want MORE slots (ramp UP), not back off. Conflating them
craters the cap during healthy bursts.
"""
from dataclasses import dataclass


@dataclass
class WindowStats:
    """Rolling-window stats the controller reads each tick."""
    bounce_count: int            # lease-full bounces in window_ms
    upstream_429_count: int      # upstream 429s in window_ms (sum)
    lease_utilization: float     # mean(active / cap) over window; NaN-safe -> 0
    latency_stable: bool         # True when p95/p50 < 2 over window
    window_ms: float


@dataclass
class ControllerOpts:
    ramp_up_step: int = 1                          # additive increase
    ramp_down_step: int = 3                        # additive decrease (> up = AIMD)
    min_floor: int = 2
    max_ceiling: int = 16                          # concrete int; caller owns 200k-ctx budget
    upstream_429_threshold_per_min: float = 0.5
    bounce_rate_starving_threshold: float = 2.0
    utilization_ramp_threshold: float = 0.5


# UNTUNED first-real-use defaults. initial_cap belongs to the CALLER (the seed),
# not the controller; kept here for reference. Calibrate all of these on first
# real use - do NOT assert these exact numbers in tests.
INITIAL_CAP = 8        # UNTUNED
DEFAULTS = ControllerOpts()  # UNTUNED (ramp 1/3, floor 2, ceiling 16)


def next_lease_cap(current, window, opts=DEFAULTS):
    """Given the current cap + window stats, return the next cap. Pure, no I/O.

    Decision tree (priority order - faithful to the source):
      1. RAMP DOWN  - upstream pushback (429s OR latency unstable). ONLY shrink.
      2. RAMP UP fast - workers starving (bounces high, no 429s, latency stable).
      3. RAMP UP slow - headroom (no bounces, no 429s, util high, latency stable).
      4. DEADBAND - mixed signals: do not move.
    """
    window_min = max(1e-6, window.window_ms / 60000.0)
    bounce_rate = window.bounce_count / window_min
    upstream_429_rate = window.upstream_429_count / window_min

    # 1. RAMP DOWN - the only signals that say "cap is too high".
    if upstream_429_rate > opts.upstream_429_threshold_per_min or not window.latency_stable:
        return max(current - opts.ramp_down_step, opts.min_floor)

    # 2. RAMP UP fast - workers starving, no upstream pushback.
    if (bounce_rate > opts.bounce_rate_starving_threshold
            and upstream_429_rate == 0
            and window.latency_stable):
        return min(current + opts.ramp_up_step, opts.max_ceiling)

    # 3. RAMP UP slow - no pressure but utilization shows we are using the cap.
    if (bounce_rate == 0
            and upstream_429_rate == 0
            and window.lease_utilization > opts.utilization_ramp_threshold
            and window.latency_stable):
        return min(current + opts.ramp_up_step, opts.max_ceiling)

    # 4. DEADBAND.
    return current
