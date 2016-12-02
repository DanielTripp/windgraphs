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

if __name__ == '__main__':

	target_time = int(sys.argv[1])
	hours_in_advance = int(sys.argv[2])
	graph_domain_num_days = int(sys.argv[3])
	make_single_file(target_time, hours_in_advance, graph_domain_num_days)

