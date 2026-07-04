# Windows display/GPU black-screen debugging over SSH/RDP

Use when a Windows workstation is reachable remotely but the local monitor black-screens after changing refresh rate, HDR, VRR, adapter/cable path, or display input.

## Principles

- Treat this as a **display pipeline negotiation** problem until evidence says otherwise: GPU driver, display topology, EDID, link training, DSC/HDR/VRR/DRR, monitor OSD, cable/adapter.
- Do **read-only instrumentation first**. Do not immediately change resolution/refresh rate from SSH unless the user explicitly authorizes recovery changes.
- Keep tests single-variable: one cable path, one refresh/HDR/VRR/DSC change at a time.
- Avoid multiple physical display paths to the same monitor during diagnosis; Windows may keep duplicate/stale topologies for the same EDID.

## Read-only probes

From the controlling machine:

```bash
nc -vz -G 3 HOST 22
nc -vz -G 3 HOST 3389
ssh -o BatchMode=yes -o ConnectTimeout=5 -o StrictHostKeyChecking=no USER@TARGET-BOX 'powershell -NoProfile -Command "$PSVersionTable.PSVersion.ToString(); Get-Date; hostname"'
```

On the Windows host, collect:

```powershell
Get-CimInstance Win32_VideoController |
  Select Name,PNPDeviceID,DriverVersion,Status,
    CurrentHorizontalResolution,CurrentVerticalResolution,CurrentRefreshRate,
    VideoModeDescription | Format-List

Get-PnpDevice -Class Display | Select Status,FriendlyName,InstanceId | Format-List
Get-PnpDevice -Class Monitor | Select Status,FriendlyName,InstanceId | Format-List

Get-CimInstance -Namespace root/wmi -ClassName WmiMonitorConnectionParams |
  Select InstanceName,VideoOutputTechnology | Format-List

Get-CimInstance -Namespace root/wmi -ClassName WmiMonitorID | ForEach-Object {
  $man = -join ($_.ManufacturerName | ? {$_ -ne 0} | % {[char]$_})
  $name = -join ($_.UserFriendlyName | ? {$_ -ne 0} | % {[char]$_})
  $serial = -join ($_.SerialNumberID | ? {$_ -ne 0} | % {[char]$_})
  [pscustomobject]@{InstanceName=$_.InstanceName; Active=$_.Active; Manufacturer=$man; Name=$name; Serial=$serial}
} | Format-List

nvidia-smi --query-gpu=name,driver_version,pstate,display_active,display_mode,clocks.current.graphics,clocks.current.memory,temperature.gpu --format=csv,noheader,nounits
```

Useful `VideoOutputTechnology` values include `10` for external DisplayPort. `nvidia-smi` can distinguish **attached** from **active** in `nvidia-smi -q`; a black screen with `Display Attached: Yes` and `Display Active: Disabled` points to a display-pipeline/link-mode failure rather than the GPU being absent.

## Event log probes

Check the hot window after the mode switch:

```powershell
$since=(Get-Date).AddMinutes(-45)
Get-WinEvent -FilterHashtable @{LogName='System'; StartTime=$since} -ErrorAction SilentlyContinue |
  Where-Object {
    $_.ProviderName -match 'Display|nvlddmkm|Kernel-PnP|UserPnp|DxgKrnl|amdwddmg|Kernel-Power|Power-Troubleshooter' -or
    $_.Message -match 'display|monitor|NVIDIA|nvlddmkm|AMD|reset|driver|DisplayPort|HDMI'
  } |
  Sort-Object TimeCreated -Descending |
  Select-Object -First 80 TimeCreated,ProviderName,Id,LevelDisplayName,Message |
  Format-List
```

For NVIDIA failures, extract event properties, not just the blank message:

```powershell
$evs = Get-WinEvent -LogName System -MaxEvents 120 | ? {$_.ProviderName -eq 'nvlddmkm'} | Select -First 10
foreach ($e in $evs) {
  '---'; 'Time=' + $e.TimeCreated.ToString('o'); 'RecordId=' + $e.RecordId; 'Id=' + $e.Id
  $i=0; $e.Properties | % { '['+$i+']=' + $_.Value; $i++ }
}
```

A burst of `nvlddmkm` Event ID 14 during a refresh-rate change is strong evidence that NVIDIA driver/display negotiation is failing/retrying. It is not proof of bad hardware by itself.

## Safe-off toggles for testing

With user authorization, make Windows graphics features boring before testing refresh-rate boundaries:

- VRR optimization off
- Auto HDR off
- Use HDR off if accessible
- Dynamic Refresh Rate off by choosing a static refresh in the UI
- 3D display mode off
- G-Sync/Adaptive Sync off while isolating

Registry-backed global toggles for the current user:

```powershell
$dxPath = 'HKCU:\Software\Microsoft\DirectX\UserGpuPreferences'
New-Item -Path $dxPath -Force | Out-Null
Set-ItemProperty -Path $dxPath -Name DirectXUserGlobalSettings -Type String -Value 'VRROptimizeEnable=0;AutoHDREnable=0;'
```

Before mutating display-related state, export relevant keys:

```powershell
$dir = 'C:\ProgramData\the user\display-debug\' + (Get-Date -Format 'yyyyMMdd-HHmmss')
New-Item -ItemType Directory -Force -Path $dir | Out-Null
reg export HKCU\Software\Microsoft\GameBar "$dir\HKCU-GameBar.reg" /y
reg export HKLM\SYSTEM\CurrentControlSet\Control\GraphicsDrivers "$dir\HKLM-GraphicsDrivers.reg" /y
reg export HKCU\Software\Microsoft\DirectX "$dir\HKCU-DirectX.reg" /y
```

`HKCU\Software\Microsoft\DirectX` may not exist yet on fresh installs; that is normal.

## Recovery/continuity

If the host sleeps while debugging, Wake-on-LAN may be enough if the MAC is known from ARP/UniFi:

```python
import socket
mac='aa:bb:cc:dd:ee:ff'.replace(':','')
pkt=bytes.fromhex('ff'*6 + mac*16)
for addr in ['255.255.255.255','<lan-ip>']:
    s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET,socket.SO_BROADCAST,1)
    s.sendto(pkt,(addr,9))
    s.close()
```

## Test ladder

After instrumentation and safe-off toggles, ask the human at the monitor to test:

1. Single physical display cable only.
2. Monitor power cycle.
3. 4K60 static, HDR off, VRR/G-Sync off.
4. Intermediate refresh such as 4K100 if exposed.
5. 4K120 static SDR.
6. Then add HDR, then VRR/G-Sync, one at a time.

If 4K100 works but 4K120 fails, suspect high-bandwidth DP link training/DSC/driver/monitor firmware/cable. If all >60Hz modes fail, suspect broader high-refresh negotiation or monitor-side DP configuration.

## Pitfalls

- Windows may report multiple stale monitor instances for the same physical panel. Do not over-interpret `Get-PnpDevice -Class Monitor` duplicates; correlate active WMI monitor params and current video controller state.
- `QueryDisplayConfig`/Advanced Color calls may return access denied/unavailable from an SSH session context. Report that limitation and use the UI for `Use HDR` if needed.
- Shell quoting PowerShell through SSH is fragile; for complex probes prefer copying a `.ps1` file or feeding PowerShell via stdin/encoded command.
- `3D display mode` is stereoscopic 3D, not performance 3D graphics. It can black-screen incompatible display paths; keep it off unless explicitly testing stereoscopic displays.
