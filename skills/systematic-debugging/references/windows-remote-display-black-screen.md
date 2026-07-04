# Windows Remote Display Black-Screen / High-Refresh Instability Triage

Use when a Windows workstation is reachable over SSH/RDP but the physical monitor is black-screening, blinking, or mode-switching badly after GPU/cable/adapter changes.

## Core lesson

Separate **machine health** from **display-path health**. A black monitor does not mean the host or GPU driver is dead. First prove SSH/RDP, driver status, display topology, and event logs before touching drivers or rebooting repeatedly.

## Minimum remote probe

From the controlling machine:

```bash
nc -vz -G 3 <ip> 22
nc -vz -G 3 <ip> 3389
ssh -o BatchMode=yes -o ConnectTimeout=5 <user>@<ip> 'powershell -NoProfile -Command "$PSVersionTable.PSVersion.ToString(); Get-Date; hostname"'
```

On Windows via SSH/PowerShell:

```powershell
Get-CimInstance Win32_VideoController |
  Select-Object Name,PNPDeviceID,DriverVersion,Status,
    CurrentHorizontalResolution,CurrentVerticalResolution,
    CurrentRefreshRate,VideoModeDescription |
  Format-List

Get-CimInstance Win32_DesktopMonitor |
  Select-Object Name,PNPDeviceID,MonitorType,Status,ScreenWidth,ScreenHeight |
  Format-List

Get-PnpDevice -Class Monitor |
  Select-Object Status,FriendlyName,InstanceId |
  Format-List

Get-PnpDevice -Class Display |
  Select-Object Status,FriendlyName,InstanceId |
  Format-List

nvidia-smi --query-gpu=name,driver_version,pstate,display_active,display_mode,clocks.current.graphics,clocks.current.memory,temperature.gpu --format=csv,noheader,nounits

$since=(Get-Date).AddHours(-2)
Get-WinEvent -FilterHashtable @{LogName='System'; StartTime=$since} -ErrorAction SilentlyContinue |
  Where-Object { $_.ProviderName -match 'Display|nvlddmkm|Kernel-PnP|DxgKrnl|amdwddmg' -or $_.Message -match 'display|nvlddmkm|NVIDIA|AMD|monitor|reset' } |
  Select-Object TimeCreated,ProviderName,Id,LevelDisplayName,Message -First 50 |
  Format-List
```

## WMI connection clues

Windows can expose active monitor paths through WMI:

```powershell
Get-CimInstance -Namespace root/wmi -ClassName WmiMonitorConnectionParams |
  Select-Object InstanceName,VideoOutputTechnology | Format-List

Get-CimInstance -Namespace root/wmi -ClassName WmiMonitorBasicDisplayParams |
  Select-Object InstanceName,MaxHorizontalImageSize,MaxVerticalImageSize,VideoInputType,Active | Format-List
```

If one physical monitor appears as multiple active `DISPLAY\...` instances, suspect topology confusion before blaming the GPU.

## Common root causes / interpretations

- **Host reachable + GPU status OK + no driver-reset logs:** likely display topology, link training, EDID/mode negotiation, cable/adapter, or monitor input state — not a dead machine.
- **Same physical monitor visible through both iGPU and dGPU:** Windows may extend/assign desktops to the wrong path/input. Test with only one display cable connected.
- **DP-to-HDMI active adapter works at 4K60 but blinks at 4K120:** classic link-margin / HDMI 2.1 handshake instability. Reduce variables: SDR, HDR off, VRR/G-Sync off, then increase bandwidth one feature at a time.
- **Direct DisplayPort black screens after another path worked:** power-cycle monitor, unplug all other display cables, test a single path at 4K60 first; stale topology and DP link training can masquerade as GPU failure.

## 3D display mode pitfall

Windows **3D display mode** is stereoscopic 3D output for old 3D TV/glasses workflows. It is not a general graphics-performance option. It can change timing/output modes and black-screen unsupported display paths. Leave it off unless deliberately testing stereoscopic 3D hardware.

## Clean test sequence

1. Keep SSH/RDP available.
2. Turn off Windows 3D display mode.
3. Unplug every display cable except the path under test.
4. Power-cycle the monitor for 20–30 seconds.
5. Start at 4K60 SDR with HDR/VRR/G-Sync off.
6. Increase one variable at a time: 4K120 → HDR → VRR/G-Sync → higher refresh.
7. Treat black screens as data: immediately re-probe video controllers, PnP monitors, GPU state, and event logs.
