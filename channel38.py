################################################################################
#
#   retrofeed.py - Main entry point for running RetroFeed
#
#   - Reads in config.toml
#   - Instantiates Display and Segment objects based on the config file
#   - Cycles through the Segments and asks them to send info to standard output
#     (via Display), in the order/manner specified in the config file
#
#   Runs as `retrofeed` at the console. Same headless-pygame + direct-
#   /dev/fb0 + evdev architecture as bars.py/vizmic/menu.py -- see
#   bars.py's module docstring for the full rationale (SDL's kmsdrm
#   driver doesn't survive composite output, so pygame here only builds
#   surfaces/fonts, the framebuffer is written to directly, and the
#   keyboard is read via evdev instead of through SDL). display.py's
#   Display class does the actual rendering; segment code is unaware of
#   any of this and only ever calls Display's public print()/newline()/
#   etc. methods.
#
#   Jeff Jetton
#
#   January-October 2023
#
################################################################################



# Standard library imports
import argparse
import fcntl
import importlib.util
import os
import selectors
import signal
import subprocess
import sys
import time
import tomllib
from pathlib import Path

import evdev
from evdev import ecodes

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "alsa")

import pygame  # noqa: E402  (must come after SDL env vars are set)

# RetroFeed imports
from display import Display, GoHomeRequested, QuitRequested, RestartRequested, SegmentSkip, ShutdownRequested  # noqa: E402



# Globals...
VERSION = '1.3'
COPYRIGHT_YEAR = '2026'
EXPECTED_TABLES = ['display', 'segments', 'playlist']

# See menu.py -- Home exits with this so menu.py's launch_app() knows to
# hand off to Health Monitor instead of redrawing its own app list.
EXIT_GOTO_HOME = 42

BASE_DIR = Path(__file__).resolve().parent
FONT_PATH = BASE_DIR / "VCR_OSD_MONO_1.001.ttf"
CLICK_PATH = BASE_DIR / "click.wav"
SPLASH_PATH = BASE_DIR / "splash.png"  # optional -- see show_splash()
SPLASH_SECONDS = 3.0
BLACK = (0, 0, 0)  # only used by show_splash()'s letterbox fill -- this app is otherwise ANSI-color-string based, not RGB tuples
# Was a bare relative filename -- open()'d it fine when run manually
# from /opt/channel38 (matches CWD), but STRINGS launches every app
# with CWD=/ (no WorkingDirectory= in strings.service), so the same
# relative lookup silently resolved to /config.toml instead and hit
# the "Missing configuration file" early-return below every time,
# with zero indication it was a CWD problem rather than a truly
# missing file. Absolute, like every other path in this file.
CONFIG_FILENAME = str(BASE_DIR / 'config.toml')
MAX_FONT_SIZE = 64
MIN_FONT_SIZE = 8
UNDERSCAN = 0.10  # fraction of each dimension reserved as border, split both sides
TARGET_WIDTH = 26  # word-wrap column count
FRAME_W, FRAME_H = 720, 480

KDSETMODE = 0x4B3A
KD_TEXT = 0x00
KD_GRAPHICS = 0x01



def fit_font(target_width_chars, usable_w, max_size=MAX_FONT_SIZE, min_size=MIN_FONT_SIZE):
    # Picks the largest point size whose 'M' width still fits
    # target_width_chars columns in usable_w pixels -- a hardcoded point
    # size doesn't track how many actual pixels a TTF's glyphs end up
    # occupying at a given real resolution (health.py's HealthDisplay
    # uses this same measure-then-pick approach for the same reason).
    # A fixed FONT_SIZE here previously only "worked" because it was
    # tuned against HDMI's much wider usable area during development --
    # composite's narrower 720px real width left only ~19 columns at
    # that same fixed size instead of the intended 26.
    for size in range(max_size, min_size - 1, -1):
        candidate = pygame.font.Font(str(FONT_PATH), size)
        if candidate.size("M")[0] * target_width_chars <= usable_w:
            return candidate
    return pygame.font.Font(str(FONT_PATH), min_size)


