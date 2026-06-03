# Changelog

## 1.0.0
- Initial public release.
- Screenshot on GNOME 49+/Wayland via the `allow-gnome-screenshot` extension (scoped, no global unsafe_mode).
- Per-display and per-window capture via Mutter DisplayConfig + the Window Calls extension (`screenshot-display`).
- Input injection via `ydotool`/`/dev/uinput` (rootless persistent user service).
- Click-by-element (SOM) via hybrid coordinates — AT-SPI WINDOW-relative extents + Window Calls window origin (`locate-element`), with a vision fallback for elements that zero even WINDOW extents.
- Window actions (focus/move/resize/maximize/close) via Window Calls.
- Optional GNOME Remote Desktop (Remote Login) setup + an authoritative server-side RDP auth-failure diagnosis guide.
