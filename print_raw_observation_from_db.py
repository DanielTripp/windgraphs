#!/usr/bin/env python

import sys
from misc import *
import windgraphs

if __name__ == '__main__':

	datestr = sys.argv[1]
	windgraphs.print_raw_observation(datestr)

