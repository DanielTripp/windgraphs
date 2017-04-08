#!/usr/bin/env python

import sys
import windgraphs

if __name__ == '__main__':

	verbose = len(sys.argv) == 2 and sys.argv[1] == '--verbose'
	windgraphs.get_all_forecasts_from_web_and_insert_into_db(verbose)


