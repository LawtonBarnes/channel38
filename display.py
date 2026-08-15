################################################################################
#
#   Display Class
#
#   - Stores configured display settings (print speeds, verbosity, etc.)
#   - Provides various printing and text processing functions to segments
#
#   Every segment should accept a Display object at initialization and use its
#   functions for all text display, including linefeeds, headers, update
#   messages, and pauses ("beats") within the segment.
#
#   Renders onto a pygame Surface written directly to /dev/fb0 (see
#   retrofeed.py's main(), which builds the FrameBuffer/font/evdev pieces
#   and hands them to this class) rather than printing to a real terminal
#   -- see bars.py for why (SDL's kmsdrm driver doesn't survive composite
#   output, and this keeps the same architecture as bars/vizmic). Segment
#   code below this class is completely unaware of the change: every
#   segment only ever calls print()/newline()/set_color()/wait_beats()/
#   print_header()/print_update_msg(), never touches rendering directly.
#
################################################################################

import random
import re
import textwrap
import time

import pygame
from evdev import ecodes


class QuitRequested(BaseException):
    # Raised when Q/Esc/Back/Menu is pressed (or SIGTERM/SIGINT received)
    # during output, to break out of whatever segment is currently
    # printing -- returns to the App Menu (this process's immediate
    # parent). Inherits BaseException (not Exception) so it can't be
    # accidentally swallowed by segments' `except Exception:`/bare
    # `except:` blocks around their own data-fetching code.
    pass


class GoHomeRequested(BaseException):
    # Raised when Home is pressed -- distinct from QuitRequested: this
    # skips *past* the App Menu straight to Health Monitor instead of
    # just returning to it. See retrofeed.py's main() (which exits with
    # EXIT_GOTO_HOME on this) and menu.py's launch_app() (which relays
    # that exit code). Same BaseException rationale as QuitRequested.
    pass


class SegmentSkip(BaseException):
    # Raised when Up/Down is pressed during output, to jump the main
    # playlist loop forward (+1) or backward (-1) instead of quitting.
    # Same BaseException rationale as QuitRequested above.
    def __init__(self, delta):
        super().__init__()
        self.delta = delta


class ShutdownRequested(BaseException):
    # Raised when YES is confirmed in the Power-button confirmation dialog.
    # Same BaseException rationale as QuitRequested above.
    pass


class RestartRequested(BaseException):
    # Raised when RESTART is confirmed in the Power-button confirmation
    # dialog. Same BaseException rationale as QuitRequested above.
    pass


# Only these 7 standard ANSI SGR codes are used anywhere in the segment
# codebase (grep-verified) -- no bold, background, or 256-color codes.
ANSI_COLORS = {
    31: (220, 50, 50),    # red
    32: (0, 210, 0),      # green
    33: (230, 200, 0),    # yellow
    34: (90, 130, 255),   # blue
    35: (220, 90, 220),   # magenta
    36: (0, 210, 210),    # cyan
    37: (230, 230, 230),  # white
}
DEFAULT_COLOR = ANSI_COLORS[37]
BG_COLOR = (0, 0, 0)
WHITE = (255, 255, 255)
ORANGE = (0xFF, 0xA5, 0x00)

POWER_OPTIONS = ["NO", "YES", "RESTART"]
MOUSE_MOVE_THRESHOLD = 12  # cumulative REL_X/REL_Y units before it counts as one direction press


def _rel_to_keycode(axis, accum):
    """Translates accumulated air-mouse-mode movement into the same
    discrete direction the remote's keyboard-mode D-pad would send."""
    if axis == "x":
        return ecodes.KEY_RIGHT if accum > 0 else ecodes.KEY_LEFT
    return ecodes.KEY_DOWN if accum > 0 else ecodes.KEY_UP

# Trailing typewriter cursor, drawn one char-cell past whatever's
# currently "typed" -- matches the underscore cursor the old
# terminal-print version showed natively. Purely a _redraw()-time
# addition (see _blit_cursor below), never appended to _current_line,
# so it can't affect word-wrap (print()'s wrap check only ever sees
# the real text) or get saved into a committed line.
CURSOR_CHAR = '_'

_ANSI_RE = re.compile(r'\033\[(\d+)m')


