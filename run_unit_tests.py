#!/usr/bin/env python

import sys, subprocess
import windgraphs

if __name__ == '__main__':

	if len(sys.argv) == 1:
		subprocess.check_call([sys.executable, '-m', 'unittest', 'windgraphs'])
	elif len(sys.argv) == 2:
		test_method_name = sys.argv[1]
		subprocess.check_call([sys.executable, '-m', 'unittest', 'windgraphs.UnitTests.%s' % test_method_name])
	else:
		raise Exception()

