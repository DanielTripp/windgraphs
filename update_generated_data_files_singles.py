#!/usr/bin/env python

import sys, datetime, os, json, time, traceback
import windgraphs
from dtpythonutil.misc import *

def make_single_file(target_time_, hours_in_advance_, stats_time_frame_days_):
	data_end_date = datetime.date.today()
	json_filename = windgraphs.get_json_filename(target_time_, hours_in_advance_, stats_time_frame_days_)
	data = windgraphs.get_data(
			target_time, hours_in_advance, data_end_date, stats_time_frame_days)
	windgraphs.write_json_file(json_filename, data)

def get_vals(arg_, all_):
	if arg_ == 'all':
		return all_
	else:
		return [int(e) for e in arg_.split(',')]

if __name__ == '__main__':

	target_times = get_vals(sys.argv[1], windgraphs.get_target_hours())
	hours_in_advances = get_vals(sys.argv[2], windgraphs.get_hours_in_advance())
	stats_time_frame_dayses = get_vals(sys.argv[3], windgraphs.get_stats_time_frame_days())
	for target_time in target_times:
		for hours_in_advance in hours_in_advances:
			for stats_time_frame_days in stats_time_frame_dayses:
				make_single_file(target_time, hours_in_advance, stats_time_frame_days)