class Display:

    def __init__(self, display_settings, fb, font, selector, quit_flag, click_sound,
                 underscan=0.0, target_width=None, font_path=None):
        # Use sensible defaults if any of the keys are missing
        self._cps = display_settings.get('cps', 20)
        self._print_delay = 1/self._cps
        self._newline_cps = display_settings.get('newline_cps', 100)
        self._newline_delay = 1/self._newline_cps
        self._beat_delay = display_settings.get('beat_seconds', 1)
        self._force_uppercase = display_settings.get('force_uppercase', True)
        self._verbose_updates = display_settings.get('verbose_updates', True)
        self._prefer_24hr_time = display_settings.get('prefer_24hr_time', True)

        # Rendering pieces, built by retrofeed.py's main() (same FrameBuffer/
        # evdev-selector pattern as bars.py/menu.py).
        self._fb = fb
        self._font = font
        self._selector = selector
        self._quit_flag = quit_flag  # 1-element list; [0]=True on SIGTERM/SIGINT
        self._click_sound = click_sound  # pygame.mixer.Sound, or None if audio init failed
        self._click_enabled = True  # remote Volume Up/Down toggles this, see _check_quit()

        # `underscan` reserves a border (as a fraction of each dimension,
        # split evenly on both sides) so text doesn't run into the edge of
        # a CRT that overscans -- e.g. 0.15 leaves a 15% margin on every
        # side, 70% of the frame left as usable drawing area.
        self._margin_x = int(fb.width * underscan)
        self._margin_y = int(fb.height * underscan)
        usable_w = fb.width - 2 * self._margin_x
        usable_h = fb.height - 2 * self._margin_y

        # Row count is derived from actual measured font metrics against
        # the usable (post-underscan) area -- not read from config, since a
        # hand-picked font point size won't land on an exact target count.
        # Column count (word-wrap width) works the same way UNLESS
        # `target_width` is given, in which case that exact value is used
        # as long as it actually fits (no font size lands on every column
        # count exactly, e.g. nothing hits 26 columns cleanly at this
        # font/frame combination -- explicitly targeting it, capped by
        # what's actually safe, beats settling for whatever the nearest
        # size happens to compute).
        self._char_w = font.size('M')[0]
        self._char_h = font.get_linesize()
        max_width = max(1, usable_w // self._char_w)
        self._width = min(target_width, max_width) if target_width is not None else max_width
        self._visible_rows = max(1, usable_h // self._char_h)
        self._height = self._visible_rows

        self._color = DEFAULT_COLOR
        self._lines = []          # committed rows: list of list[(char, rgb)]
        self._current_line = []   # in-progress row being "typed"

        self._dialog_title_font = pygame.font.Font(str(font_path), 36)
        self._dialog_option_font = pygame.font.Font(str(font_path), 32)
        self._power_dialog_selection = 0  # index into POWER_OPTIONS, defaults to NO
        self._rel_accum = {"x": 0, "y": 0}

    # Getters, but no setters (to hopefully keep other code from altering display values)
    @property
    def height(self):
        return self._height

    @property
    def width(self):
        return self._width

    @property
    def size(self):
        return (self.height, self.width)

    @property
    def cps(self):
        return self._cps

    @property
    def print_delay(self):
        return self._print_delay

    @property
    def newline_cps(self):
        return self._newline_cps

    @property
    def newline_delay(self):
        return self._newline_delay

    @property
    def beat_delay(self):
        return self._beat_delay

    @property
    def force_uppercase(self):
        return self._force_uppercase

    @property
    def verbose_updates(self):
        return self._verbose_updates

    @property
    def prefer_24hr_time(self):
        return self._prefer_24hr_time

    def __str__(self):
        s = f'Display: {self.height} Rows, {self.width} Columns, '
        s += f'{self.cps} CPS (Print Delay: {self.print_delay}s), '
        s += f'Newline CPS: {self.newline_cps} '
        s += f'(Newline Delay: {self.newline_delay}s), '
        s += f'Beat Delay: {self.beat_delay}s, '
        s += f'Force Uppercase: {self.force_uppercase}, '
        s += f'Verbose Updates: {self.verbose_updates}, '
        s += f'24hr Time: {self.prefer_24hr_time}'
        return s


########  Quit handling  #######################################################

    def _check_quit(self):
        if self._quit_flag[0]:
            raise QuitRequested()
        for key, _ in self._selector.select(timeout=0):
            device = key.fileobj
            for event in device.read():
                if event.type == ecodes.EV_KEY and event.value == 1:  # 1 == key down (skip up/repeat)
                    self._handle_keycode(event.code)
                elif event.type == ecodes.EV_REL:
                    self._handle_rel_event(event.code, event.value)

    def _handle_keycode(self, code):
        if code in (ecodes.KEY_HOMEPAGE, ecodes.KEY_HOME):
            raise GoHomeRequested()
        if code in (ecodes.KEY_Q, ecodes.KEY_ESC, ecodes.KEY_BACK, ecodes.KEY_COMPOSE):
            raise QuitRequested()
        if code == ecodes.KEY_UP:
            raise SegmentSkip(1)
        if code == ecodes.KEY_DOWN:
            raise SegmentSkip(-1)
        if code in (ecodes.KEY_VOLUMEUP, ecodes.KEY_F2):
            self._click_enabled = True
        if code in (ecodes.KEY_VOLUMEDOWN, ecodes.KEY_F3):
            self._click_enabled = False
        if code == ecodes.KEY_POWER:
            self._power_dialog()

    def _handle_rel_event(self, code, value):
        # REL_X (Left/Right) has no bound action outside the power dialog,
        # but is still accumulated for consistency -- see _rel_to_keycode.
        if code == ecodes.REL_Y:
            axis = "y"
        elif code == ecodes.REL_X:
            axis = "x"
        else:
            return
        self._rel_accum[axis] += value
        accum = self._rel_accum[axis]
        if abs(accum) < MOUSE_MOVE_THRESHOLD:
            return
        self._rel_accum[axis] = 0
        if axis == "y":
            self._handle_keycode(_rel_to_keycode(axis, accum))

    def _power_dialog(self):
        """Modal confirmation loop entered on the remote's Power button.
        Blocks (with its own evdev polling, independent of the segment
        print loop that called us) until NO/Back cancels it or YES/RESTART
        raises to unwind all the way back to retrofeed.py's main()."""
        self._power_dialog_selection = 0
        rel_accum = {"x": 0, "y": 0}
        self._redraw(power_dialog=True)
        while True:
            if self._quit_flag[0]:
                raise QuitRequested()
            for key, _ in self._selector.select(timeout=1):
                device = key.fileobj
                for event in device.read():
                    code = None
                    if event.type == ecodes.EV_KEY and event.value == 1:
                        code = event.code
                    elif event.type == ecodes.EV_REL and event.code in (ecodes.REL_X, ecodes.REL_Y):
                        axis = "x" if event.code == ecodes.REL_X else "y"
                        rel_accum[axis] += event.value
                        if abs(rel_accum[axis]) < MOUSE_MOVE_THRESHOLD:
                            continue
                        code = _rel_to_keycode(axis, rel_accum[axis])
                        rel_accum[axis] = 0
                    if code is None:
                        continue

                    if code in (ecodes.KEY_LEFT, ecodes.KEY_UP):
                        self._power_dialog_selection = (self._power_dialog_selection - 1) % len(POWER_OPTIONS)
                    elif code in (ecodes.KEY_RIGHT, ecodes.KEY_DOWN):
                        self._power_dialog_selection = (self._power_dialog_selection + 1) % len(POWER_OPTIONS)
                    elif code in (ecodes.KEY_ENTER, ecodes.KEY_KPENTER, ecodes.BTN_LEFT, ecodes.BTN_MOUSE):
                        choice = POWER_OPTIONS[self._power_dialog_selection]
                        if choice == "NO":
                            self._redraw()
                            return
                        elif choice == "YES":
                            raise ShutdownRequested()
                        else:
                            raise RestartRequested()
                    elif code in (ecodes.KEY_ESC, ecodes.KEY_BACK, ecodes.KEY_POWER):
                        self._redraw()
                        return
                    else:
                        continue
                    self._redraw(power_dialog=True)


########  Printing methods  ###################################################

    # Wait for n "beats" (default = 1).  Used below--available to segments too
    # Length of one beat is defined at configuration
    def wait_beats(self, n=1):
        if n < 0:
            n = 1
        for i in range(n):
            self._check_quit()
            time.sleep(self.beat_delay)

    def set_color(self, code):
        m = _ANSI_RE.match(code)
        if m:
            self._color = ANSI_COLORS.get(int(m.group(1)), DEFAULT_COLOR)

    # Slooow version of print()
    # Passed strings should usually be mixed case to give the user the option
    # to see them that way if they conifg force_uppercase to be false
    def print(self, s='', end='\n', instant=False):
        # instant=True skips per-character delay/click and the trailing
        # pause -- used by show_title() so startup credits don't slow down
        # launch. Normal segment output never sets this.
        # Use wrapping if string is longer than display width
        if len(s) > self.width:
            lines = textwrap.wrap(s, self.width, break_long_words=False, break_on_hyphens=False)
            last_i = len(lines) - 1
            for i, line in enumerate(lines):
                line_end = end if i == last_i else '\n'
                self._print_line(line, end=line_end, instant=instant)
            return
        self._print_line(s, end=end, instant=instant)

    def _print_line(self, s, end='\n', instant=False):
        for c in s:
            if self._force_uppercase:
                c = c.upper()
            self._current_line.append((c, self._color))
            if instant:
                continue
            self._check_quit()
            self._redraw()
            if c != ' ' and self._click_sound is not None and self._click_enabled:
                # play(), not a subprocess -- spawning `aplay` per
                # character used to both silently deadlock (see project
                # memory on pygame.init()'s mixer) and, once that was
                # fixed, come out arrhythmic: process-spawn/PipeWire-
                # connection overhead exceeding the ~20ms inter-character
                # delay at typing speed, piling up overlapping instances.
                # pygame.mixer plays overlapping short sounds natively
                # with no per-call spawn cost.
                self._click_sound.play()
            time.sleep(self.print_delay)
        # end='' (only other value ever used) means "stay on this line" --
        # anything else (including the default '\n') commits it, matching
        # the original terminal version's behavior.
        if end != '':
            self._commit_line()
        elif instant:
            self._redraw()
        if not instant:
            time.sleep(self.print_delay)

    def _commit_line(self):
        self._lines.append(self._current_line)
        self._current_line = []
        if len(self._lines) > self._visible_rows:
            self._lines = self._lines[-self._visible_rows:]
        self._redraw()

    # Slooow Newline - the original prints `width` space characters (each
    # with a per-character delay) then a real newline, so that calling
    # newline(delay) between segments creates a timed pause with a
    # randomized mid-pause beat. We don't need to actually draw invisible
    # spaces -- just replicate the timing/quit-check loop and commit the
    # line once.
    def newline(self, delay=None, instant=False):
        if instant:
            self._commit_line()
            return
        self._check_quit()
        self._commit_line()
        pause_pos = random.randrange(self.width)
        for i in range(self.width):
            self._check_quit()
            time.sleep(self.newline_delay)
            if i == pause_pos and delay is not None:
                time.sleep(delay)
        time.sleep(self.newline_delay)

    # Display the passed string as a segment header, surrounded by markers
    def print_header(self, s, left_marker=' ', right_marker=None):
        if right_marker is None:
            right_marker = left_marker
        s = s.strip()
        if self.force_uppercase:
            s = s.upper()
        num_markers = 0
        if len(s) + 4 < self.width:
            num_markers = int((self.width - 4 - len(s)) / 2)
        self.print(left_marker * num_markers, end='')
        self.print('  ' + s + '  ', end='')
        self.print(right_marker * num_markers, end='')
        self.print()

    # Display passed string as an "updating..." message
    def print_update_msg(self, m):
        if self.verbose_updates:
            self.set_color('\033[32m')
            # print() only wrap-checks the string passed to *this* call --
            # since the trailing "..." + "]" get appended via separate
            # print(end='') calls below, wrapping against the full
            # self.width here (like print() would on its own) could still
            # leave the last wrapped line too close to the edge once that
            # suffix is tacked on. Wrapping against self.width - 4 instead
            # guarantees every line -- including whichever ends up last --
            # leaves room for it, so the suffix never needs to truncate the
            # message itself, just word-wrap it a line earlier.
            prefix = f'[{m}'
            max_width = self.width - 4
            if len(prefix) > max_width:
                lines = textwrap.wrap(prefix, max_width, break_long_words=False, break_on_hyphens=False)
            else:
                lines = [prefix]
            for line in lines[:-1]:
                self.print(line)
            self.print(lines[-1], end='')
            for i in range(3):
                self.wait_beats()
                self.print('.', end='')
            self.wait_beats()
            self.print(']')
            self.newline()


########  Rendering  ###########################################################

    def _redraw(self, power_dialog=False):
        canvas = pygame.Surface((self._fb.width, self._fb.height))
        canvas.fill(BG_COLOR)
        rows = self._lines[-self._visible_rows:]
        y = self._margin_y
        for line in rows:
            self._blit_line(canvas, line, y)
            y += self._char_h
        if y < self._fb.height - self._margin_y:
            self._blit_line(canvas, self._current_line, y)
            self._blit_cursor(canvas, y)
        if power_dialog:
            self._draw_power_dialog(canvas)
        self._fb.write_surface(canvas)

    def _draw_power_dialog(self, canvas):
        lines = ["ARE YOU SURE YOU WANT", "TO SHUT DOWN?"]
        line_surfs = [self._dialog_title_font.render(line, True, WHITE) for line in lines]
        option_surfs = [
            self._dialog_option_font.render(opt, True, BG_COLOR if i == self._power_dialog_selection else ORANGE)
            for i, opt in enumerate(POWER_OPTIONS)
        ]

        pad_x, pad_y, gap = 40, 24, 40
        options_w = sum(s.get_width() for s in option_surfs) + gap * (len(option_surfs) - 1)
        content_w = max(max(s.get_width() for s in line_surfs), options_w)
        content_h = (sum(s.get_height() for s in line_surfs) + 10 * (len(line_surfs) - 1)
                     + 30 + option_surfs[0].get_height())

        box = pygame.Surface((content_w + pad_x * 2, content_h + pad_y * 2))
        box.fill(BG_COLOR)
        pygame.draw.rect(box, ORANGE, box.get_rect(), 3)

        y = pad_y
        for surf in line_surfs:
            box.blit(surf, ((box.get_width() - surf.get_width()) // 2, y))
            y += surf.get_height() + 10
        y += 20

        x = (box.get_width() - options_w) // 2
        for i, surf in enumerate(option_surfs):
            if i == self._power_dialog_selection:
                highlight = pygame.Rect(x - 10, y - 6, surf.get_width() + 20, surf.get_height() + 12)
                pygame.draw.rect(box, ORANGE, highlight)
            box.blit(surf, (x, y))
            x += surf.get_width() + gap

        canvas.blit(box, ((self._fb.width - box.get_width()) // 2, (self._fb.height - box.get_height()) // 2))

    def _blit_line(self, canvas, line, y):
        x = self._margin_x
        for c, color in line:
            if c != ' ':
                surf = self._font.render(c, True, color)
                canvas.blit(surf, (x, y))
            x += self._char_w

    def _blit_cursor(self, canvas, y):
        # Only the in-progress (last, uncommitted) row ever gets a cursor --
        # called just for that one row in _redraw() above. Skipped once the
        # row is already full so it never draws past the margin.
        if len(self._current_line) >= self._width:
            return
        x = self._margin_x + len(self._current_line) * self._char_w
        surf = self._font.render(CURSOR_CHAR, True, self._color)
        canvas.blit(surf, (x, y))


########  Formatting helpers  #################################################

    # Returns a string for the time given by datetime object dt
    def fmt_time_text(self, dt, use24=None):
        if use24 is None:
            use24 = self.prefer_24hr_time
        h = dt.hour
        if use24:
            if h == 0:
                h = 12
            elif h > 12:
                h -= 12
        return str(h) + dt.strftime(":%M%p")


    # Returns a string for the date givcen by datetime object dt
    @classmethod
    def fmt_date_text(cls, dt):
        date_text = dt.strftime("%A, %B ")
        day_num = dt.day
        date_text += str(day_num)
        if day_num in (1, 21, 31):
            date_text += 'st'
        elif day_num in (2, 22):
            date_text += 'nd'
        elif day_num in (3, 23):
            date_text += 'rd'
        else:
            date_text += 'th'
        return date_text


    # Substitute some unicode characters, remove others
    # This also removes returns and strips whitespace at ends
    @classmethod
    def clean_chars(cls, s):
        new_s = ''
        for c in s:
            u = ord(c)
            # Tab = four spaces
            if u == 9:
                new_s += '    '
                continue
            # Fancy puncuation and other special characters
            if u >= 0x2013:
                # Various dashes
                if 0x2013 <= u <= 0x2017:
                    new_s += '-'
                # Double quotes
                elif u == 0x201C or u == 0x201D:
                    new_s += '"'
                # Single quotes
                elif u == 0x2018 or u == 0x2019:
                    new_s += "'"
                # Bullet
                elif u == 0x2022:
                    new_s += "*"
                # Ellipsis...
                elif u == 0x2026:
                    new_s += '...'
                # Copyright and Reg Trmk
                elif u == 0x00A9:
                    new_s += '(c)'
                elif u == 0x00AE:
                    new_s += '(R)'
                # Capital and lowercase tilde-n
                elif u == 0x00D1:
                    news_s += 'N'
                elif u == 0x00F1:
                    news_s += 'n'
            # Any old-school ASCII may pass
            elif (32 <= u <= 126):
                new_s += c
        return new_s.strip()


    # Pulls out a few HTML tags
    @classmethod
    def strip_tags_DEPRECATED(cls, s):
        s = s.replace('\\u003c', '<')
        s = s.replace('\\"', '"')
        s = s.replace('</a>', '')
        while True:
            start_pos = s.find('<a')
            if start_pos < 0:
                break
            end_pos = s.find('>', start_pos)
            if end_pos < 0:
                break
            s = s[0:start_pos] + s[end_pos+1:]
        s = s.replace('<br>', '\n')
        s = s.replace('<BR>', '\n')
        return s
