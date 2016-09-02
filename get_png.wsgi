#!/usr/bin/env python

import sys, os, os.path, urlparse, json, time, re, cgi, urllib
from collections import Sequence
sys.path.append('.')
import windgraphs
from misc import *

# WSGI entry point.
def application(environ, start_response):
	try:
		if '.' not in sys.path:
			# This was necessary once.  Not sure if it still is.
			sys.path.append('.')

		query_vars = urlparse.parse_qs(environ['QUERY_STRING'])
		target_time_of_day = int(query_vars['target_time_of_day'][0])
		weather_check_num_hours_in_advance = int(query_vars['weather_check_num_hours_in_advance'][0])
		num_days = int(query_vars['num_days'][0])

		png_content = windgraphs.get_png(target_time_of_day, weather_check_num_hours_in_advance, num_days)

		response_headers = [('Content-type', 'image/png')]
		start_response('200 OK', response_headers)

		return [png_content]

	except:
		printerr('[client %s]          (pid=%s) Request url: %s' % (environ['REMOTE_ADDR'], os.getpid(), get_request_url(environ)))
		raise

# Thanks to Ian Becking via https://www.python.org/dev/peps/pep-0333/ 
def get_request_url(environ):
	url = environ['wsgi.url_scheme']+'://'

	if environ.get('HTTP_HOST'):
			url += environ['HTTP_HOST']
	else:
			url += environ['SERVER_NAME']

			if environ['wsgi.url_scheme'] == 'https':
					if environ['SERVER_PORT'] != '443':
						 url += ':' + environ['SERVER_PORT']
			else:
					if environ['SERVER_PORT'] != '80':
						 url += ':' + environ['SERVER_PORT']

	url += urllib.quote(environ.get('SCRIPT_NAME', ''))
	url += urllib.quote(environ.get('PATH_INFO', ''))
	if environ.get('QUERY_STRING'):
			url += '?' + environ['QUERY_STRING']
	return url

