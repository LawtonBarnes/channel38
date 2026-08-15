################################################################################
#
#   CFP Top 25
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

INTRO = 'College Football Top 25 from Google News'
RSS_URL = 'https://news.google.com/rss/search?q=college+football+top+25+rankings&hl=en-US&gl=US&ceid=US:en'

PRIMARY   = '\033[33m'  # yellow
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
                'headline': '*** CFP Top 25 Feed Unavailable ***',
                'description': ''
            })

    def show(self, fmt):
        num_items = fmt.get('items', 5)

        if self.data_is_stale():
            self.d.print_update_msg('Getting CFP Top 25')
            self.refresh_data()

        self.d.set_color(PRIMARY)
        self.d.print_header('CFP Top 25', '!')
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

