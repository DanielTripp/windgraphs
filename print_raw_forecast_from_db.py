#!/usr/bin/env python

import sys
from dtpythonutil.misc import *
import windgraphs

if __name__ == '__main__':

	if len(sys.argv) != 3:
		print 'This program needs two arguments: 1) a raw weather channel, and 2) a date/time.'
		sys.exit(1)
	else:
		weather_channel = sys.argv[1]
		datestr = sys.argv[2]
		windgraphs.print_raw_forecast_from_db(weather_channel, datestr)

