# Ubuntu GNOME Wayland high-refresh / HDMI audio probes

Use this when an Ubuntu GNOME Wayland workstation has multiple high-refresh displays, active DP→HDMI adapters, HDMI/eARC audio routing, or “one monitor does 4K240 but identical monitors cap at 4K100/120”.

## Principles

- **Read-only first.** Query GNOME/Mutter, DRM, EDID, PipeWire, ALSA, and NVIDIA state before changing modes.
- **Wayland is not Windows NVIDIA Control Panel.** `nvidia-settings` exists on Linux, but under GNOME Wayland it may only see the GPU and not expose full per-output controls. X11 exposes more of the classic NVIDIA UI.
- **Mode pruning is often link validation.** Identical monitor EDIDs with different exposed max modes usually means cable/adapter/DSC/link-training/topology differences, not “the monitor is worse”.
- **4K240 requires DSC or equivalent compression.** If one path exposes 4K240 and another identical display caps at 4K100/120, suspect DSC/adapter/link validation first.

Approximate uncompressed active-pixel payloads, before blanking/encoding overhead:

- 4K100 RGB 8 bpc: ~19.9 Gbps active, ~21 Gbps reduced-blanking-ish
- 4K120 RGB 8 bpc: ~23.9 Gbps active, ~25 Gbps reduced-blanking-ish
- 4K240 RGB 8 bpc: ~47.8 Gbps active, ~50 Gbps reduced-blanking-ish
- 4K240 RGB 10 bpc: ~59.7 Gbps active, ~63 Gbps reduced-blanking-ish

DP 1.4 HBR3 usable payload is ~25.9 Gbps. HDMI 2.1 48G FRL usable payload is ~42.7 Gbps. 4K240 on PG32UCDM-class displays is a DSC scenario.

## Display probe sequence

Run as the logged-in desktop user or export the desktop session bus:

```bash
export XDG_RUNTIME_DIR=/run/user/1000
export DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus
```

Summarize GNOME/Mutter current modes:

```bash
python3 scripts/ubuntu-wayland-display-summary.py
```

Direct one-liners for a remote box:

```bash
loginctl show-user ace -p Display -p State -p Sessions -p RuntimePath
loginctl show-session "$(loginctl show-user ace -p Display --value)" -p Type -p Desktop -p Name -p Active -p Remote
nvidia-smi --query-gpu=index,name,pci.bus_id,driver_version,display_active,pstate,temperature.gpu --format=csv,noheader,nounits
```

Kernel DRM connector state:

```bash
for d in /sys/class/drm/card*-*/status; do
  conn=${d%/status}; echo "--- ${conn##*/} ---"; cat "$conn/status"
  for f in enabled modes dpms link_status max_bpc bpc colorspace vrr_capable; do
    [ -e "$conn/$f" ] && { echo "$f:"; cat "$conn/$f"; }
  done
  [ -r "$conn/edid" ] && sha256sum "$conn/edid"
done
```

If `edid-decode` is installed:

```bash
for conn in /sys/class/drm/card*-*; do
  [ -s "$conn/edid" ] || continue
  echo "--- ${conn##*/} ---"
  edid-decode "$conn/edid" | grep -E 'Display Product Name|Detailed Timing|FRL|DSC|VRR|3840|2160|240|120|100|60'
done
```

Under GNOME Wayland, `xrandr` often cannot inspect the real session remotely. Prefer Mutter D-Bus and DRM sysfs. If you intentionally log into an Xorg session, then `xrandr --props` and `nvidia-settings` become more useful.

## Interpretation checklist

1. **Map connectors to physical paths.** Build a table: connector, monitor serial, cable, adapter model/firmware, AVR/TV/eARC involvement, current mode, max exposed mode.
2. **Compare EDIDs.** If identical displays have EDIDs differing only by serial/checksum but max exposed modes differ, the limit is probably link validation/topology, not monitor capability.
3. **Look for lower-resolution 240 Hz.** If 2560×1440@240 or 1080p@240 exists but 3840×2160 caps at 100/120, the issue is specifically high-bandwidth 4K/DSC, not a generic refresh-rate cap.
4. **Test one capped display alone.** If it reaches 4K240 alone, suspect multi-display DSC/GNOME/NVIDIA validation. If it remains capped alone, suspect that cable/adapter/port/firmware chain.
5. **Check color/HDR only after link basics.** GNOME `color-mode`, `supported-color-modes`, and `rgb-range` are useful but not a complete substitute for Windows NVIDIA Control Panel’s output format/depth/range controls.

## Linux NVIDIA control UI reality

- `nvidia-settings` exists and is worth opening locally.
- Under GNOME Wayland, it may expose GPU-level information but fail X-style target queries such as `CurrentMetaMode` or per-display color-range settings.
- Under “Ubuntu on Xorg,” `nvidia-settings` can expose more classic controls: X Server Display Configuration, G-SYNC availability, color correction, and sometimes mode validation behavior.
- Treat switching to Xorg as a diagnostic session first, not a permanent change, unless it clearly improves the workflow.

## HDMI/eARC audio probe pattern

For “silent but display is visible” issues, inspect PipeWire + ALSA before changing sinks:

```bash
export XDG_RUNTIME_DIR=/run/user/1000
export DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus
wpctl status
cat /proc/asound/cards
cat /proc/asound/pcm
aplay -l
for f in /proc/asound/card*/eld*; do echo "--- $f ---"; cat "$f"; done
for f in /proc/asound/card*/pcm*p/sub0/status; do echo "--- $f ---"; cat "$f"; done
```

Useful signs:

- `wpctl status` shows the default sink and active app streams.
- `/proc/asound/cardN/eld*` shows the monitor/TV/AVR name and supported channel/codecs.
- `/proc/asound/cardN/pcmXp/sub0/status` says `RUNNING` when PipeWire is actively feeding that HDMI/DP endpoint.

If the app stream is routed to the expected HDMI/DP sink and ALSA PCM is `RUNNING`, Linux is emitting audio to the endpoint. Silence then usually means downstream TV/AVR/eARC/format handling, stale HDMI handshake, or a multichannel LPCM profile the chain does not play. A conservative next test is stereo on the same output, but only after capturing the read-only state.
