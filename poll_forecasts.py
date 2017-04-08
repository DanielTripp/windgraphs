#!/usr/bin/env python

import sys, os, argparse, time
from dtpythonutil.misc import *
import windgraphs

if __name__ == '__main__':

	argparser = argparse.ArgumentParser()
	argparser.add_argument('--force-web-get', action='store_true')
	argparser.add_argument('--dont-insert-into-db', action='store_true')
	argparser.add_argument('--redir-stdout-to-log-file', action='store_true')
	args = argparser.parse_args()
	if args.redir_stdout_to_log_file:
		logs_dir = os.path.expanduser('~/windgraphs-logs')
		try:
			os.makedirs(logs_dir)
		except OSError:
			pass
		stdout_log_file = os.path.join(logs_dir, 'windgraphs-poll-forecasts-stdout-%s.txt' % now_str_ymd())
		sys.stdout = open(stdout_log_file, 'a')
	windgraphs.get_all_forecasts_from_web_and_insert_into_db(args.force_web_get, args.dont_insert_into_db)


