#!/usr/bin/env python

import sys
from dtpythonutil.misc import *
import windgraphs

def main():
	channel = sys.argv[1]
	datestr = sys.argv[2]
	windgraphs.print_raw_observation_from_db(channel, datestr)

if __name__ == '__main__':

	main()


