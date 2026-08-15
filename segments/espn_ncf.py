################################################################################
#
#  ESPN College Football News
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

INTRO = 'College Football news from ESPN'
DEFAULT_URL = 'https://www.espn.com/espn/rss/ncf/news'

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
                'headline': '*** ESPN Feed Unavailable ***',
                'description': '',
                'author': ''
            })

    def show(self, fmt):
        num_items = fmt.get('items', 5)

        if self.data_is_stale():
            self.d.set_color('\033[32m')
            self.d.print_update_msg('Getting ESPN Football')
            self.refresh_data()
            self.d.newline()
            self.d.newline()
            self.d.newline()
            

        self.d.set_color('\033[33m')
        self.d.print_header('ESPN College Football', '!')
        self.d.newline()

        if not self.data['items']:
            self.d.print('No stories available.')
            return

        for item in self.data['items'][:num_items]:
            self.d.newline()
            self.d.set_color('\033[37m')
            self.d.print(item['headline'])
            self.d.set_color('\033[33m')
            if item['description']:
                self.d.newline()
                self.d.print(item['description'])
            self.d.newline(self.d.beat_delay * 2)
            self.d.set_color('\033[33m')
            self.d.print('_' * self.d.width)
            self.d.newline()
