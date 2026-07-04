# Active DisplayPort→HDMI adapter VRR/high-refresh debugging

Use when a Windows or Linux workstation can drive a monitor over native DisplayPort, but high refresh, VRR/G-SYNC/DRR, HDR, or color range behaves differently through an active DP→HDMI 2.1 adapter.

## Core mental model

Treat the adapter as an active protocol bridge with its own firmware and EDID/link behavior, not as a passive cable.

Common symptoms:

- Fixed high refresh works but VRR/G-SYNC/DRR is missing.
- Different refresh rates have different color/black level appearance.
- 4K60 looks correct but 4K120 looks washed/lifted, or vice versa.
- Native DP works at 4K240/VRR but DP→HDMI does not.
- Adapter supports high fixed refresh but product docs say VRR is unsupported or requires special firmware.

## Investigation order

1. Prove the native path first when possible:
   - GPU DP → monitor DP, single cable.
   - Test 4K60 → 4K120 → 4K240 → VRR/DRR/G-SYNC.
   - If native DP works, the GPU/driver/monitor are mostly exonerated; focus on adapter/HDMI negotiation.

2. Identify the exact adapter model and firmware path:
   - Some adapters have separate normal vs VRR firmware.
   - Firmware usually lives on the adapter and persists across OSes.
   - Firmware flash tools may be Windows-only.
   - Always find rollback firmware before flashing.

3. Test fixed refresh before VRR:
   - 4K60 SDR
   - 4K120 SDR
   - 4K240 SDR if advertised
   - Then HDR/10 bpc
   - Then VRR/G-SYNC/DRR last

4. Force color output explicitly:
   - RGB
   - Full dynamic range / 0–255
   - Known-good bpc, usually 8 bpc first, then 10 bpc

5. Power-cycle/reconnect after firmware or mode changes:
   - Unplug adapter from GPU/source side.
   - Wait ~10 seconds.
   - Power-cycle monitor.
   - Reconnect adapter.
   - Reboot OS only if mode list remains stale.

## Windows probes/settings

Read-only checks:

```powershell
Get-CimInstance Win32_VideoController |
  Select Name,DriverVersion,CurrentHorizontalResolution,CurrentVerticalResolution,CurrentRefreshRate,VideoModeDescription | Format-List

Get-CimInstance -Namespace root/wmi -ClassName WmiMonitorConnectionParams |
  Select InstanceName,VideoOutputTechnology | Format-List

Get-CimInstance -Namespace root/wmi -ClassName WmiMonitorID | ForEach-Object {
  $name = -join ($_.UserFriendlyName | ? {$_ -ne 0} | % {[char]$_})
  [pscustomobject]@{InstanceName=$_.InstanceName; Active=$_.Active; Name=$name}
}

nvidia-smi --query-gpu=name,driver_version,pstate,display_active,temperature.gpu --format=csv,noheader,nounits
```

VRR/Auto HDR user setting check:

```powershell
Get-ItemProperty 'HKCU:\Software\Microsoft\DirectX\UserGpuPreferences' |
  Select-Object DirectXUserGlobalSettings
```

If a previous safe-off step disabled Windows VRR optimization and the user is ready to test VRR again:

```powershell
New-Item -Path 'HKCU:\Software\Microsoft\DirectX\UserGpuPreferences' -Force | Out-Null
Set-ItemProperty \
  -Path 'HKCU:\Software\Microsoft\DirectX\UserGpuPreferences' \
  -Name DirectXUserGlobalSettings \
  -Type String \
  -Value 'VRROptimizeEnable=1;AutoHDREnable=0;'
```

NVIDIA Control Panel baseline for adapter testing:

- Display → Change resolution
- Prefer PC resolution bucket when available
- Resolution: target native resolution
- Refresh: fixed first, VRR/DRR later
- Output color format: RGB
- Output dynamic range: Full
- Output color depth: 8 bpc first; 10 bpc after stable

If colors differ by refresh rate, suspect RGB Full/Limited mismatch before HDR/calibration.

## Cable Matters 102101-BLK notes from the Linux GPU box case

Observed working path on RTX PRO 6000 Blackwell Max-Q + ASUS PG32UCDM:

