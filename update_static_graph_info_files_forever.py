#!/usr/bin/env python

import sys, datetime, os, json, time, stat, traceback
import windgraphs
from misc import *

DEST_DIR = 'static_graph_info'

def get_file_contents_as_list_of_integers(filename_):
	r = []
	with open(filename_) as fin:
		for line in fin:
			r.append(int(line.rstrip()))
	return r

def get_target_times():
	return get_file_contents_as_list_of_integers('target_times.txt')

def get_hours_in_advance():
	return get_file_contents_as_list_of_integers('hours_in_advance.txt')

def get_graph_domain_num_days():
	return get_file_contents_as_list_of_integers('graph_domain_num_days.txt')

def get_json_filename(target_time_, hours_in_advance_, graph_domain_num_days_):
	r = 'graph_info___target_time_%02d___hours_in_advance_%d___graph_domain_num_days_%d.json' \
			% (target_time_, hours_in_advance_, graph_domain_num_days_)
	r = os.path.join(DEST_DIR, r)
	return r

def is_file_out_of_date(filename_):
	return not os.path.exists(filename_) or (time.time() - os.path.getmtime(filename_) > 60*60*6)

def make_all_files_if_out_of_date():
	graph_end_date = datetime.date.today()
	for target_time in get_target_times():
		for hours_in_advance in get_hours_in_advance():
			for graph_domain_num_days in get_graph_domain_num_days():
				try:
					json_filename = get_json_filename(target_time, hours_in_advance, graph_domain_num_days)
					if is_file_out_of_date(json_filename):
						graph_info = windgraphs.get_graph_info(
								target_time, hours_in_advance, graph_end_date, graph_domain_num_days)
						write_file(json_filename, graph_info)
				except Exception:
					print >> sys.stderr, now_str(), \
							'Exception while making file.  Args: target_time=%d, hours_in_advance=%d, graph_domain_num_days=%d' \
							% (target_time, hours_in_advance, graph_domain_num_days)
					traceback.print_exc()

def write_file(filename_, contents_obj_):
	tempfile_fd, tempfile_path = tempfile.mkstemp(dir=os.path.dirname(filename_))
	os.close(tempfile_fd)
	with open(tempfile_path, 'w') as fout:
		json.dump(contents_obj_, fout)
	os.chmod(tempfile_path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)
	os.rename(tempfile_path, filename_)

if __name__ == '__main__':

	os.chdir(os.path.dirname(sys.argv[0]))
	if not os.path.isdir(DEST_DIR):
		os.makedirs(DEST_DIR)
	os.nice(20)
	while True:
		make_all_files_if_out_of_date()
		time.sleep(60*30)
		windgraphs.db_reconnect()


