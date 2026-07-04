#!/usr/bin/env python3
"""Summarize GNOME/Mutter Wayland monitor modes over the session D-Bus.

Run as the logged-in desktop user, or export the user's DBus session first, e.g.:
  export XDG_RUNTIME_DIR=/run/user/1000
  export DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus
  python3 ubuntu-wayland-display-summary.py

Read-only: calls org.gnome.Mutter.DisplayConfig.GetCurrentState.
"""
import os
import sys

try:
    import dbus
except Exception as exc:  # pragma: no cover - diagnostic script
    print(f"ERROR: python dbus module unavailable: {exc}", file=sys.stderr)
    sys.exit(2)

BUS_NAME = "org.gnome.Mutter.DisplayConfig"
OBJ_PATH = "/org/gnome/Mutter/DisplayConfig"

bus = dbus.SessionBus()
obj = bus.get_object(BUS_NAME, OBJ_PATH)
iface = dbus.Interface(obj, BUS_NAME)
serial, monitors, logicals, props = iface.GetCurrentState()

print(f"serial: {serial}")
print(f"layout-mode: {props.get('layout-mode')} supports-changing-layout-mode: {props.get('supports-changing-layout-mode')}")

current_by_spec = {}
print("\n=== CURRENT LOGICAL MONITORS ===")
for x, y, scale, transform, primary, monitor_specs, logical_props in logicals:
    for spec in monitor_specs:
        key = tuple(str(v) for v in spec)
        current_by_spec[key] = {
            "x": int(x),
            "y": int(y),
            "scale": float(scale),
            "primary": bool(primary),
        }
        conn, vendor, product, serial_s = key
        print(f"{conn} | {vendor} {product} | serial={serial_s} | pos={x},{y} scale={float(scale)} primary={bool(primary)}")

print("\n=== MONITOR MODES SUMMARY ===")
for spec, modes, monitor_props in monitors:
    key = tuple(str(v) for v in spec)
    conn, vendor, product, serial_s = key
    by_res = {}
    notable = []
    for mode in modes:
        mode_id, width, height, rate, preferred_scale, scales, mode_props = mode
        width = int(width)
        height = int(height)
        rate = float(rate)
        mode_id = str(mode_id)
        by_res.setdefault((width, height), []).append(rate)
        flags = []
        if bool(mode_props.get("is-current", False)):
            flags.append("CURRENT")
        if bool(mode_props.get("is-preferred", False)):
            flags.append("preferred")
        if "refresh-rate-mode" in mode_props:
            flags.append(str(mode_props["refresh-rate-mode"]))
        if flags:
            notable.append((width, height, rate, mode_id, flags))

    native = (3840, 2160)
    native_rates = sorted({round(r, 3) for r in by_res.get(native, [])}, reverse=True)
    max_rate = max((r for rates in by_res.values() for r in rates), default=0)
    max_res = max(by_res.keys(), key=lambda wh: wh[0] * wh[1]) if by_res else None

    print(f"\n{conn} | {vendor} {product} | serial={serial_s}")
    print(f"  display-name: {monitor_props.get('display-name')}")
    print(f"  min-refresh-rate: {monitor_props.get('min-refresh-rate')}")
    print(f"  color-mode: {monitor_props.get('color-mode')} supported-color-modes: {list(monitor_props.get('supported-color-modes', [])) if 'supported-color-modes' in monitor_props else None} rgb-range: {monitor_props.get('rgb-range')}")
    if key in current_by_spec:
        print(f"  placement: {current_by_spec[key]}")
    print("  current/preferred/VRR modes:")
    for width, height, rate, mode_id, flags in notable[:30]:
        print(f"    {mode_id} {width}x{height}@{rate:.3f} {' '.join(flags)}")
    print(f"  4K rates: {', '.join(map(str, native_rates[:30])) if native_rates else 'none'}")
    print(f"  max 4K rate: {max(native_rates) if native_rates else None} max any rate: {round(max_rate, 3)} max res: {max_res}")
