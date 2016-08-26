#!/usr/bin/env python

import sys
import windgraphs

if __name__ == '__main__':

	weather_channel = sys.argv[1]
	datestr = sys.argv[2]
	windgraphs.backfill_reparse_raw_forecast_in_db(weather_channel, datestr)

