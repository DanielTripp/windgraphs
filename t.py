#!/usr/bin/env python

import sys, pprint, datetime
import windgraphs

if __name__ == '__main__':

	#for day in range(1, 10):
	for day in [1]:
		windgraphs.get_graph_info(17, 24, datetime.date(2016, 10, day), 30)

