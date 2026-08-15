################################################################################
#
#  Ole Miss Football Full Season Schedule
#
#  Parses the Ole Miss football schedule from Google Calendar ICS feed
#
#   - Initialization parameters:
#
#       refresh     Minutes to wait between fetches (default=360)
#
#   - Format parameters:  none
#
################################################################################

import datetime as dt
import urllib.request
from segment_parent import SegmentParent

INTRO = 'Ole Miss Football Schedule from olemisssports.com'
ICS_URL = 'https://calendar.google.com/calendar/ical/qg6rtkdc9sb10t9arcesecj48k6jhtoi%40import.calendar.google.com/public/basic.ics'

RED    = '\033[31m'
WHITE  = '\033[37m'
BLUE   = '\033[34m'
CYAN   = '\033[36m'
GREEN  = '\033[32m'

class Segment(SegmentParent):

    def __init__(self, display, init):
        super().__init__(display, init, default_refresh=360, default_intro=INTRO)

    def parse_date_and_time(self, line):
        val = line.split(':', 1)[1] if ':' in line else ''
        if ';' in line:
            val = line.split(':', 1)[1]
        val = val.strip()
        if 'T' in val:
            d = dt.datetime.strptime(val, '%Y%m%dT%H%M%SZ').replace(tzinfo=dt.timezone.utc).astimezone()
            return d.date(), d.strftime('%H:%M')
        else:
            return dt.datetime.strptime(val, '%Y%m%d').date(), None

    def parse_ics(self, text):
        games = []
        events = text.split('BEGIN:VEVENT')
        for event in events[1:]:
            game = {}
            for line in event.splitlines():
                line = line.strip()
                if line.startswith('DTSTART'):
                    try:
                        date, time = self.parse_date_and_time(line)
                        game['date'] = date
                        game['time'] = time
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
        games.sort(key=lambda g: g['date'])
        return games

    def parse_game(self, game):
        summary = game['summary']
        summary = summary.replace('Ole Miss Football ', '')
        if summary.startswith('vs '):
            home_away = 'home'
            opponent = summary[3:]
        elif summary.startswith('at '):
            home_away = 'away'
            opponent = summary[3:]
        else:
            home_away = 'home'
            opponent = summary
        if '-' in opponent:
            opponent = opponent.split('-')[0].strip()
        tv = ''
        wear = ''
        desc = game.get('description', '')
        if 'TV:' in desc:
            tv_part = desc.split('TV:')[1]
            tv = tv_part.split('\\n')[0].strip()[:3]
        full_summary = game['summary']
        if 'Wear ' in full_summary:
            wear_part = full_summary.split('Wear ')[1]
            wear = wear_part.split('-')[0].strip()
        elif 'Stripe Out' in full_summary:
            wear = 'Stripe Out'
        return {
            'date': game['date'],
            'time': game.get('time'),
            'opponent': opponent,
            'home_away': home_away,
            'location': game.get('location', ''),
            'tv': tv,
            'wear': wear
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

    def format_line(self, game):
        # Date: MMM DD = 6 chars
        date_str = game['date'].strftime('%b %d').upper()

        # Opponent: @ prefix if away, padded/truncated to 8 chars
        if game['home_away'] == 'away':
            opp = ('@ ' + game['opponent'])[:8]
        else:
            opp = game['opponent'][:8]
        opp = opp.ljust(8)

        # Time: 5 chars right-aligned, blank if no time
        if game['time']:
            h, m = game['time'].split(':')
            h = int(h)
            if h >= 12:
                h -= 12
            if h == 0:
                h = 12
            time_str = f'{h}:{m}'.rjust(5)
        else:
            time_str = '     '

        # TV: 3 chars
        tv = game['tv'][:3].ljust(3) if game['tv'] else 'TBA'

        return date_str, time_str, opp, tv

    def show(self, fmt):
        if self.data_is_stale():
            self.d.set_color(GREEN)
            self.d.print_update_msg('Getting Ole Miss Schedule')
            self.refresh_data()
            self.d.newline()
            self.d.newline()
            self.d.newline()

        today = dt.date.today()
        year = today.year

        # Header with red stars
        header = f' {year} OLE MISS '
        num_stars = (self.d.width - len(header)) // 2
        self.d.set_color(RED)
        self.d.print('*' * num_stars, end='')
        self.d.set_color(WHITE)
        self.d.print(header, end='')
        self.d.set_color(RED)
        self.d.print('*' * num_stars)
        self.d.newline()

        if not self.data['games']:
            self.d.print('Schedule unavailable.')
            return

        # Find next game wear info
        upcoming = [g for g in self.data['games'] if g['date'] >= today]
        next_wear = upcoming[0]['wear'] if upcoming else ''

        # Print each game
        for game in self.data['games']:
            date_str, time_str, opp, tv = self.format_line(game)
            self.d.set_color(RED)
            self.d.print(date_str + ' ', end='')
            self.d.set_color(WHITE)
            self.d.print(opp + ' ', end='')
            self.d.set_color(CYAN)
            self.d.print(time_str + ' ', end='')
            self.d.print(tv)
            self.d.newline(self.d.beat_delay)

        # Next game wear line
        self.d.newline()
        if next_wear:
            wear_lower = next_wear.lower()
            if next_wear == 'Stripe Out':
                words  = ['NEXT', 'GAME', 'STRIPE', 'OUT']
                colors = [RED,    CYAN,   RED,      CYAN]
                padding = (self.d.width - len('NEXT GAME STRIPE OUT')) // 2
                self.d.print(' ' * padding, end='')
                for i, (word, color) in enumerate(zip(words, colors)):
                    self.d.set_color(color)
                    if i < len(words) - 1:
                        self.d.print(word + ' ', end='')
                    else:
                        self.d.print(word)
            else:
                if 'powder' in wear_lower:
                    wear_color = CYAN
                elif 'red' in wear_lower:
                    wear_color = RED
                elif 'white' in wear_lower:
                    wear_color = WHITE
                elif 'blue' in wear_lower:
                    wear_color = BLUE
                else:
                    wear_color = CYAN
                wear_text = f'NEXT GAME: WEAR {next_wear.upper()}'
                padding = (self.d.width - len(wear_text)) // 2
                self.d.set_color(wear_color)
                self.d.print(' ' * padding + wear_text)

        # Footer stars
        self.d.newline()
        self.d.set_color(RED)
        self.d.print('*' * self.d.width)