- Adapter: Cable Matters 102101-BLK DP 1.4 → HDMI 2.1
- VRR firmware: `7.02.120_forVRR`
- Rollback firmware in same package: `7.02.126`
- Flash tool: `VmmDPTool64.exe` / `VMMDPTool64.exe`, run as administrator on Windows
- Required after flash: unplug/replug adapter and power-cycle monitor
- User-confirmed: 4K240 + DRR + G-SYNC works, both 8 bpc and 10 bpc
- Washed/lighter 4K120 color was fixed by forcing NVIDIA Output dynamic range = Full

Do not generalize this as “all 102101 adapters always support VRR”; confirm exact firmware and rollback path.

### Firmware flashing runbook pattern

When multiple identical active adapters need firmware, flash **one adapter at a time** unless the vendor tool explicitly shows unique per-device targeting (serial/port/path) and documents batch flashing.

Reasoning: the risk is usually not bandwidth or electrical impossibility; it is ambiguous enumeration. Firmware tools for VMM/Synaptics-style bridge chips may show only one status pane or identical product IDs, so with several adapters connected you can end up flashing one target, not knowing which target changed, or failing to verify per-adapter state.

Safe runbook:

1. Physically label adapters before connecting them (`CM-1`, `CM-2`, ...).
2. Connect exactly one adapter: GPU DisplayPort → adapter → HDMI cable → powered-on functioning monitor.
3. Prefer a boring pre-flash mode: 4K60/120, SDR, RGB, Full range if available.
4. Run the vendor flash tool as administrator.
5. Flash the VRR firmware, wait for the tool's success text (e.g. `Action complete`).
6. Unplug/replug the adapter from the GPU/source side.
7. Power-cycle the monitor.
8. Verify fixed refresh first (4K60 → 4K120 → 4K240), then RGB Full, then VRR/G-SYNC/DRR.
9. Mark the physical adapter with the firmware version if successful.
10. Keep the rollback firmware/tool staged and document the exact file flashed.

### Active optical/fiber HDMI caveat

Fiber/active optical HDMI can be used after a DP→HDMI active adapter, but treat it as another active device in the chain. Use HDMI 2.1 / 48Gbps / Ultra High Speed-rated cables; connect directional cables with **Source** toward the adapter/GPU and **Display** toward the monitor. Test each adapter+cable pair individually and change only one variable at a time when diagnosing blinking, black screens, missing high-refresh modes, missing G-SYNC, or color/range changes.

## NVIDIA App / driver management caution

When remotely installing NVIDIA companion tools on a workstation GPU, snapshot driver state first and verify afterward:

```powershell
nvidia-smi --query-gpu=name,driver_version,display_active,pstate,temperature.gpu --format=csv,noheader,nounits
Get-ItemProperty 'HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*','HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*' -ErrorAction SilentlyContinue |
  Where-Object { $_.DisplayName -match 'NVIDIA app|NVIDIA Control Panel|GeForce Experience|NVIDIA Graphics Driver' } |
  Select-Object DisplayName,DisplayVersion,InstallLocation,Publisher
```

Do not assume a consumer NVIDIA App installer is a harmless UI-only add-on in workstation/RTX Enterprise driver setups. It may fail without installing the app, prompt interactively, return an undocumented exit code, or change/update driver state as part of its package flow. Prefer the official workstation/enterprise app path when available, keep the known-good enterprise driver installer staged, and avoid rebooting or driver changes while the user is actively using the display unless they explicitly ask.

## Club 3D CAC-1088 notes
In the same investigation, public Club 3D forum material said CAC-1085/CAC-1087/CAC-1088 do not officially support VRR/G-SYNC/FreeSync. Another Club 3D reply suggested possible support-provided alternate firmware for CAC-1088, but no public VRR firmware was found.

Practical rule: treat CAC-1088 as fixed-refresh unless support provides firmware; prefer a known VRR-firmware-capable adapter when VRR/DRR is required.

## Linux/Ubuntu notes

Adapter firmware flashed from Windows should persist when booting Linux because it is stored on the adapter.

Linux still may need separate tuning:

```bash
xrandr --query
xrandr --props | grep -E ' connected|vrr_capable|Colorspace|Broadcast RGB|max bpc' -A8
nvidia-settings
```

Linux test order:

1. 4K60 SDR fixed refresh.
2. 4K120 fixed refresh.
3. 4K240 fixed refresh.
4. RGB range/color space.
5. VRR/G-SYNC last.

If Linux fails to expose high refresh/VRR but Windows works, do not blame hardware first; investigate EDID, X11/Wayland, NVIDIA driver settings, and adapter-specific firmware behavior.
