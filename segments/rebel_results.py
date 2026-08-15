################################################################################
#
#  Rebel Results
#
#  Pulls Ole Miss results from the last 7 days across every sport, using
#  the official Ole Miss Athletics calendar RSS feed. Includes all events,
#  not just ones with a clean Win/Loss result (golf, track, etc.).
#
#   - Initialization parameters:
#
#       refresh     Minutes to wait between fetches (default=60)
#
################################################################################

import datetime as dt
import re
import urllib.request
import xml.etree.ElementTree as ET
from segment_parent import SegmentParent

INTRO = 'Rebel Results - Last 7 Days, All Sports'

RSS_URL = 'https://olemisssports.com/calendar.ashx/calendar.rss'

RED    = '\033[31m'
GREEN  = '\033[32m'
WHITE  = '\033[37m'
YELLOW = '\033[33m'
BLUE   = '\033[34m'

NS = {'ev': 'http://purl.org/rss/1.0/modules/event/'}


class Segment(SegmentParent):

    def __init__(self, display, init):
        super().__init__(display, init, default_refresh=60, default_intro=INTRO)

    def parse_date(self, date_str):
        date_str = date_str.strip()
        if 'T' in date_str:
            return dt.datetime.strptime(date_str[:19], '%Y-%m-%dT%H:%M:%S')
        else:
            return dt.datetime.strptime(date_str, '%Y-%m-%d')

    def refresh_data(self):
        self.data = {'fetched_on': dt.datetime.now(), 'results': []}
        cutoff = dt.datetime.utcnow() - dt.timedelta(days=7)

        try:
            req = urllib.request.Request(RSS_URL, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as r:
                text = r.read()
            root = ET.fromstring(text)

            for item in root.iter('item'):
                title = item.findtext('title', '').strip()
                desc = item.findtext('description', '')

                date_el = item.find('ev:startdate', NS)
                if date_el is None or not date_el.text:
                    continue
                try:
                    event_date = self.parse_date(date_el.text)
                except Exception:
                    continue
                if event_date < cutoff or event_date > dt.datetime.utcnow():
                    continue

                # Pull the [W]/[L]/[N] tag if present (not all events have one)
                m = re.match(r'\[(\w+)\]\s*(.*)', title)
                if m:
                    tag, rest = m.group(1), m.group(2)
                else:
                    tag, rest = None, title

                if rest.startswith('Ole Miss '):
                    rest = rest[len('Ole Miss '):]
                if ' vs ' in rest:
                    sport, opponent = rest.split(' vs ', 1)
                    side = 'VS'
                elif ' at ' in rest:
                    sport, opponent = rest.split(' at ', 1)
                    side = 'AT'
                else:
                    sport, opponent, side = rest, '', ''

                # Pull a couple of detail lines from the description, skipping
                # the title repeat (first line) and the trailing link line
                detail_lines = []
                for line in desc.split('\\n')[1:]:
                    line = line.strip()
                    if not line or line.startswith('http'):
                        continue
                    detail_lines.append(self.d.clean_chars(line))
                    if len(detail_lines) == 2:
                        break

                header = f"{sport.strip().upper()}"
                if side:
                    header += f" {side} {self.d.clean_chars(opponent.strip())}"

                self.data['results'].append({
                    'date': event_date,
                    'header': header,
                    'tag': tag,
                    'lines': detail_lines,
                })
        except Exception:
            pass

        self.data['results'].sort(key=lambda r: r['date'])

    def show(self, fmt):
        if self.data_is_stale():
            self.d.set_color(GREEN)
            self.d.print_update_msg('Getting Rebel Results')
            self.refresh_data()
            self.d.newline()
            self.d.newline()
            self.d.newline()

        for title in (' REBEL RESULTS ', ' LAST 7 DAYS '):
            num_stars = (self.d.width - len(title)) // 2
            self.d.set_color(BLUE)
            self.d.print('*' * num_stars, end='')
            self.d.set_color(RED)
            self.d.print(title, end='')
            self.d.set_color(BLUE)
            self.d.print('*' * num_stars)
        self.d.newline()

        if not self.data['results']:
            self.d.set_color(WHITE)
            self.d.print('No results in the last 7 days.')
            return

        for game in self.data['results']:
            self.d.newline(self.d.beat_delay)

            self.d.set_color(WHITE)
            self.d.print(game['header'])

            if game['tag'] == 'W':
                self.d.set_color(GREEN)
            elif game['tag'] == 'L':
                self.d.set_color(RED)
            else:
                self.d.set_color(YELLOW)

            for line in game['lines']:
                self.d.print(line)

            self.d.set_color(RED)
            self.d.print(game['date'].strftime('%b %d').upper())