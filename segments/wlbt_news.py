################################################################################
#
#  WLBT News
#
#  Fetches local news stories from WLBT-3's (Jackson, MS) RSS feed
#
#   - Initialization parameters:
#
#       refresh     Minutes to wait between fetches (default=30)
#
#   - Format parameters:
#
#       items       Number of stories to show (default=3)
#
################################################################################

import datetime as dt
import xml.etree.ElementTree as ET
import urllib.request
from segment_parent import SegmentParent

INTRO = 'News from WLBT-3'
URL = 'https://www.wlbt.com/arc/outboundfeeds/rss/category/news/?outputType=xml'

MAGENTA = '\033[35m'

class Segment(SegmentParent):

    def __init__(self, display, init):
        super().__init__(display, init, default_refresh=30, default_intro=INTRO)

    def refresh_data(self):
        self.data = {'fetched_on': dt.datetime.now(),
                     'items': [],
                     'item_index': 0}
        try:
            req = urllib.request.Request(URL, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as response:
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
        except Exception as e:
            self.data['items'].append({
                'headline': '*** WLBT Feed Unavailable ***',
                'description': ''
            })

    def show(self, fmt):
        num_items = fmt.get('items', 3)

        if self.data_is_stale():
            self.d.set_color('\033[32m')
            self.d.print_update_msg('Getting WLBT-3 News')
            self.refresh_data()
            self.d.newline()
            self.d.newline()
            self.d.newline()

        self.d.set_color(MAGENTA)
        self.d.print_header('WLBT-3 News', '!')
        self.d.newline()

        if not self.data['items']:
            self.d.print('No stories available.')
            return

        for i in range(num_items):
            item = self.data['items'][self.data['item_index']]
            self.d.set_color(MAGENTA)
            self.d.print('-' * self.d.width)
            self.d.newline()
            self.d.print(item['headline'])
            self.d.newline()
            if item['description']:
                self.d.print(item['description'])
            self.d.newline(self.d.beat_delay)
            self.d.newline()
            self.data['item_index'] += 1
            if self.data['item_index'] >= len(self.data['items']):
                self.data['item_index'] = 0
