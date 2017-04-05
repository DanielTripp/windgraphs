#!/usr/bin/env python

import sys
import BeautifulSoup

if __name__ == '__main__':

	with open(sys.argv[1]) as fin:
		html_str = fin.read()
	print BeautifulSoup.BeautifulSoup(html_str).prettify()

