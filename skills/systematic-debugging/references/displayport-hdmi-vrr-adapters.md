# DisplayPort-to-HDMI active adapters: VRR / DRR debugging notes

Use when Windows 11 Dynamic Refresh Rate (DRR), VRR, G-SYNC, or FreeSync does not appear/work through an active DisplayPort-to-HDMI adapter, especially when native DisplayPort works.

## Core model

Windows 11 DRR requires the display path to expose VRR support, not just high fixed refresh rates.

A DP-to-HDMI adapter can support fixed modes such as 4K120/4K240 while still not exposing VRR/G-SYNC/FreeSync to Windows. Treat adapter firmware/bridge-chip capability as a first-class suspect before blaming the GPU.

## Cable Matters 102101-BLK

Cable Matters 102101-BLK (DisplayPort 1.4 to 8K HDMI / HDMI 2.1 adapter):

- Public product/troubleshooting pages often state VRR/G-SYNC/FreeSync are not supported for the normal firmware path.
- Cable Matters also publishes a Windows-only VRR firmware package for SKUs including `102101`:
  - KB title: `Cable Matters Firmware Update Tool [Enable VRR on Windows OS]`
  - Firmware package: `7.02.120_forVRR.zip`
  - VRR firmware: `Spyder_fw_DP_CM_7.02.120.fullrom`
  - Rollback/latest normal firmware: `Spyder_fw_DP_CM_7.02.126.fullrom`
  - Tool: `VmmDPTool64.exe`

Flash procedure:

1. Connect GPU DP -> Cable Matters adapter -> HDMI display.
2. Ensure the monitor is powered on and the display is functioning before flashing.
3. Extract `7.02.120_forVRR.zip` on Windows.
4. Run `VmmDPTool64.exe` as Administrator.
5. Select `FLASH` -> `LOAD to FLASH` -> choose `Spyder_fw_DP_CM_7.02.120.fullrom`.
6. Wait for `Action complete`.
7. Unplug/replug the adapter; power-cycle the monitor if needed.
8. Re-test Windows Advanced Display, NVIDIA Control Panel G-SYNC, and DRR.

Rollback: repeat the process with `Spyder_fw_DP_CM_7.02.126.fullrom`.

Warnings:

- Cable Matters notes the VRR firmware may cause compatibility issues such as flicker.
- Test in a ladder: 4K60 SDR fixed -> 4K120 SDR fixed -> VRR/G-SYNC -> DRR -> HDR last.
- If a prior debugging session disabled Windows VRR optimization (`DirectXUserGlobalSettings=VRROptimizeEnable=0;AutoHDREnable=0;`), re-enable/clear that only after the adapter firmware path is known.

## Club 3D CAC-1088

Club 3D CAC-1088 has conflicting real-world reports, but the practical support stance is:

- Club 3D forum representatives have said CAC-1085/CAC-1087/CAC-1088 do not officially support VRR/G-SYNC/FreeSync.
- A later forum response suggests CAC-1088 may have alternate firmware that could potentially enable VRR, but it is not publicly linked and may require contacting Club 3D support.
- Treat CAC-1088 VRR as experimental/support-only, not a reliable public firmware path.

## Diagnostic heuristic

If native DisplayPort works at high refresh + DRR/VRR but DP-to-HDMI does not:

1. Exonerate the GPU/driver only for the native path; do not assume the adapter path inherits those capabilities.
2. Verify fixed refresh first.
3. Check whether Windows/NVIDIA sees VRR/G-SYNC capability at all.
4. Research adapter-specific firmware and rollback paths.
5. Avoid stacking HDR, VRR, DRR, DSC, and high refresh in the first test; add one variable at a time.
