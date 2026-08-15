################################################################################
#
#  Ole Miss ASCII Art
#
#  Displays Ole Miss branded ASCII art in team colors
#
################################################################################

import datetime as dt
from segment_parent import SegmentParent

INTRO = 'ASCII ART BY METAL SHOP'

RED     = '\033[31m'
GREEN   = '\033[32m'
YELLOW  = '\033[33m'
BLUE    = '\033[34m'
MAGENTA = '\033[35m'
CYAN    = '\033[36m'
WHITE   = '\033[37m'

class Segment(SegmentParent):

    def __init__(self, display, init):
        super().__init__(display, init, default_refresh=99999, default_intro=INTRO)

    def refresh_data(self):
        self.data = {'fetched_on': dt.datetime.now()}

    def pr(self, color, text):
        self.d.set_color(color)
        self.d.print(text)

    def pr_38_v4(self, text):
        # Each row of this hand-drawn logo is a fixed shape (~25 chars)
        # that can't be reflowed like normal text without destroying the
        # art, and printing it char-by-char via end='' bypasses the
        # normal print()/word-wrap width check entirely -- confirmed
        # live, it ran straight past the right edge of the screen under
        # composite's narrower column budget. Truncating here is a
        # not-broken floor, not a real fix for the art itself -- if
        # d.width ever ends up under ~25 again the logo will just get
        # clipped rather than reflowed.
        text = text[: self.d.width]
        for c in text:
            if c in '/\\_|<':
                self.d.set_color(BLUE)
            elif c == '#':
                self.d.set_color(RED)
            elif c == '$':
                self.d.set_color(BLUE)
            self.d.print(c, end='')
        self.d.print('')

    def show(self, fmt):
        if self.data_is_stale():
            self.refresh_data()
        d = self.d

        # 38 v4
        d.newline()
        self.pr(WHITE,' YOU ARE WATCHING CHANNEL')
        d.newline()
        self.pr_38_v4('  $$$$$$$$$$$$$$$$$$$$$$ ')
        self.pr_38_v4(' $$$######\\$$$######\\$$$$')
        self.pr_38_v4(' $$## ___##\\$##  __##\\$$$')
        self.pr_38_v4(' $$\\_/$$$## |## /$$## |$$')
        self.pr_38_v4(' $$$$##### /$$######  |$$')
        self.pr_38_v4(' $$$$\\___##\$##  __##<$$$')
        self.pr_38_v4(' $$##\\$$$## |## /$$## |$$')
        self.pr_38_v4(' $$\\######  |\\######  |$$')
        self.pr_38_v4(' $$$\\______/$$\\______/$$$')
        self.pr_38_v4('  $$$$$$$$$$$$$$$$$$$$$$ ')
        d.wait_beats(3)