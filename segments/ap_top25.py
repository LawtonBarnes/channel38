################################################################################
#
#  AP Top 25 College Football Rankings
#
#  Scrapes rankings from ncaa.com
#
#   - Initialization parameters:
#
#       refresh     Minutes to wait between fetches (default=360)
#
#   - Format parameters:
#
#       teams       Number of teams to show (default=25)
#
################################################################################

import datetime as dt
import urllib.request
from bs4 import BeautifulSoup
from segment_parent import SegmentParent

INTRO = 'AP Top 25 College Football Rankings from ncaa.com'
URL = 'https://www.ncaa.com/rankings/football/fbs/associated-press'

class Segment(SegmentParent):

    def __init__(self, display, init):
        super().__init__(display, init, default_refresh=360, default_intro=INTRO)

    def refresh_data(self):
        self.data = {'fetched_on': dt.datetime.now(),
                     'rankings': [],
                     'as_of': ''}
        try:
            req = urllib.request.Request(URL, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as r:
                soup = BeautifulSoup(r.read(), 'html.parser')

            # Grab the "through games" date
            through = soup.find(string=lambda t: t and 'Through Games' in t)
            if through:
                self.data['as_of'] = through.strip()

            # Parse the rankings table
            table = soup.find('table')
            if table is None:
                return
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all('td')
                if len(cells) >= 5:
                    rank = cells[0].get_text().strip()
                    school = cells[1].get_text().strip()
                    record = cells[3].get_text().strip()
                    previous = cells[4].get_text().strip()
                    if rank.isdigit():
                        self.data['rankings'].append({
                            'rank': rank,
                            'school': self.d.clean_chars(school),
                            'record': record,
                            'previous': previous
                        })
        except Exception as e:
            self.data['rankings'] = []

    def show(self, fmt):
        num_teams = fmt.get('teams', 25)

        if self.data_is_stale():
            self.d.set_color('\033[32m')
            self.d.print_update_msg('Getting AP Top 25')
            self.refresh_data()
            self.d.newline()
            self.d.newline()
            self.d.newline()

        self.d.set_color('\033[33m')
        self.d.print_header('AP Top 25', '=')
        self.d.set_color('\033[37m')
        self.d.newline()

        if not self.data['rankings']:
            self.d.print('Rankings unavailable.')
            return

        if self.data['as_of']:
            self.d.print(self.data['as_of'])
            self.d.newline()

        for team in self.data['rankings'][:num_teams]:
            self.d.newline(self.d.beat_delay)
            is_ole_miss = 'OLE MISS' in team['school'].upper()
            self.d.set_color('\033[36m' if is_ole_miss else '\033[37m')
            self.d.print(f"{team['rank']:>2}. {team['school']}", end='')
            self.d.set_color('\033[33m')
            self.d.print(f" ({team['record']})")
