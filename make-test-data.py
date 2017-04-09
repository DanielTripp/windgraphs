#!/usr/bin/env python

import sys, pprint
from dtpythonutil.misc import *
import windgraphs

if __name__ == '__main__':

	if 0:
		for day in xrange(1, 30):
			print "insert into wind_observations_parsed values ('gc.ca', str_to_em('1980-01-%02d 08:00:00'), '1980-01-%02d 08:00:00', 10, -1);" % (day, day)

	if 1:
		for day in xrange(1, 30):
			for channel in windgraphs.PARSED_WEATHER_CHANNELS:
				time_retrieved_str = '1980-01-%02d 06:00:00' % day
				target_time_str = '1980-01-%02d 08:00:00' % day
				print "insert into wind_forecasts_parsed values (%10s, %d, '%s', %d, '%s', 10, -1);" % \
						("'%s'" % channel, str_to_em(time_retrieved_str), time_retrieved_str, str_to_em(target_time_str), target_time_str)



