################################################################################
#
#  New York Times News
#
#  Fetches latest NYT stories from NYT RSS feed.
#
#   - Initialization parameters:
#
#       refresh     Minutes to wait between fetches (default=30)
#       url         RSS feed URL (default=HomePage)
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

INTRO = 'News from The New York Times'
DEFAULT_URL = 'https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml'

MAGENTA = '\033[35m'

class Segment(SegmentParent):

    def __init__(self, display, init):
        super().__init__(display, init, default_refresh=30, default_intro=INTRO)
        self.url = init.get('url', DEFAULT_URL)

    def refresh_data(self):
        self.data = {'fetched_on': dt.datetime.now(),
                     'items': [],
                     'item_index': 0}
        try:
            req = urllib.request.Request(self.url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as response:
                xml_data = response.read()
            root = ET.fromstring(xml_data)
            channel = root.find('channel')
            if channel is None:
                return
            for item in channel.findall('item'):
                title = item.findtext('title', '').strip()
                desc = item.findtext('description', '').strip()
                creator = item.findtext('{http://purl.org/dc/elements/1.1/}creator', '').strip()
                if title:
                    self.data['items'].append({
                        'headline': self.d.clean_chars(title),
                        'description': self.d.clean_chars(desc),
                        'author': self.d.clean_chars(creator)
                    })
        except Exception as e:
            self.data['items'].append({
                'headline': '*** NYT Feed Unavailable ***',
                'description': '',
                'author': ''
            })

    def show(self, fmt):
        num_items = fmt.get('items', 3)

        if self.data_is_stale():
            self.d.set_color('\033[32m')
            self.d.print_update_msg('Getting NYT News')
            self.refresh_data()
            self.d.newline()
            self.d.newline()
            self.d.newline()

        self.d.set_color(MAGENTA)
        self.d.print_header('New York Times', '!')
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
