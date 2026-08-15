################################################################################
#
#  Current Conditions - Oxford, MS
#
#  Pulls current weather conditions from the National Weather Service (NOAA)
#  for Oxford, MS and displays a one-line summary.
#
#   - Initialization parameters:
#
#       refresh     Minutes to wait between fetches (default=60)
#
################################################################################

import datetime as dt
import json
import urllib.request
from segment_parent import SegmentParent

INTRO = 'Current Conditions in Oxford, MS from NOAA'

LAT = 34.3665
LON = -89.5192

GREEN = '\033[32m'
CYAN  = '\033[36m'

# NWS API requires a User-Agent identifying the app/contact - replace email
HEADERS = {'User-Agent': '(retrofeed, lawton@lawtonbarnes.com)'}


class Segment(SegmentParent):

    def __init__(self, display, init):
        super().__init__(display, init, default_refresh=60, default_intro=INTRO)

    def refresh_data(self):
        self.data = {'fetched_on': dt.datetime.now(),
                     'temp': None,
                     'forecast': '',
                     'pop': None}
        try:
            # Step 1: look up the gridpoint forecast URL for this lat/lon
            points_url = f'https://api.weather.gov/points/{LAT},{LON}'
            req = urllib.request.Request(points_url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=10) as r:
                points_data = json.loads(r.read())
            forecast_hourly_url = points_data['properties']['forecastHourly']

            # Step 2: pull the current hourly forecast period
            req = urllib.request.Request(forecast_hourly_url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=10) as r:
                forecast_data = json.loads(r.read())
            period = forecast_data['properties']['periods'][0]

            self.data['temp'] = period.get('temperature')
            self.data['forecast'] = self.d.clean_chars(period.get('shortForecast', ''))
            pop = period.get('probabilityOfPrecipitation', {}).get('value')
            self.data['pop'] = pop
        except Exception as e:
            self.data['temp'] = None

    def show(self, fmt):
        if self.data_is_stale():
            self.d.set_color(GREEN)
            self.d.print_update_msg('Getting Current Conditions')
            self.refresh_data()
            self.d.newline()
            self.d.newline()
            self.d.newline()

        self.d.set_color(CYAN)

        if self.data['temp'] is None:
            self.d.print('Current conditions unavailable.')
            return

        msg = f"Current Conditions in Oxford {self.data['temp']} Deg {self.data['forecast']}"
        if self.data['pop'] is not None:
            msg += f" {self.data['pop']} Pct Chance of Rain"
        self.d.print(msg)