def find_keyboard_devices():
    # See bars.py for why this filters by EV_KEY capability rather than
    # hardcoding device paths (remote controls split across several
    # /dev/input nodes, node numbers aren't stable across reboots).
    devices = []
    for path in evdev.list_devices():
        dev = evdev.InputDevice(path)
        if dev.capabilities().get(ecodes.EV_KEY):
            devices.append(dev)
    if not devices:
        # Puppets in the McBrain fleet run unattended, with no keyboard/
        # remote physically attached -- STRINGS launches this app
        # headless. An empty device list here just means the evdev
        # selector loop below never has anything to read, so the app
        # runs its normal render loop forever with no input reactivity,
        # rather than refusing to start. Production/dev use with a real
        # remote attached is unaffected.
        print("No keyboard input device found -- running headless/unattended.", file=sys.stderr)
    return devices


class FrameBuffer:
    """Direct writer for /dev/fb0, bypassing DRM page-flips entirely.

    Verbatim copy of bars.py's FrameBuffer -- see that file for the full
    rationale. Geometry is read from sysfs at open time since it depends
    on whichever output (composite/HDMI) is currently active.
    """

    def __init__(self, dev="/dev/fb0"):
        import mmap
        import numpy as np

        self._np = np
        sys_dir = Path("/sys/class/graphics") / Path(dev).name
        self.width, self.height = (int(x) for x in (sys_dir / "virtual_size").read_text().split(","))
        self.bpp = int((sys_dir / "bits_per_pixel").read_text())
        self.stride = int((sys_dir / "stride").read_text())
        self.bypp = self.bpp // 8
        self.row_bytes = self.width * self.bypp
        size = self.stride * self.height
        self.fd = os.open(dev, os.O_RDWR)
        self.mm = mmap.mmap(self.fd, size, mmap.MAP_SHARED, mmap.PROT_WRITE | mmap.PROT_READ)
        if self.bpp not in (16, 32):
            raise RuntimeError(f"Unsupported framebuffer depth: {self.bpp}bpp")

    def write_surface(self, surface):
        np = self._np
        if surface.get_size() != (self.width, self.height):
            surface = pygame.transform.scale(surface, (self.width, self.height))
        arr = pygame.surfarray.pixels3d(surface).transpose(1, 0, 2)  # (H, W, RGB) uint8
        if self.bpp == 16:
            r = arr[:, :, 0].astype(np.uint16) >> 3
            g = arr[:, :, 1].astype(np.uint16) >> 2
            b = arr[:, :, 2].astype(np.uint16) >> 3
            raw = ((r << 11) | (g << 5) | b).astype("<u2").tobytes()
        else:
            alpha = np.zeros((self.height, self.width, 1), dtype=np.uint8)
            raw = np.concatenate([arr[:, :, ::-1], alpha], axis=2).astype(np.uint8).tobytes()

        if self.stride == self.row_bytes:
            self.mm.seek(0)
            self.mm.write(raw)
        else:
            for y in range(self.height):
                self.mm.seek(y * self.stride)
                self.mm.write(raw[y * self.row_bytes : (y + 1) * self.row_bytes])

    def close(self):
        self.mm.close()
        os.close(self.fd)


