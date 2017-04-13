#!/usr/bin/env python

import sys, os, stat, datetime, pprint, base64, tempfile, shutil
import windgraphs, u

if len(sys.argv) not in (4, 5):
	raise Exception()

target_time = int(sys.argv[1])
hours_in_advance = int(sys.argv[2])
graph_domain_num_days = int(sys.argv[3])
if len(sys.argv) == 4:
	end_date = datetime.date.today()
else:
	s = sys.argv[4]
	end_date = datetime.date(int(s[:4]), int(s[4:6]), int(s[6:8]))

stats = windgraphs.get_stats(target_time, hours_in_advance, end_date, graph_domain_num_days) 

pprint.pprint(stats)



