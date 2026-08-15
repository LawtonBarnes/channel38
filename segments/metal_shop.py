################################################################################
#
#  Metal Shop
#
#  Simple shout-out segment for the Metal Shop
#
################################################################################

import datetime as dt
from segment_parent import SegmentParent

INTRO = ''

YELLOW = '\033[33m'

class Segment(SegmentParent):

    def __init__(self, display, init):
        super().__init__(display, init, default_refresh=99999, default_intro=INTRO)

    def refresh_data(self):
        self.data = {'fetched_on': dt.datetime.now()}

    def show(self, fmt):
        if self.data_is_stale():
            self.refresh_data()
        d = self.d
        d.set_color(YELLOW)
        d.newline()
        d.newline()
        d.print('CHANNEL 38 IS A'.center(d.width))
        d.print('METAL SHOP PRODUCTION'.center(d.width))
        d.newline()
        d.print('KEEP ON ROCKIN LIKE DOKKEN'.center(d.width))
        d.newline()
        d.newline()
        d.newline()
        d.newline()
        d.newline(3)