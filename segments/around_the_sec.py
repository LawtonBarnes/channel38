################################################################################
#
#  Around the SEC
#
#  Pulls current SEC football scores from ESPN's scoreboard API
#
#   - Initialization parameters:
#
#       refresh     Minutes to wait between fetches (default=15)
#
################################################################################

import datetime as dt
import json
import urllib.request
from segment_parent import SegmentParent

INTRO = 'Around the SEC - Live Scores from ESPN'

URL = 'https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard?groups=8'

GREEN = '\033[32m'
WHITE = '\033[37m'
MAGENTA = '\033[35m'
YELLOW  = '\033[33m'
BLUE    = '\033[34m'


class Segment(SegmentParent):

    def __init__(self, display, init):
        super().__init__(display, init, default_refresh=15, default_intro=INTRO)

    def refresh_data(self):
        self.data = {'fetched_on': dt.datetime.now(),
                     'games': []}
        try:
            req = urllib.request.Request(URL, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.loads(r.read())

            for event in data.get('events', []):
                comp = event['competitions'][0]
                competitors = comp['competitors']
                home = next(c for c in competitors if c['homeAway'] == 'home')
                away = next(c for c in competitors if c['homeAway'] == 'away')

                status = event['status']['type']
                state = status['state']
                if state == 'post':
                    game_status = 'Final'
                elif state == 'in':
                    period = event['status'].get('period', '')
                    clock = event['status'].get('displayClock', '')
                    game_status = f"Q{period} {clock}"
                else:
                    game_status = status.get('shortDetail', '')

                self.data['games'].append({
                    'away_name': self.d.clean_chars(away['team']['location']),
                    'away_score': away.get('score', '0'),
                    'home_name': self.d.clean_chars(home['team']['location']),
                    'home_score': home.get('score', '0'),
                    'status': game_status
                })
        except Exception as e:
            self.data['games'] = []

    def show(self, fmt):
        if self.data_is_stale():
            self.d.set_color(GREEN)
            self.d.print_update_msg('Getting SEC Scores')
            self.refresh_data()
            self.d.newline()
            self.d.newline()
            self.d.newline()

        self.d.newline()
        title = ' AROUND THE SEC '
        num_dashes = (self.d.width - len(title)) // 2
        self.d.set_color(WHITE)
        self.d.print('-' * num_dashes, end='')
        self.d.set_color(GREEN)
        self.d.print(title, end='')
        self.d.set_color(WHITE)
        self.d.print('-' * num_dashes)
        self.d.newline()

        if not self.data['games']:
            self.d.set_color(GREEN)
            self.d.print('No SEC games in progress.')
            return

        for game in self.data['games']:

            away = game['away_name'][:18]
            home = game['home_name'][:16]

            self.d.set_color(WHITE)
            self.d.print(f"{away:>18}", end='')
            self.d.set_color(YELLOW)
            self.d.print(' ' + game['away_score'])

            self.d.set_color(WHITE)
            self.d.print(f"{'@ ' + home:>18}", end='')
            self.d.set_color(YELLOW)
            self.d.print(' ' + game['home_score'])

            self.d.set_color(GREEN)
            self.d.print(game['status'].center(self.d.width))
            self.d.newline()
            self.d.wait_beats(1)