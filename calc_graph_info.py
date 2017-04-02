#!/usr/bin/env python

import sys, os, stat, datetime, pprint, base64, tempfile
import windgraphs

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

png_in_base64 = graph_info['png']
png_file_prefix = '%d---%d---%d---%s---' % (target_time, hours_in_advance, graph_domain_num_days, end_date)
png_dir=os.path.join(os.path.dirname(sys.argv[0]), 'tmp')
try:
	os.mkdir(png_dir)
except OSError:
	pass
with tempfile.NamedTemporaryFile(prefix=png_file_prefix, suffix='.png', dir=png_dir, delete=False) as fout:
	fout.write(base64.b64decode(png_in_base64))
	print 'Wrote PNG to %s' % fout.name
	print 
	os.chmod(fout.name, stat.S_IRWXU | stat.S_IRWXO)
del graph_info['png']

pprint.pprint(graph_info)



