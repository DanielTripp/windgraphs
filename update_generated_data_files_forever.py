#!/usr/bin/env python

import sys, datetime, os, json, time, traceback
import windgraphs
from dtpythonutil.misc import *

def is_file_out_of_date(filename_):
	return not os.path.exists(filename_) or (time.time() - os.path.getmtime(filename_) > 60*60*6)

def make_all_files_if_out_of_date():
	data_end_date = datetime.date.today()
	for target_time in windgraphs.get_target_times():
		for hours_in_advance in windgraphs.get_hours_in_advance():
			for stats_time_frame_days in windgraphs.get_stats_time_frame_days():
				try:
					json_filename = windgraphs.get_json_filename(target_time, hours_in_advance, stats_time_frame_days)
					if is_file_out_of_date(json_filename):
						data = windgraphs.get_data(
								target_time, hours_in_advance, data_end_date, stats_time_frame_days)
						windgraphs.write_json_file(json_filename, data)
				except Exception:
					print >> sys.stderr, now_str(), \
							'Exception while making file.  Args: target_time=%d, hours_in_advance=%d, stats_time_frame_days=%d' \
							% (target_time, hours_in_advance, stats_time_frame_days)
					traceback.print_exc()

if __name__ == '__main__':

	os.nice(20)
	while True:
		make_all_files_if_out_of_date()
		time.sleep(60*30)
		windgraphs.db_reconnect()


