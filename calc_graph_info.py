#!/usr/bin/env python

import sys, datetime
import windgraphs

target_time = int(sys.argv[1])
hours_in_advance = int(sys.argv[2])
graph_domain_num_days = int(sys.argv[3])
end_date = datetime.date.today()

graph_info = windgraphs.get_graph_info(target_time, hours_in_advance, end_date, graph_domain_num_days) 
del graph_info['png']
print graph_info



