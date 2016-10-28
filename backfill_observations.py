#!/usr/bin/env python

import sys, pprint, datetime
import windgraphs

if __name__ == '__main__':

	def get_prev_month(date_):
		r = datetime.date(date_.year, date_.month, date_.day)
		orig_month = r.month
		while r.month == orig_month:
			r -= datetime.timedelta(1)
		return r

	date = datetime.date.today()
	for i in range(12):
		print 'Date: %s' % date 
		windgraphs.get_observations_and_insert_into_db_single_month(date, False, 1)
		date = get_prev_month(date)
