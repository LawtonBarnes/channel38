################################################################################
#
#  Ole Miss Football News
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

INTRO = 'Ole Miss Headlines from olemisssports.com'
RSS_URL = 'https://news.google.com/rss/search?q=Ole+Miss+football&hl=en-US&gl=US&ceid=US:en'

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
                    src_tag = item.find('source')
                    source = src_tag.text.strip() if src_tag is not None and src_tag.text else ''
                    # Strip publisher name from end of headline
                    if source and title.endswith(' - ' + source):
                        title = title[: -(len(source) + 3)]
                    self.data['items'].append({
                        'headline': self.d.clean_chars(title),
                        'description': self.d.clean_chars(source)
                    })
        except Exception:
            self.data['items'].append({
                'headline': '*** Ole Miss Feed Unavailable ***',
                'description': ''
            })

    def show(self, fmt):
        num_items = fmt.get('items', 5)

        if self.data_is_stale():
            self.d.set_color('\033[32m')
            self.d.print_update_msg('Getting Ole Miss Headlines')
            self.refresh_data()
            self.d.newline()
            self.d.newline()
            self.d.newline()

        self.d.set_color('\033[31m')
        self.d.print_header('Ole Miss Headlines', '!')
        self.d.newline()

        if not self.data['items']:
            self.d.print('No stories available.')
            return

        for item in self.data['items'][:num_items]:
            self.d.newline(self.d.beat_delay)
            self.d.print(item['headline'])
            if item['description']:
                self.d.set_color('\033[34m')
                self.d.print('-- ' + item['description'])
                self.d.set_color('\033[31m')
