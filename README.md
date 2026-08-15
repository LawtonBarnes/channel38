# CHANNEL 38 (`channel38`)

A vintage-style news terminal for a Raspberry Pi + CRT, displaying live
Ole Miss and SEC football updates, college football rankings, and news
headlines over composite video in a TV-typewriter style (mimicking Don
Lancaster's TV Typewriter).

![Running on a real CRT](./img/TV_CH38.jpg)

Built for a Raspberry Pi 3B+ running Raspberry Pi OS Bookworm. A heavily
customized fork of [RetroFeed](https://github.com/JeffJetton/retrofeed)
by Jeff Jetton — this version replaces the general news/weather/finance
segments with Ole Miss/SEC-specific content and a full rewrite of the
rendering pipeline.

![Framebuffer capture](./img/SCREEN_CH38.png)

## Architecture

Renders via headless pygame (`SDL_VIDEODRIVER=dummy`) directly onto
`/dev/fb0`, with keyboard/remote input read via raw `evdev` — the same
architecture as its sibling apps [BARS](https://github.com/LawtonBarnes/bars)
and [LOUDNESS](https://github.com/LawtonBarnes/loudness). Column/row count
and font size are computed from real font metrics against the actual
framebuffer resolution (`display.py`'s `fit_font()`), not hardcoded, so it
self-corrects across different displays. No venv — `pygame`, `evdev`,
`numpy`, `beautifulsoup4`, and `requests` are all system packages.

## Keyboard / remote controls

| Key | Action |
|---|---|
| `↑` / `↓` | Skip forward/backward through the segment playlist |
| `Home` | Jump straight back to the app menu |
| `Q` / `Esc` / `Back` | Quit to the app menu |
| Vol `↑` / `↓` | Toggle the typewriter click sound on/off |

## Segments

Ole Miss football results/schedule, SEC football roundup, Pete Golding
news, CFB rankings, AP Top 25, AP News, ESPN College Football, NYT News,
current conditions, date/time, and Ole Miss/Channel 38 ASCII art. Segment
order, timing, and which are active are controlled via `config.toml` —
see `segments/` for individual modules, each following the pattern in
`segments/template.py`.

## Credits

- Built on [RetroFeed](https://github.com/JeffJetton/retrofeed) by Jeff Jetton (MIT License — see `LICENSE`)
- Font: `VCR_OSD_MONO_1.001.ttf`

## License

MIT — see `LICENSE`. Original copyright retained per the terms of the upstream RetroFeed project.
