#!/usr/bin/env python

import sys, datetime, os, json, time
import windgraphs

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

def get_out_filename(target_time_, hours_in_advance_, graph_domain_num_days_):
	r = 'graph_info___target_time_%02d___hours_in_advance_%d___graph_domain_num_days_%d.json' \
			% (target_time_, hours_in_advance_, graph_domain_num_days_)
	r = os.path.join(DEST_DIR, r)
	return r

def make_all_files():
	graph_end_date = datetime.date.today()
	for target_time in get_target_times():
		for hours_in_advance in get_hours_in_advance():
			for graph_domain_num_days in get_graph_domain_num_days():
				out_filename = get_out_filename(target_time, hours_in_advance, graph_domain_num_days)
				graph_info = windgraphs.get_graph_info(
						target_time, hours_in_advance, graph_end_date, graph_domain_num_days)
				with open(out_filename, 'w') as fout:
					json.dump(graph_info, fout)

if __name__ == '__main__':

	os.chdir(os.path.dirname(sys.argv[0]))
	if not os.path.isdir(DEST_DIR):
		os.makedirs(DEST_DIR)
	os.nice(10)
	while True:
		make_all_files()
		time.sleep(60)



