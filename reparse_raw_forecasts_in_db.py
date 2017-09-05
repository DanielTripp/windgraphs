#!/usr/bin/env python

import sys
import windgraphs
from dtpythonutil.misc import *

if __name__ == '__main__':

	if len(sys.argv) not in (3, 4):
		print 'This program needs either 2 or 3 arguments:'
		print '1) a raw weather channel, 2) a start date/time, and 3) (optional) an end date/time (defaults to the current date/time).'
		sys.exit(1)
	else:
		weather_channel = sys.argv[1]
		start_date_incl = str_to_em(sys.argv[2])
		end_date_excl = str_to_em(sys.argv[3]) if len(sys.argv) == 4 else now_em()
		windgraphs.reparse_raw_forecasts_in_db(weather_channel, start_date_incl, end_date_excl)