def show_splash(fb):
    """Blocking splash shown once at launch, before the app's real
    content appears -- same technique/rationale as bars.py's version of
    this function, duplicated per this file's own no-shared-library
    convention. Writes straight to fb, bypassing the Display class
    entirely, since Display is ANSI-terminal/character-cell based and
    has no image-blitting concept of its own."""
    if not SPLASH_PATH.exists():
        return
    try:
        img = pygame.image.load(str(SPLASH_PATH)).convert()
    except (pygame.error, OSError) as exc:
        print(f"Splash load failed: {exc}", file=sys.stderr)
        return
    canvas = pygame.Surface((FRAME_W, FRAME_H))
    canvas.fill(BLACK)
    img_w, img_h = img.get_size()
    scale = min(FRAME_W / img_w, FRAME_H / img_h)
    scaled = pygame.transform.smoothscale(img, (int(img_w * scale), int(img_h * scale)))
    canvas.blit(scaled, ((FRAME_W - scaled.get_width()) // 2, (FRAME_H - scaled.get_height()) // 2))
    fb.write_surface(canvas)
    time.sleep(SPLASH_SECONDS)



def check_config_tables(config):
    # Just throw an error if any of the main three sections aren't in config
    # Nothing fancy...
    missing_tables = []
    for table in EXPECTED_TABLES:
        if table not in config:
            missing_tables.append(table)
    if len(missing_tables) > 0:
        raise RuntimeError('Table(s) missing in config: ' + ', '.join(missing_tables))
    # Make sure each declared segment has at least a module key
    bad_segments = []
    for key in config['segments']:
        if 'module' not in config['segments'][key]:
            bad_segments.append(key)
    if len(bad_segments) > 0:
        raise RuntimeError('No module defined for segment(s) in config: ' + ', '.join(bad_segments))



def override_timings(config):
    config['display']['cps'] = 1000
    config['display']['newline_cps'] = 1000
    config['display']['beat_seconds'] = 0.1
    config['playlist']['segment_pause'] = 1
    return config


def instantiate_segments(config, d):
    # Segments dictionary holds references to all instantiated objects
    segments = {}
    # Keep track of intro strings we show, so we don't show any more than once
    shown_intros = []
    # Go through config and initialize all required segments
    # We don't check to see if they exist, so... fingers crossed!
    for key in config['segments']:
        mod_name = config['segments'][key]['module']
        # Just in case the user put the .py on the end...
        if mod_name.endswith('.py'):
            mod_name = mod_name[0:-3]
        # Import, instantiate, and add to segments dictionary
        # using the specified key (which will match in playlist)
        module = importlib.import_module('segments.' + mod_name)
        segments[key] = module.Segment(d, config['segments'][key])
        # If we haven't heard it already, give the module
        # a chance to introduce itself...
        intro = segments[key].intro
        if intro is not None:
                intro = intro.strip()
                if intro != '' and intro not in shown_intros:
                    # instant=True: these source-credit intros run once at
                    # startup, right after the copyright screen -- same
                    # treatment as show_title() so they don't slow launch.
                    # A short fixed sleep after each one (much shorter than
                    # the typewriter print_delay, but nonzero) keeps this
                    # block of credits from blowing straight past the
                    # visible row count before it can be read.
                    d.set_color('\033[32m')
                    d.print(intro, instant=True)
                    d.newline(instant=True)
                    time.sleep(0.3)
                    shown_intros.append(intro)
    return segments


def parse_seg_key_and_fmt(seg):
    seg_key = ''
    seg_fmt = {}
    # If the segment is just a plain-old string,
    # use that as the key and assume no formatting
    if isinstance(seg, str):
        seg_key = seg
    # But if it's a list, use the first element as key
    # and second element (if any) as format stuff
    elif isinstance(seg, list):
        seg_key = seg[0]
        if len(seg) > 1:
            seg_fmt = seg[1]
    return (seg_key, seg_fmt)


def show_title(d):
    # instant=True: no per-character delay/click/newline-pause, so the
    # startup credits flash by instead of slowing down launch.
    d.set_color('\033[32m')
    d.print(f'RETROFEED - VERSION {VERSION}', instant=True)
    d.print(f'Copyright (c) {COPYRIGHT_YEAR} Jeff Jetton', instant=True)
    d.print('MIT License', instant=True)
    d.newline(instant=True)


def get_args():
    parser = argparse.ArgumentParser(description='Send a retro-style newsfeed to a Pi console.')
    parser.add_argument('-f', '--fast', action='store_true', dest='fast_mode',
                        help='Use fast display speed, overriding config file settings')
    parser.add_argument('-v', '--version', action='version', version='RetroFeed ' + VERSION)
    parser.add_argument('filename', nargs='?', default=CONFIG_FILENAME,
                        help='Specify TOML configuration file. If omitted, defaults to config.toml')
    return parser.parse_args()



###############################################################################

def main():

    # Handle command-line options/arguments
    args = get_args()

    # Get config info from the TOML file
    try:
        with open(args.filename, 'rb') as f:
            config = tomllib.load(f)
        check_config_tables(config)
        # If user ran with the -f flag, use faster display timings, which is
        # useful for quickly checking segment order/format changes, etc.
        if args.fast_mode:
            config = override_timings(config)
    except FileNotFoundError:
        print(f'\n*** Missing configuration file "{CONFIG_FILENAME}"\n')
        return

    # pygame/SDL installs its own SIGINT/SIGTERM handler that turns the
    # signal into an SDL_QUIT event; since input is read via evdev and
    # nothing drains pygame's event queue, that would silently swallow
    # both signals. Install plain handlers so the process still
    # terminates normally -- see bars.py for the same pattern.
    quit_flag = [False]
    def handle_signal(signum, frame):
        quit_flag[0] = True
    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    # Deliberately not the blanket pygame.init() -- only initialize the
    # subsystems actually used, mixer included (see click_sound below for
    # why mixer is now one of them, and project memory for why routing
    # the click through a subprocess `aplay` call instead used to both
    # silently deadlock *and*, once that deadlock was fixed, come out
    # arrhythmic -- per-character process-spawn overhead exceeding the
    # inter-character delay at typing speed).
    pygame.display.init()
    pygame.font.init()
    pygame.display.set_mode((FRAME_W, FRAME_H))  # headless (dummy driver); needed for .convert()

    try:
        pygame.mixer.init()
        click_sound = pygame.mixer.Sound(str(CLICK_PATH))
    except pygame.error as exc:
        print(f"Audio init failed, click sound disabled: {exc}", file=sys.stderr)
        click_sound = None

    fb = FrameBuffer()
    # Same margin formula Display.__init__ uses below -- duplicated here
    # (rather than picking the font after constructing Display) because
    # the font has to already exist to hand to Display's constructor.
    usable_w = fb.width - 2 * int(fb.width * UNDERSCAN)
    font = fit_font(TARGET_WIDTH, usable_w)

    kbd_devices = find_keyboard_devices()
    selector = selectors.DefaultSelector()
    for dev in kbd_devices:
        selector.register(dev, selectors.EVENT_READ)

    # Tell the console driver to stop drawing its own cursor/text over our
    # framebuffer writes. Only possible on a real VT (not over SSH, and
    # not without any controlling terminal at all) -- see bars.py.
    tty_fd = None
    console_graphics_mode = False
    try:
        tty_fd = os.open("/dev/tty", os.O_RDWR)
        fcntl.ioctl(tty_fd, KDSETMODE, KD_GRAPHICS)
        console_graphics_mode = True
    except OSError as exc:
        print(f"Console graphics mode not available: {exc}", file=sys.stderr)

    show_splash(fb)

    d = Display(config['display'], fb, font, selector, quit_flag, click_sound,
                underscan=UNDERSCAN, target_width=TARGET_WIDTH, font_path=FONT_PATH)

    pending_power_action = None  # None, "shutdown", or "restart"
    pending_exit_code = 0  # 0 or EXIT_GOTO_HOME
    try:
        show_title(d)
        segments = instantiate_segments(config, d)

        # Unpack the playlist
        segment_pause = config['playlist']['segment_pause']
        order = config['playlist']['order']

        d.newline()
        d.newline()

        # Main loop -- index-based (not `for seg in order`) so the remote's
        # Up/Down can jump forward/backward through the playlist; order[i]
        # wraps in both directions via Python's modulo (negative i wraps
        # backward correctly, e.g. -1 % n == n - 1).
        i = 0
        n = len(order)
        while True:
            seg = order[i % n]
            d.newline()
            d.newline()

            (seg_key, seg_fmt) = parse_seg_key_and_fmt(seg)

            try:
                if seg_key not in segments:
                    d.newline()
                    d.print_header(f'Missing Segment "{seg_key}"', '*')
                    d.newline(segment_pause)
                else:
                    # Show the segment, with any special formating
                    segments[seg_key].show(seg_fmt)

                    d.newline()
                    d.newline(segment_pause)
            except SegmentSkip as skip:
                i += skip.delta
                continue

            i += 1
    except (QuitRequested, KeyboardInterrupt):
        pass
    except GoHomeRequested:
        pending_exit_code = EXIT_GOTO_HOME
    except ShutdownRequested:
        pending_power_action = "shutdown"
    except RestartRequested:
        pending_power_action = "restart"
    finally:
        if console_graphics_mode:
            fcntl.ioctl(tty_fd, KDSETMODE, KD_TEXT)
            os.write(tty_fd, b"\033[2J\033[H")  # clear screen, home cursor
        if tty_fd is not None:
            os.close(tty_fd)
        fb.close()
        pygame.quit()

    if pending_power_action == "shutdown":
        subprocess.run(["sudo", "shutdown", "-h", "now"])
    elif pending_power_action == "restart":
        subprocess.run(["sudo", "shutdown", "-r", "now"])

    sys.exit(pending_exit_code)



if __name__ == "__main__":
    main()
