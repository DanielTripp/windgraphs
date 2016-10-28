#!/usr/bin/env python

import sys
import windgraphs

if __name__ == '__main__':

	dry_run = len(sys.argv) == 2 and sys.argv[1] == '--dry-run'
	windgraphs.get_observations_and_insert_into_db(dry_run, 0)

