################################################################################
#
#  Around the SEC
#
#  Pulls SEC football scores from the last 7 days from ESPN's scoreboard API
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

URL = 'https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard?groups=8&dates={dates}'

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
            today = dt.datetime.utcnow()
            start = today - dt.timedelta(days=7)
            date_range = f"{start.strftime('%Y%m%d')}-{today.strftime('%Y%m%d')}"
            # No custom User-Agent here on purpose -- ESPN's Akamai WAF 403s
            # on a spoofed browser string (or a blank one), but lets through
            # urllib's own default identifier. Confirmed by hand: 'Mozilla/5.0'
            # -> 403, no header at all -> 200, same URL either way.
            req = urllib.request.Request(URL.format(dates=date_range))
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.loads(r.read())

            for event in data.get('events', []):
                status = event['status']['type']
                state = status['state']
                # Only actual scores -- not-yet-started games are the
                # full-season schedule segment's job, not this one's.
                if state not in ('in', 'post'):
                    continue

                comp = event['competitions'][0]
                competitors = comp['competitors']
                home = next(c for c in competitors if c['homeAway'] == 'home')
                away = next(c for c in competitors if c['homeAway'] == 'away')

                if state == 'post':
                    game_status = 'FINAL'
                elif 'HALFTIME' in status.get('name', ''):
                    game_status = 'HALF'
                else:
                    period = event['status'].get('period', 0)
                    clock = event['status'].get('displayClock', '')
                    if period and period > 4:
                        qtr = 'OT' if period == 5 else f'{period - 4}OT'
                    else:
                        qtr = f'Q{period}' if period else ''
                    game_status = f'{clock} {qtr}'.strip()

                event_date = dt.datetime.strptime(event['date'], '%Y-%m-%dT%H:%MZ')

                self.data['games'].append({
                    'date': event_date,
                    'matchup': self.d.clean_chars(event.get('shortName', '')),
                    'away_score': away.get('score', '0'),
                    'home_score': home.get('score', '0'),
                    'status': game_status,
                    'live': state == 'in'
                })

            self.data['games'].sort(key=lambda g: g['date'])
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
            self.d.print('No SEC games in the last 7 days.')
            return

        for game in self.data['games']:

            score = f"{game['away_score']}-{game['home_score']}"
            status_color = MAGENTA if game['live'] else GREEN

            self.d.set_color(WHITE)
            self.d.print(game['matchup'] + ' ', end='')
            self.d.set_color(YELLOW)
            self.d.print(score + ' ', end='')
            self.d.set_color(status_color)
            self.d.print(game['status'])
            self.d.newline(self.d.beat_delay)