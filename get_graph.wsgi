#!/usr/bin/env python

import sys, os, os.path, urlparse, json, time, re, cgi, urllib, datetime, base64, json
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
		end_date = query_vars['end_date'][0]
		if end_date == 'today':
			end_date = datetime.date.today()
		else:
			end_date = datetime.date(int(end_date[:4]), int(end_date[4:6]), int(end_date[6:8]))
		png_content = windgraphs.get_png(target_time_of_day, weather_check_num_hours_in_advance, end_date, num_days)

		response_headers = [('Content-type', 'application/json')]
		start_response('200 OK', response_headers)

		r = {'png': base64.b64encode(png_content)}
		r = json.dumps(r)

		return [r]

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

