#!/usr/bin/env python

import sys
import windgraphs
from misc import *

if __name__ == '__main__':

	weather_channel = sys.argv[1]
	if len(sys.argv) == 3:
		datestr = sys.argv[2]
		windgraphs.backfill_reparse_raw_forecast_in_db(weather_channel, datestr, True)
	elif len(sys.argv) == 4:
		start_datestr_incl = sys.argv[2]
		end_datestr_incl = sys.argv[3]
		for epoch_time in range(str_to_em(start_datestr_incl), str_to_em(end_datestr_incl), 1000*60*60):
			datestr = em_to_str(epoch_time)
			windgraphs.backfill_reparse_raw_forecast_in_db(weather_channel, datestr, False)
	else:
		raise Exception()

