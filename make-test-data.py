#!/usr/bin/env python

import sys, pprint
from dtpythonutil.misc import *
import c

if __name__ == '__main__':

	print "delete from wind_observations_parsed where time_retrieved < str_to_em('1981');"
	print "delete from wind_forecasts_parsed where time_retrieved < str_to_em('1981');"

	if 1:
		for day in xrange(1, 30):
			wind = max(0, get_range_val((16,0), (17,1), day))
			print "insert into wind_observations_parsed values ('gc.ca', str_to_em('1980-01-%02d 08:00:00'), '1980-01-%02d 08:00:00', %d, -1);" \
					% (day, day, wind)

	if 1:
		for day in xrange(1, 30):
			for channel in c.FORECAST_PARSED_CHANNELS:
				time_retrieved_str = '1980-01-%02d 06:00:00' % day
				target_time_str = '1980-01-%02d 08:00:00' % day
				obs_wind = max(0, get_range_val((16,0), (17,1), day))
				num_forecast_winds = max(1, get_range_val((16,1), (17,2), day))
				forecast_winds = [obs_wind+x for x in xrange(num_forecast_winds)]
				forecast_wind = forecast_winds[c.FORECAST_PARSED_CHANNELS.index(channel) % len(forecast_winds)]
				print "insert into wind_forecasts_parsed values (%10s, %d, '%s', %d, '%s', %d, -1);" % \
						("'%s'" % channel, str_to_em(time_retrieved_str), time_retrieved_str, str_to_em(target_time_str), target_time_str, 
								forecast_wind)



