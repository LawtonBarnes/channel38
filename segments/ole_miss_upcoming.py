################################################################################
#
#  Ole Miss Football Schedule
#
#  Parses the Ole Miss football schedule from Google Calendar ICS feed
#
#   - Initialization parameters:
#
#       refresh     Minutes to wait between fetches (default=360)
#
#   - Format parameters:
#
#       games       Number of upcoming games to show (default=3)
#
################################################################################

import datetime as dt
import urllib.request
from segment_parent import SegmentParent

INTRO = 'Ole Miss Football Schedule from olemisssports.com'
ICS_URL = 'https://calendar.google.com/calendar/ical/qg6rtkdc9sb10t9arcesecj48k6jhtoi%40import.calendar.google.com/public/basic.ics'

class Segment(SegmentParent):

    def __init__(self, display, init):
        super().__init__(display, init, default_refresh=360, default_intro=INTRO)

    def parse_date(self, dtstart):
        # Handle both date-only and datetime formats
        dtstart = dtstart.strip()
        if 'T' in dtstart:
            # Full datetime in UTC e.g. 20260906T233000Z
            return dt.datetime.strptime(dtstart, '%Y%m%dT%H%M%SZ').replace(tzinfo=dt.timezone.utc).astimezone().date()
        else:
            # Date only e.g. 20261017
            return dt.datetime.strptime(dtstart, '%Y%m%d').date()

    def parse_ics(self, text):
        games = []
        events = text.split('BEGIN:VEVENT')
        for event in events[1:]:
            game = {}
            for line in event.splitlines():
                line = line.strip()
                if line.startswith('DTSTART'):
                    val = line.split(':', 1)[1] if ':' in line else ''
                    # Handle DTSTART;VALUE=DATE:20261017
                    if ';' in line:
                        val = line.split(':', 1)[1]
                    try:
                        game['date'] = self.parse_date(val)
                    except:
                        pass
                elif line.startswith('SUMMARY:'):
                    game['summary'] = line[8:].strip()
                elif line.startswith('LOCATION:'):
                    game['location'] = line[9:].replace('\\,', ',').strip()
                elif line.startswith('DESCRIPTION:'):
                    game['description'] = line[12:].strip()
            if 'date' in game and 'summary' in game:
                games.append(game)
        # Sort by date
        games.sort(key=lambda g: g['date'])
        return games

    def parse_game(self, game):
        summary = game['summary']
        # Strip "Ole Miss Football " prefix
        summary = summary.replace('Ole Miss Football ', '')
        # Determine home vs away
        if summary.startswith('vs '):
            home_away = 'HOME'
            opponent = summary[3:]
        elif summary.startswith('at '):
            home_away = 'AWAY'
            opponent = summary[3:]
        else:
            home_away = ''
            opponent = summary
        # Strip wear/theme info after dash
        if '-' in opponent:
            opponent = opponent.split('-')[0].strip()
        # Extract TV info from description
        tv = ''
        desc = game.get('description', '')
        if 'TV:' in desc:
            tv_part = desc.split('TV:')[1]
            tv = tv_part.split('\\n')[0].strip()
        return {
            'date': game['date'],
            'opponent': opponent,
            'home_away': home_away,
            'location': game.get('location', ''),
            'tv': tv
        }

    def refresh_data(self):
        self.data = {'fetched_on': dt.datetime.now(),
                     'games': []}
        try:
            req = urllib.request.Request(ICS_URL, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as r:
                text = r.read().decode('utf-8')
            raw_games = self.parse_ics(text)
            self.data['games'] = [self.parse_game(g) for g in raw_games]
        except Exception as e:
            pass

    def show(self, fmt):
        num_games = fmt.get('games', 3)

        if self.data_is_stale():
            self.d.set_color('\033[32m')
            self.d.print_update_msg('Getting Ole Miss Schedule')
            self.refresh_data()
            self.d.newline()
            self.d.newline()
            self.d.newline()

        self.d.set_color('\033[31m')
        self.d.print_header('Ole Miss Schedule', '!')
        self.d.newline()

        if not self.data['games']:
            self.d.print('Schedule unavailable.')
            return

        today = dt.date.today()
        upcoming = [g for g in self.data['games'] if g['date'] >= today]
        past = [g for g in self.data['games'] if g['date'] < today]

        # Show next upcoming games
        if upcoming:
            self.d.set_color('\033[33m')
            self.d.print('Upcoming Games:')
            self.d.newline()
            for game in upcoming[:num_games]:
                days_away = (game['date'] - today).days
                self.d.set_color('\033[36m')
                date_str = game['date'].strftime('%a %b %d')
                self.d.print(f"{date_str}")
                self.d.set_color('\033[31m')
                self.d.print(f"{game['home_away']} vs {game['opponent']}")
                self.d.set_color('\033[37m')
                self.d.print(f"{game['location']}")
                if game['tv']:
                    self.d.print(f"TV: {game['tv']}")
                if days_away == 0:
                    self.d.print('*** TODAY ***')
                elif days_away == 1:
                    self.d.print('Tomorrow!')
                else:
                    self.d.print(f"{days_away} days away")
                self.d.newline(self.d.beat_delay)
                self.d.set_color('\033[34m')
                self.d.print('=' * self.d.width)
                self.d.newline()
        else:
            self.d.print('Season complete!')
