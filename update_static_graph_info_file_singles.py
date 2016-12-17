#!/usr/bin/env python

import sys, datetime, os, json, time, traceback
import windgraphs
from misc import *

def make_single_file(target_time_, hours_in_advance_, graph_domain_num_days_):
	graph_end_date = datetime.date.today()
	json_filename = windgraphs.get_json_filename(target_time_, hours_in_advance_, graph_domain_num_days_)
	graph_info = windgraphs.get_graph_info(
			target_time, hours_in_advance, graph_end_date, graph_domain_num_days)
	windgraphs.write_json_file(json_filename, graph_info)

def get_vals(arg_, all_):
	if arg_ == 'all':
		return all_
	else:
		return [int(e) for e in arg_.split(',')]

if __name__ == '__main__':

	target_times = get_vals(sys.argv[1], windgraphs.get_target_times())
	hours_in_advances = get_vals(sys.argv[2], windgraphs.get_hours_in_advance())
	graph_domain_num_dayses = get_vals(sys.argv[3], windgraphs.get_graph_domain_num_days())
	for target_time in target_times:
		for hours_in_advance in hours_in_advances:
			for graph_domain_num_days in graph_domain_num_dayses:
				make_single_file(target_time, hours_in_advance, graph_domain_num_days)

