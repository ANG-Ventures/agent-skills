# Windows DP→HDMI active adapters: VRR/DRR and color-range debugging

Use when a Windows workstation display works over an active DisplayPort→HDMI 2.1 adapter, but VRR/DRR/G-Sync is missing, refresh modes behave inconsistently, or colors look different at different refresh rates.

## Key model

Windows Dynamic Refresh Rate (DRR) requires the display path to expose VRR support to Windows. A fixed-high-refresh mode (4K120/4K240) is not enough. DP→HDMI bridge chips can support high fixed modes while not exposing VRR/G-Sync/FreeSync, or only exposing it with alternate firmware.

Color can also vary by refresh because the adapter/GPU/monitor may renegotiate:

- RGB Full vs RGB Limited (`0–255` vs `16–235`)
- RGB vs YCbCr 4:4:4 / 4:2:2 / 4:2:0
- different CTA/HDMI timing buckets
- DSC/FRL bridge behavior

If 4K120 looks washed out while 4K60/4K240 look different, first suspect output dynamic range/chroma before blaming the GPU.

## Read-only probes first

Use the normal Windows display/GPU probes in `references/windows-display-gpu-black-screen.md`, plus check current user DirectX VRR settings:

```powershell
reg query HKCU\Software\Microsoft\DirectX\UserGpuPreferences /v DirectXUserGlobalSettings
```

If a previous debugging session set `VRROptimizeEnable=0`, re-enable only after the physical adapter firmware/path supports VRR:

```powershell
reg add HKCU\Software\Microsoft\DirectX\UserGpuPreferences /v DirectXUserGlobalSettings /t REG_SZ /d "VRROptimizeEnable=1;AutoHDREnable=0;" /f
```

## Cable Matters 102101-BLK notes

Cable Matters publishes firmware for the 102101/102103/101101/101109 adapter family.

Relevant packages:

- VRR firmware article: `https://kb.cablematters.com/index.php?View=entry&EntryID=185`
- VRR package: `7.02.120_forVRR.zip`
- Tool: `VmmDPTool64.exe`
- VRR firmware image: `Spyder_fw_DP_CM_7.02.120.fullrom`
- rollback/latest normal firmware image in the same package: `Spyder_fw_DP_CM_7.02.126.fullrom`
- general firmware package article: `https://kb.cablematters.com/index.php?View=entry&EntryID=147`

Firmware flashing requirements:

1. Adapter connected to the Windows host.
2. Adapter connected to powered-on monitor.
3. Display working before flashing.
4. Run `VmmDPTool64.exe` as Administrator.
5. Select `FLASH` → `LOAD to FLASH` → choose `.fullrom`.
6. Wait for `Action complete`.
7. Unplug/replug the adapter from GPU side; power-cycle the monitor if redetect is not clean.

VRR firmware may introduce flicker/instability; rollback to `7.02.126` if needed.

## Club 3D CAC-1088 notes

Club 3D forum guidance has been inconsistent, but the practical stance is:

- CAC-1085/CAC-1087/CAC-1088 are not officially marketed as VRR/G-Sync/FreeSync capable.
- A Club 3D forum representative stated their earlier G-Sync claim was a mistaken test and that DP1.4→HDMI 4K120 adapters do not officially support VRR.
- Another Club 3D response suggested support may provide alternate firmware that *could potentially* enable VRR on CAC-1088, but it is not public and may be unstable.

Treat CAC-1088 VRR as support-only/experimental, not a documented feature.

## Color mismatch fix ladder

When colors differ by refresh rate over DP→HDMI:

1. NVIDIA Control Panel → Display → Change resolution.
2. Choose the display and prefer `PC` resolution modes if available.
3. Force:
   - Output color format: `RGB`
   - Output dynamic range: `Full`
   - Start with 8 bpc SDR for baseline
4. If available, set monitor HDMI black level/range to Full/Normal/0–255 rather than Auto.
5. If monitor has no HDMI black-level setting, NVIDIA `Full` is the main lever.
6. Change one variable at a time: fixed refresh first, HDR later, VRR/DRR last.

Evidence that RGB range was the issue: setting NVIDIA Output dynamic range to `Full` immediately fixes washed/lighter colors at a given refresh.

## Test ladder after firmware/path changes

1. 4K60 SDR RGB Full fixed.
2. 4K120 SDR RGB Full fixed.
3. Check NVIDIA G-Sync page / Windows Advanced Display DRR availability.
4. Try VRR/DRR.
5. Add HDR only after fixed SDR and VRR behavior are characterized.
6. If black screens/flicker recur, capture event logs for `nvlddmkm`, `Display`, `DxgKrnl`, `Kernel-PnP` before changing more settings.
