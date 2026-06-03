# agent-skills

Public, reusable [agent skills](https://hermes-agent.nousresearch.com/docs) by ANG Ventures —
self-contained capabilities for AI coding/ops agents. Each skill lives under `skills/<name>/` with
a `SKILL.md`, optional `scripts/`, and `references/`.

## Skills

- **[peekaboo-linux-gnome-wayland-computer-use](skills/peekaboo-linux-gnome-wayland-computer-use/)** —
  See and control GNOME/Wayland desktops: `gnome-screenshot` capture, per-display/window cropping,
  `ydotool` input injection, click-by-element via AT-SPI hybrid coordinates, and optional GNOME
  Remote Desktop. The Linux/Wayland counterpart to macOS computer-use.

## Install

With the ClawHub CLI:
```bash
clawhub install peekaboo-linux-gnome-wayland-computer-use
```

Or with Hermes Agent (tap this repo as a skill source), or just copy a skill folder into your
agent's skills directory.
