#!/usr/bin/env python

import sys
import windgraphs

if __name__ == '__main__':

	datestr = sys.argv[1]
	windgraphs.print_parsed_observation_from_db(datestr)



