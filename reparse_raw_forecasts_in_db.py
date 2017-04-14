#!/usr/bin/env python

import sys
import windgraphs
from dtpythonutil.misc import *

if __name__ == '__main__':

	weather_channel = sys.argv[1]
	if len(sys.argv) in (3, 4):
		start_date_incl = str_to_em(sys.argv[2])
		end_date_excl = str_to_em(sys.argv[3]) if len(sys.argv) == 4 else now_em()
		windgraphs.reparse_raw_forecasts_in_db(weather_channel, start_date_incl, end_date_excl)
	else:
		raise Exception()

