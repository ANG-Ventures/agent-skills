# Windows display link debugging over SSH/RDP

Use when a Windows workstation stays reachable over SSH/RDP but a local monitor black-screens during a refresh-rate, HDR, VRR, DSC, or cable/input change.

## Read-only instrumentation pattern

Do not change display settings until evidence is captured. First collect:

```powershell
$ErrorActionPreference = 'Continue'
Write-Host "== Probe =="
Get-Date -Format o
hostname

Write-Host "== Video controllers =="
Get-CimInstance Win32_VideoController |
  Select-Object Name,AdapterCompatibility,PNPDeviceID,DriverVersion,Status,
    CurrentHorizontalResolution,CurrentVerticalResolution,CurrentRefreshRate,
    VideoModeDescription |
  Format-List

Write-Host "== Display devices =="
Get-PnpDevice -Class Display | Select-Object Status,FriendlyName,InstanceId | Format-List

Write-Host "== Monitor devices =="
Get-PnpDevice -Class Monitor | Select-Object Status,FriendlyName,InstanceId | Format-List

Write-Host "== Physical monitor connection params =="
Get-CimInstance -Namespace root/wmi -ClassName WmiMonitorConnectionParams |
  Select-Object InstanceName,VideoOutputTechnology |
  Format-List

Write-Host "== Monitor ID =="
Get-CimInstance -Namespace root/wmi -ClassName WmiMonitorID | ForEach-Object {
  $man = -join ($_.ManufacturerName | Where-Object {$_ -ne 0} | ForEach-Object {[char]$_})
  $name = -join ($_.UserFriendlyName | Where-Object {$_ -ne 0} | ForEach-Object {[char]$_})
  $serial = -join ($_.SerialNumberID | Where-Object {$_ -ne 0} | ForEach-Object {[char]$_})
  [pscustomobject]@{InstanceName=$_.InstanceName; Active=$_.Active; Manufacturer=$man; Name=$name; Serial=$serial; Week=$_.WeekOfManufacture; Year=$_.YearOfManufacture}
} | Format-List

Write-Host "== NVIDIA state, if available =="
nvidia-smi --query-gpu=name,driver_version,pstate,display_active,display_mode,clocks.current.graphics,clocks.current.memory,temperature.gpu,power.draw --format=csv,noheader,nounits
nvidia-smi -q | findstr /i "Display Attached Display Active Driver Version Product Name VBIOS"

Write-Host "== Recent display-related system events =="
$since=(Get-Date).AddMinutes(-45)
Get-WinEvent -FilterHashtable @{LogName='System'; StartTime=$since} -ErrorAction SilentlyContinue |
  Where-Object { $_.ProviderName -match 'Display|nvlddmkm|Kernel-PnP|UserPnp|DxgKrnl|amdwddmg|Kernel-Power|Power-Troubleshooter' -or $_.Message -match 'display|monitor|NVIDIA|nvlddmkm|AMD|reset|driver|DisplayPort|HDMI' } |
  Sort-Object TimeCreated -Descending |
  Select-Object -First 80 TimeCreated,ProviderName,Id,LevelDisplayName,Message |
  Format-List
```

Run remotely without quoting pain by piping the script to PowerShell over SSH:

```bash
python3 - <<'PY'
import subprocess
ps = r'''<PASTE POWERSHELL HERE>'''
cmd = ['ssh','-o','BatchMode=yes','-o','ConnectTimeout=5','-o','StrictHostKeyChecking=no','<user>@HOST','powershell','-NoProfile','-ExecutionPolicy','Bypass','-Command','-']
print(subprocess.run(cmd, input=ps, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=120).stdout)
PY
```

If command-line length is a problem, either pipe via stdin as above or copy a `.ps1` file and run it. Avoid complex one-line nested quoting; it fails noisily and wastes time.

## Interpretation cues

- `VideoOutputTechnology = 10` means external DisplayPort.
- `nvidia-smi: Display Attached: Yes` + `Display Active: Disabled` means the GPU sees a physical display but no active scanout/display pipeline. This matches a failed mode switch or link training failure better than a totally unplugged monitor.
- Bursts of `nvlddmkm` Event ID `14` around a refresh-rate/mode change are strong evidence of NVIDIA driver/display-engine failure or retry during mode negotiation. Capture the event properties, not just the blank message:

```powershell
$evs = Get-WinEvent -LogName System -MaxEvents 100 | Where-Object {$_.ProviderName -eq 'nvlddmkm'} | Select-Object -First 10
foreach ($e in $evs) {
  '---'; 'Time=' + $e.TimeCreated.ToString('o'); 'RecordId=' + $e.RecordId; 'Id=' + $e.Id
  $i=0; $e.Properties | ForEach-Object { "[$i]=$($_.Value)"; $i++ }
}
```

## Isolation order

When high refresh black-screens, test one variable at a time:

1. Single cable/path only; unplug alternate motherboard/GPU inputs to the same physical monitor.
2. Start at known-good 4K60, SDR, VRR/G-Sync off, dynamic refresh off, 3D display mode off.
3. Try intermediate refresh modes before 120Hz/144Hz/240Hz, e.g. 100Hz or 119.88Hz if exposed.
4. Add HDR only after refresh is stable.
5. Add VRR/G-Sync/dynamic refresh last.
6. Check monitor OSD firmware and DP-related settings: DisplayPort version, DSC, compatibility mode, VRR/adaptive sync, input overclock/high-refresh mode.

## Pitfalls

- Windows "3D display mode" is stereoscopic 3D, not better 3D graphics. It can force unsupported timing modes and black-screen modern non-3D workflows; keep it off during display debugging.
- Duplicate monitor histories and RDP/simulated display paths are common in Windows registry/PNP state. Treat them as clues, not root cause, until correlated with current active WMI monitor connection and event timing.
- DP-to-HDMI adapters that are stable at 4K60 but blink at 4K120 are usually near bandwidth/link-margin limits. Do not diagnose this as an app problem until cable/adapter/HDR/VRR variables are isolated.
