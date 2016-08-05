#!/usr/bin/env python

import sys
import windgraphs

if __name__ == '__main__':

	time_retrieved = int(sys.argv[1])
	print windgraphs.parse_observation_in_db(time_retrieved)



