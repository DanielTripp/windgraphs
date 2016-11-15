#!/usr/bin/env python

import sys
import windgraphs

if __name__ == '__main__':

	channel = sys.argv[1]
	datestr = sys.argv[2]
	windgraphs.print_reparsed_observation_from_db(channel, datestr)



