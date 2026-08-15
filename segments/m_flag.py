################################################################################
#
#  M Flag ASCII Art
#
#  Displays the Ole Miss "M" flag graphic in team colors
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

    def pr_flag(self, text):
        for c in text:
            if c == '#':
                self.d.set_color(RED)
            elif c == '$':
                self.d.set_color(BLUE)
            elif c in '|*/\\':
                self.d.set_color(WHITE)
            self.d.print(c, end='')
        self.d.print('')

    def show(self, fmt):
        if self.data_is_stale():
            self.refresh_data()
        d = self.d

        # MFlag Graphic
        d.newline()
        self.pr_flag('##########################')
        self.pr_flag('#|$$$$$$\\########/$$$$$$|#')
        self.pr_flag('#|$$*$$*$\\######/$*$$*$$|#')
        self.pr_flag('##|$$$|$$$\\####/$$$|$$$|##')
        self.pr_flag('##|$*$|\\$*$\\##/$*$/|$*$|##')
        self.pr_flag('##|$$$|#\\$$$\\/$$$/#|$$$|##')
        self.pr_flag('##|$*$|##\\$*$$*$/##|$*$|##')
        self.pr_flag('##|$$$|###\\$$$$/###|$$$|##')
        self.pr_flag('##|$*$|####\\$$/####|$*$|##')
        self.pr_flag('##|$$$|#####\\/#####|$$$|##')
        self.pr_flag('#|$$*$$|##########|$$*$$|#')
        self.pr_flag('#|$$$$$|##########|$$$$$|#')
        self.pr_flag('##########################')
        self.d.wait_beats(5)
        d.newline(3)