################################################################################
#
#  Around the SEC
#
#  Pulls SEC football scores from the last 6 days from ESPN's scoreboard API.
#  Refetched every time this segment comes up in the playlist rotation
#  (not on a fixed timer) -- one lightweight JSON request per lap through
#  the playlist is nowhere near enough to trip any bot-detection on a
#  public scoreboard endpoint, and it keeps scores current whatever the
#  actual lap time ends up being.
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
        super().__init__(display, init, default_intro=INTRO)

    def refresh_data(self):
        self.data = {'fetched_on': dt.datetime.now(),
                     'games': []}
        try:
            today = dt.datetime.utcnow()
            # 6 days, not 7 -- a full week reaches back to last Saturday's
            # games too, which reads as confusing/stale on a Saturday when
            # this week's games are also underway.
            start = today - dt.timedelta(days=6)
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
                    'away_name': self.d.clean_chars(away['team']['location']),
                    'away_score': away.get('score', '0'),
                    'home_name': self.d.clean_chars(home['team']['location']),
                    'home_score': home.get('score', '0'),
                    'status': game_status,
                    'live': state == 'in'
                })

            self.data['games'].sort(key=lambda g: g['date'])
        except Exception as e:
            self.data['games'] = []

    def show(self, fmt):
        # Refreshed unconditionally every time this segment airs, rather
        # than gated on data_is_stale()'s timer, so it's always showing
        # this lap's scores instead of whatever was cached up to 15
        # minutes ago.
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
            self.d.print('No SEC games in the last 6 days.')
            return

        # Name field is 21 chars wide (was 18) -- rjust naturally shifts
        # shorter names further right within it, and the wider field also
        # allows 3 more characters of name before truncation. Away name
        # and "@ " + home name both fill this same 21-wide field, so the
        # single space before the yellow score lands on the same column
        # for every row.
        NAME_W = 21

        for game in self.data['games']:

            away = game['away_name'][:NAME_W]
            home = game['home_name'][:NAME_W - 2]
            status_color = MAGENTA if game['live'] else GREEN

            self.d.set_color(WHITE)
            self.d.print(f"{away:>{NAME_W}}", end='')
            self.d.set_color(YELLOW)
            self.d.print(' ' + game['away_score'])

            self.d.set_color(WHITE)
            self.d.print(f"{'@ ' + home:>{NAME_W}}", end='')
            self.d.set_color(YELLOW)
            self.d.print(' ' + game['home_score'])

            # Right-justified under the team names (not centered, and no
            # date) -- just FINAL or the live clock/quarter.
            self.d.set_color(status_color)
            self.d.print(game['status'].rjust(NAME_W))
            self.d.newline()
            self.d.wait_beats(1)