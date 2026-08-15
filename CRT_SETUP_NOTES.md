# RetroFeed CRT Setup Notes

How to get the Pi 3B+ outputting a big, chunky, retro-style console to a
composite (RCA/yellow cable) CRT. Written after a full from-scratch rebuild
on 2026-06-19, following a reflash to 64-bit Raspberry Pi OS.

## The one rule that matters more than any other

**Disable the `vc4-kms-v3d` driver entirely.** Comment out every line in
`config.txt` that says `dtoverlay=vc4-kms-v3d` (there may be more than one —
check the `[all]`, `[cm4]`, and `[cm5]` sections, not just the top of the file).

The modern KMS graphics driver does not honor `framebuffer_width` /
`framebuffer_height`, does not reliably apply `console-setup` fonts, and
generally fights every classic Pi composite-TV trick. The old-school
`fbcon` framebuffer console (what you get once KMS is disabled) is what
actually respects these settings.

**Symptom that tells you KMS is still active:** overscan settings seem to
work for the first second or two of boot, then the picture "resets" to a
different size/position partway through. That's KMS taking over from the
firmware-level framebuffer.

## Why this is tricky

There are two completely different display stacks at play, and they don't
share settings:

| | Legacy (fbcon) | Modern (KMS) |
|---|---|---|
| Enabled by | `dtoverlay=vc4-kms-v3d` commented out | `dtoverlay=vc4-kms-v3d[,composite]` present |
| Respects `framebuffer_width/height` | Yes — acts as a virtual buffer the GPU scales up | No — ignored |
| Respects `console-setup` fonts (`/etc/default/console-setup`) | Mostly yes | Unreliable — font resets on login/VT switch |
| Respects `fbcon=font:` kernel param | Yes | No — no fbcon attaches, dmesg shows nothing |
| Respects `video=Composite-1:...` in cmdline.txt | N/A (not used) | Yes |

We spent a long night trying every KMS-side trick (cmdline `video=`,
systemd font services, `fbcon=font:` params, VGA bitmap fonts) because the
framebuffer was reporting a real resolution (720x480) and the resolution
genuinely was correct — it was the **font sizing and column math** that
silently failed every time, because KMS doesn't actually apply any of it.
Disabling KMS and going legacy fixed everything in one shot.

## The working recipe

### 1. `/boot/firmware/config.txt`

Comment out **every** `dtoverlay=vc4-kms-v3d` line (there were three in our
case — top of file, `[cm5]`, and `[all]`). Then set:

```ini
overscan_left=34
overscan_right=30
overscan_top=-48
overscan_bottom=-10
sdtv_mode=0
sdtv_aspect=1
sdtv_disable_colorburst=1
enable_tvout=1
disable_overscan=0
overscan_scale=1
```

- `sdtv_mode=0` = NTSC. (PAL would be `2`.)
- `sdtv_disable_colorburst=1` = monochrome/green-screen style. Set to `0`
  (or omit) for color.
- Overscan values are CRT-specific — start here, nudge in increments of
  ~8-10 based on what you see. Negative numbers reduce border, positive
  numbers increase it.

Then set the framebuffer size — this is what actually controls font/column
math under legacy fbcon:

```ini
framebuffer_width=312
framebuffer_height=360
```

**Formula:** `framebuffer_width = font_width_px × target_columns`,
`framebuffer_height = font_height_px × target_rows`.

Our target: 26 columns × 15 rows, using `TerminusBold24x12` (24px tall,
12px wide):
```
312 = 12 × 26
360 = 24 × 15
```

If you change font or target columns/rows later, recalculate both numbers
together — they're a matched pair.

### 2. `/boot/firmware/cmdline.txt`

Single line, no line breaks. Add `logo.nologo` to the end to suppress the
raspberry boot logo. Do **not** add a `video=Composite-1:...` parameter —
that's a KMS-only mechanism and does nothing once KMS is disabled.

### 3. Console font — set it in `.bashrc`, not just `console-setup`

`/etc/default/console-setup` and the `console-setup.service` exist and
will run, but in our testing the font kept getting reset between that
service running and the `getty@tty1` login actually happening. The
reliable fix: set the font explicitly, as the literal last thing before
RetroFeed launches, inside the autostart block itself.

Relevant `~/.bashrc` block:
```bash
if [ "$(tty)" = "/dev/tty1" ]; then
  sudo setfont /usr/share/consolefonts/Uni2-TerminusBold24x12.psf.gz
  sleep 2
  stty cols 26 rows 15
  setterm --foreground yellow
  clear
  cd /home/metalshop/retrofeed
  python retrofeed.py
fi
```

This requires passwordless sudo for `setfont` specifically. Add via:
```bash
sudo visudo -f /etc/sudoers.d/consolefont
```
with contents:
```
metalshop ALL=(ALL) NOPASSWD: /usr/bin/setfont
```

`stty cols` / `rows` must match the framebuffer math above — same numbers
you used to calculate `framebuffer_width`/`height`.

### 4. Optional belt-and-suspenders: systemd font service

We also created `/etc/systemd/system/consolefont.service` to set the font
before `getty@tty1` starts (in addition to the `.bashrc` line). Not
strictly required if the `.bashrc` line works on its own, but doesn't
hurt:

```ini
[Unit]
Description=Set console font for CRT display
Before=getty@tty1.service

[Service]
Type=oneshot
ExecStart=/usr/bin/setfont /usr/share/consolefonts/Uni2-TerminusBold24x12.psf.gz
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
```
```bash
sudo systemctl enable consolefont.service
sudo systemctl daemon-reload
```

### 5. Console autologin

For the `.bashrc` tty1 check to ever fire, the Pi needs to boot to a text
console with autologin, not a desktop GUI:

```bash
sudo raspi-config
# System Options -> Boot / Auto Login -> Console Autologin
```

## Available font files (for future size changes)

Path: `/usr/share/consolefonts/`. Naming is `Uni2-TerminusBold{H}x{W}.psf.gz`
(height x width, in pixels). Sizes that exist: 14, 16, 18x10, 20x10,
22x11, 24x12, 28x14, 32x16. There is no 12x24 — if you want a tall/narrow
look instead of the current squarish/blocky look, the closest available
is 22x11.

## Files backed up alongside this note

- `config.txt.boot` — full working `/boot/firmware/config.txt`
- `cmdline.txt.boot` — full working `/boot/firmware/cmdline.txt`
- `bashrc.boot` — full working `~/.bashrc`
- `consolefont.service` — the systemd unit described above

## Quick rebuild checklist (next time)

1. Flash Pi OS, preload SSH key via Imager advanced settings.
2. Restore `~/retrofeed` from backup (`scp -r`).
3. Copy `config.txt.boot` → `/boot/firmware/config.txt`, confirm all
   `vc4-kms-v3d` lines are commented out.
4. Copy `cmdline.txt.boot` → `/boot/firmware/cmdline.txt`.
5. Copy `bashrc.boot` → `~/.bashrc` (or merge the tty1 block in manually).
6. Copy `consolefont.service` → `/etc/systemd/system/`, then
   `sudo systemctl enable consolefont.service`.
7. Add the sudoers exception for `setfont` (see above — this won't be in
   any backed-up file since it lives in `/etc/sudoers.d/`).
8. `sudo raspi-config` → Console Autologin.
9. Reboot, plug into the CRT, confirm.
