#!/usr/bin/env python

import sys, argparse
import windgraphs

if __name__ == '__main__':

	arg_parser = argparse.ArgumentParser()
	arg_parser.add_argument('--dry-run', action='store_true')
	arg_parser.add_argument('--channel', required=True, choices=('navcan', 'envcan'))
	arg_parser.add_argument('--print-level', type=int, default=0, choices=(0,1,2))
	args = arg_parser.parse_args()
	channel = args.channel
	dry_run = args.dry_run
	print_level = args.print_level
	windgraphs.get_observations_and_insert_into_db(channel, dry_run, print_level)

