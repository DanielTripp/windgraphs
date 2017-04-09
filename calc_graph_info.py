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

graph_info = windgraphs.get_graph_info(target_time, hours_in_advance, end_date, graph_domain_num_days) 

png_content_in_base64 = graph_info['png']
png_filename_prefix = '%d---%d---%d---%s---' % (target_time, hours_in_advance, graph_domain_num_days, end_date)
png_filename = u.write_png_to_tmp(png_filename_prefix, png_content_in_base64)
print 'Wrote PNG to %s' % png_filename
print 
del graph_info['png']

pprint.pprint(graph_info)



