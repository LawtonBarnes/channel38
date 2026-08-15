################################################################################
#
#  Ole Miss Rebels News
#
#  Fetches latest Ole Miss football headlines from the
#  Ole Miss Athletics RSS feed.
#
#   - Initialization parameters:
#
#       refresh     Minutes to wait between fetches (default=60)
#
#   - Format parameters:
#
#       items       Number of headlines to show (default=5)
#
################################################################################

import datetime as dt
import xml.etree.ElementTree as ET
import urllib.request
from segment_parent import SegmentParent

INTRO = 'Ole Miss Rebels news from Google News'
RSS_URL = 'https://news.google.com/rss/search?q=Ole+Miss+Rebels&hl=en-US&gl=US&ceid=US:en'

PRIMARY   = '\033[32m'  # green
SECONDARY = '\033[37m'  # white

class Segment(SegmentParent):

    def __init__(self, display, init):
        super().__init__(display, init, default_refresh=60, default_intro=INTRO)

    def refresh_data(self):
        self.data = {'fetched_on': dt.datetime.now(),
                     'items': []}
        try:
            with urllib.request.urlopen(RSS_URL, timeout=10) as response:
                xml_data = response.read()
            root = ET.fromstring(xml_data)
            channel = root.find('channel')
            if channel is None:
                return
            for item in channel.findall('item'):
                title = item.findtext('title', '').strip()
                desc = item.findtext('description', '').strip()
                if title:
                    self.data['items'].append({
                        'headline': self.d.clean_chars(title),
                        'description': self.d.clean_chars(desc)
                    })
        except Exception:
            self.data['items'].append({
                'headline': '*** Ole Miss Rebel Feed Unavailable ***',
                'description': ''
            })

    def show(self, fmt):
        num_items = fmt.get('items', 5)

        if self.data_is_stale():
            self.d.print_update_msg('Getting Ole Miss Rebels News')
            self.refresh_data()
            self.d.newline()
            self.d.newline()
            self.d.newline()

        self.d.set_color(PRIMARY)
        self.d.print_header('Rebel Headlines', '!')
        self.d.newline()

        if not self.data['items']:
            self.d.print('No stories available.')
            return

        for item in self.data['items'][:num_items]:
            self.d.newline(self.d.beat_delay)
            parts = item['headline'].rsplit(' - ', 1)
            self.d.set_color(PRIMARY)
            self.d.print(parts[0])
            if len(parts) == 2:
                self.d.set_color(SECONDARY)
                self.d.print('-- ' + parts[1])

