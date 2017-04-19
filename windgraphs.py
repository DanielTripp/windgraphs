#!/usr/bin/env python

import sys, urllib2, json, pprint, re, datetime, os, threading, traceback, io, math, base64, StringIO, csv, tempfile, stat, random, copy
from xml.etree import ElementTree
import xml.dom.minidom, unittest
import dateutil.parser, dateutil.tz
import BeautifulSoup, psycopg2, pytz
import matplotlib
matplotlib.use('Agg')
import matplotlib.dates
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import pylab
import numpy as np
from dtpythonutil.misc import *
import u, c

# Methodology notes: 
# Meteoblue doesn't say 'average wind' or 'gust' anywhere - it has a range eg. "19-35".  It's 
# unclear if that first number is an average or a minimum.  We're taking it to 
# be an average - which I think is the same as all other forecast channels see 
# things (evidence?) and I'm a little more sure is how the environment canada 
# observations see things. 

PASSWORD = file_to_string(os.path.expanduser('~/.windgraphs/DB_PASSWORD')).strip()

JSON_DIR = 'generated_data_files'

DEV = os.path.exists('DEV')
DEV_READ_FROM_FILES = DEV and 0
DEV_WRITE_TO_FILES = DEV and 0

g_db_conn = None
g_lock = threading.RLock()

def get_forecast_web_get_func(raw_forecast_channel_):
	d = {
		'wf_reg': windfinder_regular_get_web_response, 
		'wf_sup': windfinder_super_get_web_response, 
		'wg': windguru_get_web_response}
	for channel in c.SAILFLOW_RAW_CHANNELS:
		d[channel] = lambda: sailflow_get_web_response(raw_forecast_channel_)
	for meteoblue_day in c.METEOBLUE_DAYS:
		channel = c.METEOBLUE_DAY_TO_RAW_CHANNEL[meteoblue_day]
		d[channel] = lambda day2=meteoblue_day: meteoblue_get_web_response(day2)
	return d[raw_forecast_channel_]

def get_forecast_parse_func(raw_forecast_channel_):
	d = {
		'wf_reg': windfinder_regular_parse_web_response, 
		'wf_sup': windfinder_super_parse_web_response, 
		'wg': windguru_parse_web_response 
		}
	for channel in c.SAILFLOW_RAW_CHANNELS:
		d[channel] = lambda s__, t__, c2=channel: sailflow_parse_web_response(s__, c2, t__)
	for meteoblue_day in c.METEOBLUE_DAYS:
		channel = c.METEOBLUE_DAY_TO_RAW_CHANNEL[meteoblue_day]
		d[channel] = meteoblue_parse_web_response
	return d[raw_forecast_channel_]

'''
Some database table definitions: 

postgres=> \d  wind_observations_raw
          Table "public.wind_observations_raw"
       Column       |          Type          | Modifiers
--------------------+------------------------+-----------
 channel            | character varying(100) |
 time_retrieved     | bigint                 |
 time_retrieved_str | character varying(100) |
 content            | character varying      |
Indexes:
    "wind_observations_raw_idx1" btree (time_retrieved)

postgres=> \d  wind_observations_parsed
         Table "public.wind_observations_parsed"
       Column       |          Type          | Modifiers
--------------------+------------------------+-----------
 channel            | character varying(100) |
 time_retrieved     | bigint                 |
 time_retrieved_str | character varying(100) |
 base_wind          | integer                |
 gust_wind          | integer                |
Indexes:
    "wind_observations_parsed_idx1" btree (time_retrieved)

postgres=> \d  wind_forecasts_raw
            Table "public.wind_forecasts_raw"
       Column       |          Type          | Modifiers
--------------------+------------------------+-----------
 weather_channel    | character varying(100) |
 time_retrieved     | bigint                 |
 time_retrieved_str | character varying(100) |
 content            | character varying      |
Indexes:
    "wind_forecasts_raw_idx1" btree (time_retrieved)
    "wind_forecasts_raw_weather_channel" btree (weather_channel)

postgres=> \d  wind_forecasts_parsed
          Table "public.wind_forecasts_parsed"
       Column       |          Type          | Modifiers
--------------------+------------------------+-----------
 weather_channel    | character varying(100) |
 time_retrieved     | bigint                 |
 time_retrieved_str | character varying(100) |
 target_time        | bigint                 |
 target_time_str    | character varying(100) |
 base_wind          | integer                |
 gust_wind          | integer                |
Indexes:
    "wind_forecasts_parsed_target_time" btree (target_time)
    "wind_forecasts_parsed_time_retrieved" btree (time_retrieved)
    "wind_forecasts_parsed_weather_channel" btree (weather_channel)

postgres=>
'''

def lock(f):
	'''
	'''
	def new_f(*args, **kwds):
		with g_lock:
			return f(*args, **kwds)
	return new_f

def trans(f):
	"""Decorator that calls commit() after the method finishes normally, or rollback() if an
	exception is raised.  

	That we call commit() / rollback() is of course necessary in the absence of any standard
	'auto-commit mode' that we can count on.
	""" 
	def new_f(*args, **kwds):
		try:
			returnval = f(*args, **kwds)
			db_conn().commit()
			return returnval
		except:
			db_conn().rollback()
			raise
	return new_f

def db_connect():
	global g_db_conn
	DATABASE_CONNECT_POSITIONAL_ARGS = ("dbname='postgres' user='windgraphs' host='localhost' password='%s'" % PASSWORD,)
	DATABASE_CONNECT_KEYWORD_ARGS = {}
	g_db_conn = psycopg2.connect(*DATABASE_CONNECT_POSITIONAL_ARGS, **DATABASE_CONNECT_KEYWORD_ARGS)

def db_disconnect():
	global g_db_conn
	if g_db_conn is not None:
		g_db_conn.close()
		g_db_conn = None

def db_reconnect():
	db_disconnect()
	db_connect()

def db_conn():
	if g_db_conn is None:
		db_connect()
	return g_db_conn

class Forecast(object):

	# param time_retrieved_ is in epoch millis 
	# param target_time_ is in epoch millis 
	def __init__(self, weather_channel_, time_retrieved_, target_time_, base_wind_, gust_wind_):
		assert isinstance(weather_channel_, str)
		assert all(isinstance(x, long) for x in [time_retrieved_, target_time_])
		assert all(isinstance(x, int) for x in [base_wind_, gust_wind_])
		self.weather_channel = weather_channel_
		self.time_retrieved = time_retrieved_
		self.target_time = target_time_
		self.base_wind = base_wind_
		self.gust_wind = gust_wind_

	def __str__(self):
		return 'Forecast(%s, %s, %s, wind=%2d, gust=%2d)' % \
				(self.weather_channel, em_to_str(self.time_retrieved), em_to_str(self.target_time), self.base_wind, self.gust_wind)

	def __repr__(self):
		return self.__str__()

	def __eq__(self, other_):
		return self.__dict__ == other_.__dict__


def windfinder_super_get_web_response():
	if DEV_READ_FROM_FILES:
		with open('d-test-predictions-wfsuper') as fin:
			r = fin.read()
	else:
		url = 'https://www.windfinder.com/weatherforecast/toronto_island'
		r = urllib2.urlopen(url).read()
		if DEV_WRITE_TO_FILES:
			with open('d-test-predictions-wfsuper', 'w') as fout:
				fout.write(r)
	return r

def windfinder_regular_get_web_response():
	if DEV_READ_FROM_FILES:
		with open('d-test-predictions-wfreg') as fin:
			r = fin.read()
	else:
		url = 'https://www.windfinder.com/forecast/toronto_island'
		r = urllib2.urlopen(url).read()
		if DEV_WRITE_TO_FILES:
			with open('d-test-predictions-wfreg', 'w') as fout:
				fout.write(r)
	return r

def get_forecast_from_web_and_insert_into_db(raw_channel_, force_web_get_, dont_insert_into_db_):
	time_retrieved_em = now_em()
	if force_web_get_ or not do_any_raw_forecasts_exist_in_db_since_top_of_hour(raw_channel_, time_retrieved_em):
		web_get_func = get_forecast_web_get_func(raw_channel_)
		web_response = web_get_func()
		insert_raw_forecast_into_db(raw_channel_, web_response, time_retrieved_em)
		parse_func = get_forecast_parse_func(raw_channel_)
		forecasts = parse_func(web_response, time_retrieved_em)
		if dont_insert_into_db_:
			for forecast in forecasts:
				print forecast
		else:
			insert_parsed_forecasts_into_db(forecasts)

def windfinder_regular_parse_web_response(web_response_str_, time_retrieved_em_):
	return windfinder_parse_web_response(web_response_str_, 'wf_reg', time_retrieved_em_)

def windfinder_super_parse_web_response(web_response_str_, time_retrieved_em_):
	return windfinder_parse_web_response(web_response_str_, 'wf_sup', time_retrieved_em_)

def parent(node_, n_):
	r = node_
	for i in xrange(n_):
		r = r.parent
	return r

# Note [1]: 
# WindFinder changed their format at 2017-03-02 07:00.  Before then, these sections of 
# the web page looked like this (this is case #1) :
#                    <div class="weathertable__header">
#                            Thursday, Mar 02
#                    </div>
# As of that date/time, they started looking like this (this is case #2) :
#                    <div class="weathertable__header">
#                      <h4>
#                          Thursday, Mar 02
#                      </h4>
# And there's another possibility - it seems to appear w/ the superforecast, eg. 2017-03-25 22:00 (this is case #3):  
#                     <div class="weathertable__header">
#                          <h4>Saturday, Mar 25</h4>
# This code handles all three. 
#
#
#
# Note [2]: I'm using this abs() test rather than a "target_time > 
# time_retrieved" test because of the case where eg. we retrieve a forecast at 
# 2017-03-01 12:00 and it contains data for 2017-03-01 08:00 (which is 4 hours 
# in the past).  Even if that data won't show up in our GUI, I would rather not 
# get target year wrong on it (because a "target_time > time_retrieved"
# would say that the target year is 2018) and put that wrong data in our 
# database.
def windfinder_parse_web_response_by_lines(web_response_str_, parsed_channel_, time_retrieved_):
	"""
	Return a list of Forecast objects. 
	The windfinder regular forecast and superforecast have different URLs but use the same HTML format. 
	"""
	lines = web_response_str_.splitlines()
	r = []
	linei = 0
	while linei < len(lines):
		line = lines[linei]
		if '<div class="weathertable__header">' in line:
			linei += 1
			line = lines[linei]
			# See note [1] 
			if '<h4>' in line: 
				if len(line.strip()) == len('<h4>'): # this is case #2 
					linei += 1
					hacked_line = lines[linei]
				else: # this is case #3
					hacked_line = line.strip()[len('<h4>'):-len('</h4>')]
			else: # this is note [1] - case #1 
				hacked_line = line
			target_month_and_day = re.sub('^.*? ', '', hacked_line.strip())
		elif '<span class="value">' in line and '<span class="unit">h</span>' in line:
			if '<div class="data-time weathertable__cell">' not in lines[linei-1] \
					or '<div class="cell-timespan weathertable__cellgroup weathertable__cellgroup--stacked">' not in lines[linei-2]:
				raise Exception('problem on line %d' % (linei+1))
			target_hour = int(re.search(r'>(\d+)<', line).group(1))
		elif '<span class="data-unit">max</span>&nbsp;<span class="units-ws">' in line:
			if not re.search(r'<div class="data-gusts data--minor [\w]+ weathertable__cell">', lines[linei-1]):
				raise Exception('problem on line %d' % (linei+1))
			windgusts = int(re.search(r'>(\d+)<', line).group(1))
			time_retrieved_datetime = em_to_datetime(time_retrieved_)
			year_retrieved = time_retrieved_datetime.year
			for target_year in (year_retrieved, year_retrieved+1):
				target_datetime = datetime.datetime.strptime('%s %d %d:00' % (target_month_and_day, target_year, target_hour), 
						'%b %d %Y %H:%M')
				if abs(target_datetime - time_retrieved_datetime) < datetime.timedelta(days=120): # See note [2]
					break
			else:
				raise Exception()
			target_datetime_em = datetime_to_em(target_datetime)
			r.append(Forecast(parsed_channel_, time_retrieved_, target_datetime_em, windspeed, windgusts))
		elif '<span class="units-ws">' in line:
			# The format of this section seems to differ between the WindFinder 
			# regular and superforecast.  These things appear on different lines due 
			# to whitespace formatting.  This is the kind of thing that we wouldn't 
			# have to worry about if we were parsing the HTML.  But we're not. 
			prev_three_lines = ''.join(lines[linei-3:linei+1])
			if not all(x in prev_three_lines for x in ['<span class="data-wrap">', '<div class="speed">', 
					'data-bar', 'data--major', 'weathertable__cell', 'wsmax-level-']):
				raise Exception('problem on line %d' % (linei+1))
			windspeed = int(re.search(r'>(\d+)<', line).group(1))
		linei += 1
	return r

def windfinder_parse_web_response(web_response_str_, parsed_channel_, time_retrieved_):
	return windfinder_parse_web_response_by_lines(web_response_str_, parsed_channel_, time_retrieved_)

def is_in_dst(dt_):
	dt = em_to_datetime(dt_) if isinstance(dt_, long) else dt_
	toronto_tzinfo = pytz.timezone('America/Toronto')
	dt_with_timezone = datetime.datetime.fromtimestamp(time.mktime(dt.timetuple()), toronto_tzinfo)
	dst_offset_in_seconds = dt_with_timezone.dst().total_seconds()
	assert dst_offset_in_seconds in (0.0, 3600.0)
	r = dst_offset_in_seconds > 0
	return r

def windguru_get_web_response():
	if DEV_READ_FROM_FILES:
		with open('d-test-predictions-wg') as fin:
			r = fin.read()
	else:
		url = 'http://www.windguru.cz/int/index.php?sc=64'
		r = urllib2.urlopen(url).read()
		if DEV_WRITE_TO_FILES:
			with open('d-test-predictions-wg', 'w') as fout:
				fout.write(r)
	return r

def to_ints(strs_):
	return [int(x) for x in strs_]

def windguru_parse_web_response(web_response_str_, time_retrieved_):
	soup = BeautifulSoup.BeautifulSoup(web_response_str_)
	r = []
	models = ['3', '4', '38'] # GFS = 3, NAM = 4, HRW = 38 
	model_to_weatherchannel = {'3':'wg_gfs', '4':'wg_nam', '38':'wg_hrw'}
	for i, script_tag in enumerate(soup.findAll('script')):
		for c in script_tag.contents:
			s = c.string
			if 'var wg_fcst_tab_data' in s:
				json_str = re.search('{.*}', s).group(0)
				parsed_data = json.loads(json_str)
				for model in models:
					if model in parsed_data['fcst']:
						data = parsed_data['fcst'][model]
						retrieved_datetime = data['update_last']
						# 'update_last' changed format around noon on November 22, 2016.  
						# Before then it was in the format "Thu, 01 Sep 2016 22:50:02 +0000", after it was "2016-12-01 22:50:02". 
						if re.match(r'\d\d\d\d-\d\d-\d\d', retrieved_datetime):
							retrieved_datetime = datetime.datetime.strptime(retrieved_datetime[:10], '%Y-%m-%d')
						else:
							retrieved_datetime = data['update_last'].split(',')[1].lstrip()
							retrieved_datetime = ' '.join(retrieved_datetime.split(' ', 3)[:3])
							retrieved_datetime = datetime.datetime.strptime(retrieved_datetime, '%d %b %Y')
						retrieved_year = retrieved_datetime.year
						retrieved_month = retrieved_datetime.month
						retrieved_day = retrieved_datetime.day
						windspeeds = data['WINDSPD']
						windgusts = data['GUST']
						days = to_ints(data['hr_d'])
						hours = to_ints(data['hr_h'])
						# I think I saw one of these lists have an extra element once.  I forget when. 
						n = min(len(l) for l in (windspeeds, windgusts, days, hours))
						windspeeds = windspeeds[:n]
						windgusts = windgusts[:n]
						days = days[:n]
						hours = hours[:n]
						day_retrieved = retrieved_datetime.day
						# Sometimes data for days before today is included, and sometimes 
						# some of the speed / gust data for in those days is null.  eg.  
						# 2016-08-17 13:00.  We could ignore the null data.  But instead we 
						# ignore data for days before today.  
						for cutoff_idx, day in enumerate(days):
							if day == day_retrieved:
								break
						assert len(windspeeds) == len(windgusts) == len(days) == len(hours) 
						for i in range(len(windspeeds))[::-1]:
							speed = windspeeds[i]
							gusts = windgusts[i]
							# I think that this code is here to handle cases like 2016-08-31 14:00 - 23:00: 
							if speed is None:
								print '%s  Omitting WindGuru %s reading #%d (day=%s, hour=%s) on account of null data.  speed=%s, gusts=%s.' \
										% (now_str_iso8601(), model_to_weatherchannel[model], i, days[i], hours[i], speed, gusts)
								for l in (windspeeds, windgusts, days, hours):
									del l[i]
							elif speed is not None and gusts is None:
								print '%s  Fudging WindGuru %s reading #%d (day=%s, hour=%s) on account of null gusts.  Setting gusts to speed (%s).' \
										% (now_str_iso8601(), model_to_weatherchannel[model], i, days[i], hours[i], speed)
								windgusts[i] = windspeeds[i]
						days = days[cutoff_idx:]
						hours = hours[cutoff_idx:]
						windspeeds = to_ints(windspeeds[cutoff_idx:])
						windgusts = to_ints(windgusts[cutoff_idx:])
						for day, hour, windspeed, windgust in zip(days, hours, windspeeds, windgusts):
							weatherchannel = model_to_weatherchannel[model]
							month = (retrieved_month if day >= retrieved_day else (retrieved_month % 12) + 1)
							def calc_datetime():
								return datetime.datetime.strptime('%02d-%02d %02d:00 %d' % (month, day, hour, retrieved_year), '%m-%d %H:%M %Y')
							daytetyme = calc_datetime()
							target_time = datetime_to_em(daytetyme)
							r.append(Forecast(weatherchannel, time_retrieved_, target_time, windspeed, windgust))
				break
	return r

def zip_filter(lists_, func_):
	assert len(set(len(l) for l in lists_)) == 1
	keep = [all(func_(l[i]) for l in lists_) for i in range(len(lists_[0]))]
	for l in lists_:
		l[:] = [e for i, e in enumerate(l) if keep[i]]

def get_envcan_observations_web_response(year_, month_):
	if DEV_READ_FROM_FILES:
		with open('d-current-conditions-envcan') as fin:
			r = fin.read()
	else:
		# Thanks to ftp://ftp.tor.ec.gc.ca/Pub/Get_More_Data_Plus_de_donnees/Readme.txt 
		# ("Day: the value of the "day" variable is not used and can be an arbitrary value")
		url = "http://climate.weather.gc.ca/climate_data/bulk_data_e.html?format=csv&stationID=48549&Year=%d&Month=%d&Day=14&timeframe=1&submit=Download+Data"
		url = url % (year_, month_)
		r = urllib2.urlopen(url).read()
		if DEV_WRITE_TO_FILES:
			with open('d-current-conditions-envcan', 'w') as fout:
				fout.write(r)
	return r

class Observation(object):

	def __init__(self, channel_, time_retrieved_, base_wind_, gust_wind_):
		self.channel = channel_
		self.time_retrieved = time_retrieved_
		self.base_wind = base_wind_
		self.gust_wind = gust_wind_

	def __str__(self):
		return 'Observation(%s, %s, wind=%2d, gust=%2d)' % (self.channel, em_to_str(self.time_retrieved), self.base_wind, self.gust_wind)

	def __repr__(self):
		return self.__str__()

def parse_envcan_observation_web_response(web_response_):
	r = []
	in_data_yet = False
	for line in web_response_.splitlines():
		if not in_data_yet:
			if line.startswith('"Date/Time","Year","Month","Day"'):
				in_data_yet = True
		else:
			fields = csv.reader(StringIO.StringIO(line)).next()
			if len(fields) > 14 and fields[14]:
				wind = kmph_to_knots(int(fields[14]))
				datetime = fields[0]
				time_retrieved = int(time.mktime(time.strptime(datetime, '%Y-%m-%d %H:%M'))*1000)
				gust = -1
				r.append(Observation('envcan', time_retrieved, wind, gust))
	return r

def kmph_to_knots(kmph_):
	return kmph_*0.539957

def mph_to_knots(mph_):
	return mph_*0.868976

@lock
@trans
def insert_raw_forecast_into_db(weather_channel_, web_response_str_, time_retrieved_):
	curs = db_conn().cursor()
	time_retrieved_str = em_to_str(time_retrieved_)
	cols = [weather_channel_, time_retrieved_, time_retrieved_str, web_response_str_]
	curs.execute('INSERT INTO wind_forecasts_raw VALUES (%s,%s,%s,%s)', cols)
	curs.close()

@lock
@trans
def insert_parsed_forecasts_into_db(forecasts_):
	curs = db_conn().cursor()
	try:
		for forecast in forecasts_:
			insert_parsed_forecast_into_db(forecast, curs)
	finally:
		curs.close()

def insert_parsed_forecast_into_db(forecast_, curs_=None):
	assert isinstance(forecast_, Forecast)
	curs = db_conn().cursor() if curs_ is None else curs_
	try:
		cols = [forecast_.weather_channel, forecast_.time_retrieved, em_to_str(forecast_.time_retrieved), forecast_.target_time, 
				em_to_str(forecast_.target_time), forecast_.base_wind, forecast_.gust_wind]
		curs.execute('INSERT INTO wind_forecasts_parsed VALUES (%s,%s,%s,%s,%s,%s,%s)', cols)
	finally:
		if curs_ is None:
			curs.close()

''' This returns True on success, but it will probably always succeed. 
The chances of the primary key on (channel, time_retrieved) are small.  
This check for integrity error makes more sense on the PARSED observations, and for envcan only.
'''
@lock
@trans
def insert_raw_observation_into_db(channel_, web_response_str_):
	r = False
	curs = db_conn().cursor()
	try:
		time_em = now_em()
		time_str = em_to_str(time_em)
		cols = [channel_, time_em, time_str, web_response_str_]
		curs.execute('INSERT INTO wind_observations_raw VALUES (%s,%s,%s,%s)', cols)
		r = True
	except psycopg2.IntegrityError, e:
		pass
	finally:
		curs.close()
	return r

@lock
@trans
def insert_parsed_observation_into_db(obs_):
	assert isinstance(obs_, Observation)
	r = False
	curs = db_conn().cursor()
	try:
		time_retrieved_str = em_to_str(obs_.time_retrieved)
		cols = [obs_.channel, obs_.time_retrieved, time_retrieved_str, obs_.base_wind, obs_.gust_wind]
		curs.execute('INSERT INTO wind_observations_parsed VALUES (%s,%s,%s,%s,%s)', cols)
		r = True
	except psycopg2.IntegrityError, e:
		pass
	finally:
		curs.close()
	return r

def get_raw_observation_from_db(channel_, t_):
	sqlstr = 'select content from wind_observations_raw where channel = %s and time_retrieved = %s'
	curs = db_conn().cursor()
	curs.execute(sqlstr, [channel_, t_])
	for row in curs:
		content = row[0]
		r = content
		break
	else:
		raise Exception('no rows')
	curs.close()
	return r

def print_reparsed_observation_from_db(channel_, datestr_):
	t = get_nearest_time_retrieved('wind_observations_raw', channel_, datestr_)
	if t is None:
		print 'No rows found'
	else:
		content = get_raw_observation_from_db(channel_, t)
		print t
		print em_to_str(t)
		print 
		if channel_ == 'envcan':
			for parsed_observation in parse_envcan_observation_web_response(content):
				print parsed_observation
		elif channel_ == 'navcan':
			print parse_navcan_observation_web_response(content)
		else:
			raise Exception()

def print_reparsed_forecasts_from_db(weather_channel_, datestr_):
	t = get_nearest_raw_forecast_time_retrieved(weather_channel_, datestr_)
	if t is None:
		print 'No rows found'
	else:
		print t
		print em_to_str(t)
		print 
		web_response = get_raw_forecast_from_db(weather_channel_, t)
		parse_func = get_forecast_parse_func(weather_channel_)
		forecasts = parse_func(web_response, t)
		for forecast in forecasts:
			print forecast

def get_this_month_and_last_dates():
	today = datetime.date.today()
	last_month_date = datetime.date(today.year, today.month, today.day)
	while last_month_date.month == today.month:
		last_month_date -= datetime.timedelta(1)
	return (today, last_month_date)

def get_observations_and_insert_into_db(channel_, dry_run_, printlevel_):
	if channel_ == 'envcan':
		get_envcan_observations_and_insert_into_db(dry_run_, printlevel_)
	elif channel_ == 'navcan':
		get_navcan_observations_and_insert_into_db(dry_run_, printlevel_)
	else:
		raise Exception('Unknown observation channel: "%s"' % channel_)

def get_navcan_observations_web_response():
	if DEV_READ_FROM_FILES:
		with open('d-current-conditions-navcan') as fin:
			r = fin.read()
	else:
		url = 'http://atm.navcanada.ca/atm/iwv/CYTZ'
		r = urllib2.urlopen(url).read()
		if DEV_WRITE_TO_FILES:
			with open('d-current-conditions-navcan', 'w') as fout:
				fout.write(r)
	return r

def get_navcan_observations_and_insert_into_db(dry_run_, printlevel_):
	assert printlevel_ in (0, 1, 2)
	web_response = get_navcan_observations_web_response()
	if printlevel_ == 2:
		print '(navcan) raw observation:'
		print web_response
	if not dry_run_:
		insert_success = insert_raw_observation_into_db('navcan', web_response)
		if printlevel_ in (1, 2):
			print '(navcan) insert (raw) was a success: %s' % (insert_success)
	parsed_observation = parse_navcan_observation_web_response(web_response)
	if printlevel_ == 2:
		print '(navcan) parsed observation:'
		print parsed_observation
	if not dry_run_:
		num_inserts = 0
		if insert_parsed_observation_into_db(parsed_observation):
			num_inserts += 1
		if printlevel_ in (1, 2):
			print '(navcan) total parsed observations: 1.  Num successfully inserted: %d' % (num_inserts)

# Unlike forecasts, we get a "time retrieved" from the web content on parse 
# here, so we insert that into the "parsed observations" table, so the "time 
# retrieved" values will not match between the "raw observations" and "parsed 
# observations" table.  It's unclear if there are any strong reasons for this.  
def parse_navcan_observation_web_response(web_response_):
	soup = BeautifulSoup.BeautifulSoup(web_response_)
	wind = None
	gust = None
	for x in soup.findAll('td', {'class': 'stat-cell'}):
		for content in x.contents:
			if 'Gusting' in content:
				gust = x.span.string
			elif 'Wind Speed' in content:
				# Witnessed this being ' ' once, 2016-08-18 23:40.  Other parts of the 
				# page looked like they were in error too.  
				wind = x.span.string
			elif 'Updated' in content:
				time_retrieved = x.span.string

	if wind == 'CALM':
		wind = 0
	else:
		wind = int(wind)

	if gust == '--':
		gust = wind
	else:
		gust = gust.lstrip('G')
	gust = int(gust)

	time_retrieved = datetime_to_em(dateutil.parser.parse(time_retrieved).astimezone(dateutil.tz.tzlocal()))
	return Observation('navcan', time_retrieved, wind, gust)

def get_envcan_observations_and_insert_into_db(dry_run_, printlevel_):
	this_month_date, last_month_date = get_this_month_and_last_dates()
	get_envcan_observations_and_insert_into_db_single_month(this_month_date, dry_run_, printlevel_)
	get_envcan_observations_and_insert_into_db_single_month(last_month_date, dry_run_, printlevel_)

def get_envcan_observations_and_insert_into_db_single_month(date_, dry_run_, printlevel_):
	assert printlevel_ in (0, 1, 2)
	web_response = get_envcan_observations_web_response(date_.year, date_.month)
	monthstr = '(%d-%02d)' % (date_.year, date_.month)
	if printlevel_ == 2:
		print '%s raw observations:' % monthstr
		print web_response
	if not dry_run_:
		insert_success = insert_raw_observation_into_db('envcan', web_response)
		if printlevel_ in (1, 2):
			print '%s insert (raw) was a success: %s' % (monthstr, insert_success)
	parsed_observations = parse_envcan_observation_web_response(web_response)
	if printlevel_ == 2:
		print '%s parsed observations:' % monthstr
		for observation in parsed_observations:
			print observation
	if not dry_run_:
		num_inserts = 0
		for observation in parsed_observations:
			if insert_parsed_observation_into_db(observation):
				num_inserts += 1
		if printlevel_ in (1, 2):
			print '%s total parsed observations: %d.  Num successfully inserted: %d' % (monthstr, len(parsed_observations), num_inserts)

def get_all_forecasts_from_web_and_insert_into_db(force_web_get_, dont_insert_into_db_):
	for raw_channel in c.FORECAST_RAW_CHANNELS:
		try:
			get_forecast_from_web_and_insert_into_db(raw_channel, force_web_get_, dont_insert_into_db_)
		except:
			traceback.print_exc()

# CMC doesn't have gust info, either in the JSON in the GUI.  
def sailflow_parse_web_response(web_response_, channel_, time_retrieved_em_):
	parse_gusts = channel_ != 'sf_cmc'
	data = json.loads(web_response_)
	parsed_forecasts = []
	if data['units_wind'] != 'mph':
		raise Exception()
	for raw_forecast in data['model_data']:
		target_time = raw_forecast['model_time_local']
		target_time = str_to_em(target_time[:16])
		base_wind_mph = raw_forecast['wind_speed']
		base_wind_knots = int(mph_to_knots(base_wind_mph))
		if parse_gusts:
			gusts_mph = raw_forecast['wind_gust']
		else:
			gusts_mph = base_wind_mph
		gusts_knots = int(mph_to_knots(gusts_mph))
		parsed_forecasts.append(Forecast(channel_, time_retrieved_em_, target_time, base_wind_knots, gusts_knots))
	return parsed_forecasts

# This function returns data in miles per hour.
def sailflow_get_web_response(model_):
	model_url_id = {'sf_q': '-1', 'sf_nam12': '1', 'sf_gfs': '2', 'sf_nam3': '161', 'sf_cmc': '78'}[model_]
	url_template = 'http://api.weatherflow.com/wxengine/rest/model/getModelDataBySpot?callback=jQuery17206727484519083629_%s&units_wind=mph&units_temp=f&units_distance=mi&spot_id=826&model_id=%s&wf_token=62b16fa1f351b2ab3fd99ccd1d0dd11e&_=%s'
	url = url_template % (now_em(), model_url_id, now_em())
	r = urllib2.urlopen(url).read()
	return r

def meteoblue_get_web_response(day_):
	assert day_ in c.METEOBLUE_DAYS
	if day_ == 1:
		url = 'https://www.meteoblue.com/en/weather/forecast/week/billy-bishop-toronto-city-airport_canada_6301483'
	else:
		url = 'https://www.meteoblue.com/en/weather/forecast/week/billy-bishop-toronto-city-airport_canada_6301483?day=%d' % day_
	r = urllib2.urlopen(url).read()
	return r

def meteoblue_parse_web_response(web_response_, time_retrieved_em_):
	soup = BeautifulSoup.BeautifulSoup(web_response_)
	date_str = soup.find('table', {'class': 'picto'}).find('tbody').find('tr', {'class': 'times'})\
			.find('th').find('time')['datetime']
	r = []
	winds_kmph = []
	for e in soup.findAll('tr', {'class': 'windspeeds', 'title': 'Wind speed (km/h)'}):
		for f in e.findAll('td'):
			for g in f.findAll('div', {'class': 'cell'}):
				wind_speed_range_kmph = g.contents[0]
				wind_speed_lo_kmph = int(wind_speed_range_kmph.split('-')[0])
				winds_kmph.append(wind_speed_lo_kmph)
	hours_of_day = []
	for e in soup.find('tr', {'class': 'times'}).findAll('div', {'class': re.compile('cell time.*')}):
		f = e.find('time', recursive=False)
		hour_of_day = int(f.contents[0].strip())
		hours_of_day.append(hour_of_day)
	if len(winds_kmph) != len(hours_of_day):
		raise Exception('Got %d winds and %d hours (%s / %s)' % (len(winds_kmph), len(hours_of_day), winds_kmph, hours_of_day))
	for hour_of_day, wind_kmph in zip(hours_of_day, winds_kmph):
		datetime_str = '%s %02d:00' % (date_str, hour_of_day)
		target_datetime = datetime.datetime.strptime(datetime_str, '%Y-%m-%d %H:%M')
		target_time_em = datetime_to_em(target_datetime)
		wind_knots = int(kmph_to_knots(wind_kmph))
		forecast = Forecast('mb', time_retrieved_em_, target_time_em, wind_knots, -1)
		r.append(forecast)
	return r

def get_forecast_near_time_retrieveds(weather_channel_, time_retrieved_approx_, target_time_, 
		get_time_greater_than_aot_less_than_, maxrows_, time_span_):
	assert isinstance(time_retrieved_approx_, long)
	assert isinstance(target_time_, long)
	sign = ('>=' if get_time_greater_than_aot_less_than_ else '<=')
	order = ('asc' if get_time_greater_than_aot_less_than_ else 'desc')
	sqlstr = '''select time_retrieved from wind_forecasts_parsed where target_time = %d and time_retrieved %s %d 
			and weather_channel = '%s' order by time_retrieved %s limit %d''' % \
			(target_time_, sign, time_retrieved_approx_, weather_channel_, order, maxrows_)
	curs = db_conn().cursor()
	try:
		curs.execute(sqlstr)
		r = []
		for row in curs:
			t = row[0]
			if (time_span_ is None) or (abs(t - time_retrieved_approx_) <= time_span_):
				r.append(t)
		return r
	finally:
		curs.close()

def get_forecast_nearest_time_retrieved(weather_channel_, time_retrieved_approx_, target_time_):
	times = get_forecast_nearest_time_retrieveds(weather_channel_, time_retrieved_approx_, target_time_, 5, 1000*60*30)
	if len(times) == 0:
		return None
	else:
		return min(times, key=lambda t: abs(t-time_retrieved_approx_))

def get_forecast_nearest_time_retrieveds(weather_channel_, time_retrieved_em_, target_time_, 
			maxrows_each_side_, time_span_each_side_):
	less_thans = get_forecast_near_time_retrieveds(weather_channel_, time_retrieved_em_, target_time_, False, 
			maxrows_each_side_, time_span_each_side_)
	greater_thans = get_forecast_near_time_retrieveds(weather_channel_, time_retrieved_em_, target_time_, True, 
			maxrows_each_side_, time_span_each_side_)
	r = list(reversed(less_thans)) + greater_thans
	return r

def get_near_time_retrieveds(table_, channel_, time_em_, get_time_greater_than_aot_less_than_, maxrows_, time_span_):
	assert table_.startswith('wind_observations_')
	sign = ('>=' if get_time_greater_than_aot_less_than_ else '<=')
	order = ('asc' if get_time_greater_than_aot_less_than_ else 'desc')
	sqlstr = '''select time_retrieved from %s  
			where channel = '%s' and time_retrieved %s %d order by time_retrieved %s limit %d''' \
			% (table_, channel_, sign, time_em_, order, maxrows_)
	curs = db_conn().cursor()
	try:
		curs.execute(sqlstr)
		r = []
		for row in curs:
			t = row[0]
			if (time_span_ is None) or (abs(t - time_em_) <= time_span_):
				r.append(t)
		return r
	finally:
		curs.close()

def get_near_time_retrieved(table_, channel_, time_em_, get_time_greater_than_aot_less_than_):
	r = get_near_time_retrieveds(table_, channel_, time_em_, get_time_greater_than_aot_less_than_, 1, None)
	assert len(r) <= 1
	return (None if len(r) == 0 else r[0])

def get_nearest_raw_forecast_time_retrieved(weather_channel_, datestr_):
	t = str_to_em(datestr_)
	lt_time = get_raw_forecast_near_time_retrieved(weather_channel_, t-1, False)
	gt_time = get_raw_forecast_near_time_retrieved(weather_channel_, t,   True)
	return vote_on_nearest_time(t, lt_time, gt_time)

def get_raw_forecast_near_time_retrieved(weather_channel_, t_, get_time_greater_than_aot_less_than_):
	sign = ('>=' if get_time_greater_than_aot_less_than_ else '<=')
	order = ('asc' if get_time_greater_than_aot_less_than_ else 'desc')
	sqlstr = '''select time_retrieved from wind_forecasts_raw 
			where weather_channel = %%s and time_retrieved %s %%s order by time_retrieved %s limit 1''' % (sign, order)
	curs = db_conn().cursor()
	try:
		curs.execute(sqlstr, [weather_channel_, t_])
		r = None
		for row in curs:
			r = row[0]
		return r
	finally:
		curs.close()

def get_nearest_time_retrieved(table_, channel_, datestr_):
	time_em = str_to_em(datestr_)
	lt_time = get_near_time_retrieved(table_, channel_, time_em-1, False)
	gt_time = get_near_time_retrieved(table_, channel_, time_em, True)
	return vote_on_nearest_time(time_em, lt_time, gt_time)

def vote_on_nearest_time(t_, lt_time_, gt_time_):
	r = None
	if gt_time_ is None and lt_time_ is None:
		pass
	elif gt_time_ is None and lt_time_ is not None:
		r = lt_time_
	elif gt_time_ is not None and lt_time_ is None:
		r = gt_time_
	else:
		if abs(t_ - lt_time_) < abs(t_ - gt_time_):
			r = lt_time_
		else:
			r = gt_time_
	return r
	
def print_raw_observation_from_db(channel_, datestr_):
	t = get_nearest_time_retrieved('wind_observations_raw', channel_, datestr_)
	if t is None:
		print 'No rows found'
	else:
		content = get_raw_observation_from_db(channel_, t)
		print t
		print em_to_str(t)
		print 
		print content

def print_raw_forecast_from_db(weather_channel_, datestr_):
	t = get_nearest_raw_forecast_time_retrieved(weather_channel_, datestr_)
	if t is None:
		print 'No rows found'
	else:
		content = get_raw_forecast_from_db(weather_channel_, t)
		print content
		print 'The line above was the last line of the content.'
		print t
		print em_to_str(t)

def get_raw_forecast_from_db(weather_channel_, t_):
	sqlstr = 'select content from wind_forecasts_raw where time_retrieved = %d' % (t_)
	curs = db_conn().cursor()
	curs.execute(sqlstr)
	for row in curs:
		content = row[0]
		r = content
		break
	else:
		raise Exception('no rows')
	curs.close()
	return r

def get_observation_from_db(channel_, t_):
	assert isinstance(t_, long)
	sqlstr = '''select base_wind, gust_wind from wind_observations_parsed where channel = %s
			and time_retrieved = %s'''
	curs = db_conn().cursor()
	try:
		curs.execute(sqlstr, [channel_, t_])
		for row in curs:
			base_wind, gust_wind = row
			return Observation('envcan', t_, base_wind, gust_wind)
		else:
			return None
	finally:
		curs.close()

def get_days(start_date_, num_days_):
	r = []
	r.append(start_date_)
	for i in xrange(num_days_-1):
		r.append(r[-1] - datetime.timedelta(1))
	r = r[::-1]
	return r

def get_raw_forecast_time_retrieveds(weather_channel_, start_date_incl_, end_date_excl_):
	curs = db_conn().cursor()
	try:
		sqlstr = '''select time_retrieved from wind_forecasts_raw where 
				weather_channel = %s and time_retrieved between %s and %s order by time_retrieved '''
		cols = [weather_channel_, start_date_incl_, end_date_excl_-1]
		curs.execute(sqlstr, cols)
		r = []
		for row in curs:
			t = row[0]
			r.append(t)
		return r
	finally:
		curs.close()

def delete_parsed_forecasts_in_db(raw_weather_channel_, start_date_incl_, end_date_excl_):
	for parsed_channel in c.FORECAST_RAW_CHANNEL_TO_PARSED[raw_weather_channel_]:
		curs = db_conn().cursor()
		try:
			sqlstr = '''delete from wind_forecasts_parsed where weather_channel = %s and time_retrieved between %s and %s'''
			cols = [parsed_channel, start_date_incl_, end_date_excl_-1]
			curs.execute(sqlstr, cols)
		finally:
			curs.close()

def reparse_raw_forecasts_in_db(raw_weather_channel_, start_date_incl_, end_date_excl_):
	assert isinstance(start_date_incl_, long)
	assert isinstance(end_date_excl_, long)
	chunk_size_millis = 1000L*60*60*24*7
	if end_date_excl_ - start_date_incl_ > chunk_size_millis:
		for chunk_start_date_incl in lrange(start_date_incl_, end_date_excl_, chunk_size_millis):
			chunk_end_date_excl = chunk_start_date_incl + chunk_size_millis
			reparse_raw_forecasts_in_db(raw_weather_channel_, chunk_start_date_incl, chunk_end_date_excl)
	else:
		delete_parsed_forecasts_in_db(raw_weather_channel_, start_date_incl_, end_date_excl_)
		time_retrieveds = get_raw_forecast_time_retrieveds(raw_weather_channel_, start_date_incl_, end_date_excl_)
		for time_retrieved in time_retrieveds:
			print 'Reparsing %s %s...' % (raw_weather_channel_, em_to_str(time_retrieved))
			raw_forecast_content = get_raw_forecast_from_db(raw_weather_channel_, time_retrieved)
			parse_func = get_forecast_parse_func(raw_weather_channel_)
			forecasts = parse_func(raw_forecast_content, time_retrieved)
			insert_parsed_forecasts_into_db(forecasts)

def do_any_parsed_forecasts_exist_near_time_retrieved(channels_, t_, tolerance_):
	return do_any_forecasts_exist_near_time_retrieved('wind_forecasts_parsed', channels_, t_, tolerance_)

def do_any_raw_forecasts_exist_near_time_retrieved(channel_, t_, tolerance_):
	return do_any_forecasts_exist_near_time_retrieved('wind_forecasts_raw', [channel_], t_, tolerance_)

def do_any_forecasts_exist_near_time_retrieved(table_, channels_, t_, tolerance_):
	assert isinstance(channels_, list)
	curs = db_conn().cursor()
	try:
		sqlstr = '''select time_retrieved from %s where time_retrieved between %%s and %%s and 
				weather_channel in (%s) limit 1''' % (table_, ','.join("'%s'" % x for x in channels_))
		cols = [t_ - tolerance_, t_ + tolerance_]
		curs.execute(sqlstr, cols)
		r = False
		for row in curs:
			r = True
		return r
	finally:
		curs.close()

def do_any_raw_forecasts_exist_in_db_since_top_of_hour(raw_channel_, now_em_):
	now_datetime = em_to_datetime(now_em_)
	top_of_hour_datetime = datetime.datetime(now_datetime.year, now_datetime.month, now_datetime.day, now_datetime.hour)
	top_of_hour_em = datetime_to_em(top_of_hour_datetime)
	curs = db_conn().cursor()
	try:
		sqlstr = '''select time_retrieved from wind_forecasts_raw where time_retrieved >= %s and 
				weather_channel = %s limit 1'''
		cols = [top_of_hour_em, raw_channel_]
		curs.execute(sqlstr, cols)
		r = False
		for row in curs:
			r = True
		return r
	finally:
		curs.close()

# Get a forecast for near the specified time retrieved.  (Not near the target 
# time - target time is taken as exact.)
def get_forecast_parsed_near(channel_, time_retrieved_, target_time_):
	curs = db_conn().cursor()
	try:
		# Thanks to http://stackoverflow.com/a/6103352 for this SQL 
		sqlstr = '''SELECT * FROM 
			(
				(SELECT %(get_cols)s FROM %(table)s WHERE %(where)s and %(t)s >= %%s and %(t)s <= %%s ORDER BY %(t)s      LIMIT 1) 
				UNION ALL
				(SELECT %(get_cols)s FROM %(table)s WHERE %(where)s and %(t)s <  %%s and %(t)s >= %%s ORDER BY %(t)s DESC LIMIT 1) 
			) as f 
			ORDER BY abs(%%s-time_retrieved) LIMIT 1
			''' % {'get_cols': 'weather_channel, time_retrieved, target_time, base_wind, gust_wind', 
						'table': 'wind_forecasts_parsed', 't': 'time_retrieved', 
						'where': 'weather_channel = %s and target_time = %s'}
		tolerance = 1000*60*30
		cols = [channel_, target_time_, time_retrieved_, time_retrieved_+tolerance, 
				channel_, target_time_, time_retrieved_, time_retrieved_-tolerance, 
				time_retrieved_]
		curs.execute(sqlstr, cols)
		r = None
		for row in curs:
			r = Forecast(*row)
		return r
	finally:
		curs.close()

# Database select template: 
def f________________________():
	curs = db_conn().cursor()
	try:
		sqlstr = '''select from wind_observations_parsed where time_retrieved = %s'''
		cols = [xyz]
		curs.execute(sqlstr, cols)
		for row in curs:
			pass
	finally:
		curs.close()

def date_to_em(date_):
	assert isinstance(date_, datetime.date)
	return int(time.mktime(date_.timetuple())*1000)

def delete_parsed_observations(up_to_time_em_):
	curs = db_conn().cursor()
	try:
		sqlstr = '''delete from wind_observations_parsed where time_retrieved <= %s'''
		cols = [up_to_time_em_]
		curs.execute(sqlstr, cols)
	finally:
		curs.close()

def delete_parsed_forecasts(up_to_time_em_):
	curs = db_conn().cursor()
	try:
		sqlstr = '''delete from wind_forecasts_parsed where time_retrieved <= %s'''
		cols = [up_to_time_em_]
		curs.execute(sqlstr, cols)
	finally:
		curs.close()

@lock
@trans
def copy_db_data_for_testing():
	dest_end_em = date_to_em(datetime.date(1980, 8, 28))
	src_end_em = date_to_em(datetime.date(2016, 8, 28))
	delete_parsed_observations(dest_end_em)
	delete_parsed_forecasts(dest_end_em)
	time_window = 1000*60*60*24*30
	copy_parsed_observations_for_testing(src_end_em, dest_end_em, time_window)
	copy_parsed_forecasts_for_testing(src_end_em, dest_end_em, time_window)

@lock
@trans
def copy_parsed_forecasts_for_testing(src_end_em_, dest_end_em_, time_window_):
	curs = db_conn().cursor()
	try:
		sqlstr = '''select weather_channel, time_retrieved, target_time, base_wind, gust_wind from wind_forecasts_parsed 
				where time_retrieved between %s and %s and target_time < time_retrieved + 1000*60*60*24*2'''
		cols = [src_end_em_ - time_window_ - 1000*60*60*24*7, src_end_em_]
		curs.execute(sqlstr, cols)
		curs2 = db_conn().cursor()
		try:
			for row in curs:
				weather_channel = row[0]
				time_offset = dest_end_em_ - src_end_em_
				src_time_retrieved = row[1]
				dest_time_retrieved = src_time_retrieved + time_offset
				src_target_time = row[2]
				dest_target_time = src_target_time + time_offset
				base_wind = row[3]
				gust_wind = row[4]
				forecast = Forecast(weather_channel, dest_time_retrieved, dest_target_time, base_wind, gust_wind)
				insert_parsed_forecast_into_db(forecast, curs2)
		finally:
			curs2.close()
	finally:
		curs.close()

@lock
@trans
def copy_parsed_observations_for_testing(src_end_em_, dest_end_em_, time_window_):
	curs = db_conn().cursor()
	try:
		sqlstr = '''select time_retrieved, base_wind, gust_wind from wind_observations_parsed 
				where time_retrieved between %s and %s'''
		cols = [src_end_em_ - time_window_, src_end_em_]
		curs.execute(sqlstr, cols)
		for row in curs:
			src_time_retrieved = row[0]
			dest_time_retrieved = dest_end_em_ - (src_end_em_ - src_time_retrieved)
			base_wind = row[1]
			gust_wind = row[2]
			obs = Observation(dest_time_retrieved, base_wind, base_wind)
			insert_parsed_observation_into_db(obs)
	finally:
		curs.close()

def get_graph_width_inches(num_days_):
	return get_range_val((15,7), (365,170), num_days_)

def should_channel_be_fudged_for_dst(channel_):
	assert channel_ in c.FORECAST_PARSED_CHANNELS
	r = channel_ in ('wf_reg', 'wg_gfs', 'wg_nam', 'sf_nam12', 'sf_gfs', 'sf_cmc', 'mb')
	return r

def get_observations_and_forecasts_from_db(target_time_of_day_, weather_check_num_hours_in_advance_, 
			end_date_, num_days_):
	assert target_time_of_day_ in get_target_times()
	assert weather_check_num_hours_in_advance_ in get_hours_in_advance()
	assert isinstance(end_date_, datetime.date)
	assert num_days_ in get_stats_time_frame_days()
	target_times = get_target_times_em(target_time_of_day_, end_date_, num_days_)
	observations = []
	channel_to_forecasts = defaultdict(lambda: [])
	for gui_target_time in target_times:
		fudged_target_time = gui_target_time - 1000*60*60
		non_fudged_target_time = gui_target_time

		observation_for_fudged_target_time = get_observation_from_db('envcan', fudged_target_time)
		if observation_for_fudged_target_time is not None:
			observations.append((em_to_datetime(fudged_target_time), observation_for_fudged_target_time.base_wind))

		observation_for_non_fudged_target_time = get_observation_from_db('envcan', non_fudged_target_time)
		if observation_for_non_fudged_target_time is not None:
			observations.append((em_to_datetime(non_fudged_target_time), observation_for_non_fudged_target_time.base_wind))

		for channel in c.FORECAST_PARSED_CHANNELS:
			fudge_for_dst = should_channel_be_fudged_for_dst(channel) and not is_in_dst(non_fudged_target_time)
			real_target_time = fudged_target_time if fudge_for_dst else non_fudged_target_time
			check_weather_time = real_target_time - 1000*60*60*weather_check_num_hours_in_advance_
			forecast = get_forecast_parsed_near(channel, check_weather_time, real_target_time)
			if forecast is not None:
				channel_to_forecasts[channel].append(\
						(em_to_datetime(gui_target_time), em_to_datetime(real_target_time), forecast.base_wind))

	return (observations, channel_to_forecasts)

# param target_time_of_day_ -1 means all times 
def get_target_times_em(target_time_of_day_, end_date_, num_days_):
	assert target_time_of_day_ in get_target_times()
	days = get_days(end_date_, num_days_)
	if target_time_of_day_ == -1:
		times = [datetime.time(t, 00) for t in get_target_times() if t != -1]
	else:
		times = [datetime.time(target_time_of_day_, 00)]
	r = []
	r = [datetime_to_em(datetime.datetime.combine(day, tyme)) for tyme in times for day in days]
	return r

def get_html(channel_to_score_, channel_to_num_forecasts_):
	div = ElementTree.Element('div')
	table = ElementTree.SubElement(div, 'table', {'style':'border-spacing:7mm 1mm'})
	table_header_row = ElementTree.SubElement(table, 'tr')
	ElementTree.SubElement(table_header_row, 'th', {'valign':'top', 'style':'text-align:left'}).text = 'Forecast source'
	h2 = ElementTree.SubElement(table_header_row, 'th')
	h2.text = '"Mean Squared Error" score'
	ElementTree.SubElement(h2, 'br').tail = '(Lower = more accurate)'
	h3 = ElementTree.SubElement(table_header_row, 'th')
	h3.text = 'Number of forecasts included'
	ElementTree.SubElement(h3, 'br').tail = 'in this calculation'
	channels_sorted_by_score = sorted(channel_to_score_.keys(), key=lambda c: channel_to_score_[c] or sys.maxint)
	for i, channel in enumerate(channels_sorted_by_score):
		score = channel_to_score_[channel]
		num_forecasts = channel_to_num_forecasts_[channel]
		channel_long_name = c.FORECAST_PARSED_CHANNEL_TO_SINGLE_LINE_HTML_NAME[channel]
		background_color = '#d6d6d6' if i % 2 == 0 else '#c4c4c4'
		tr = ElementTree.SubElement(table, 'tr', {'style':'background-color: %s;' % background_color})
		url = 'external_sites/%s.html' % channel
		ElementTree.SubElement(ElementTree.SubElement(tr, 'td'), 'a', {'href':url}).text = channel_long_name
		ElementTree.SubElement(tr, 'td', {'style':'text-align:center'}).text = '-' if score is None else str(score)
		ElementTree.SubElement(tr, 'td', {'style':'text-align:center'}).text = str(num_forecasts)
	ElementTree.SubElement(div, 'p').text = 'The statistics above were last updated on %s.' % \
			time.strftime('%B %-d, %Y at %I:%M %p', time.localtime())
	r = toprettyxml_ElementTree(div)
	return r

def toprettyxml_ElementTree(et_):
	r = xml.dom.minidom.parseString(ElementTree.tostring(et_)).toprettyxml()
	return r

def get_data(target_time_of_day_, weather_check_num_hours_in_advance_, end_date_, num_days_):
	observations, channel_to_forecasts = get_observations_and_forecasts_from_db(target_time_of_day_, 
			weather_check_num_hours_in_advance_, end_date_, num_days_)

	channel_to_score = get_forecast_channel_to_score(observations, channel_to_forecasts)
	channel_to_num_forecasts = get_channel_to_num_forecasts(channel_to_forecasts)
	html = get_html(channel_to_score, channel_to_num_forecasts)

	return {'channel_to_score': channel_to_score, 
			'channel_to_num_forecasts': channel_to_num_forecasts, 
			'html': html}

def get_channel_to_num_forecasts(channel_to_forecasts_):
	r = {}
	for channel, forecasts in channel_to_forecasts_.iteritems():
		r[channel] = len(forecasts)
	return r

def get_forecast_channel_to_score(observations_, channel_to_forecasts_):
	observation_datetime_to_wind = {}
	for observation in observations_:
		observation_datetime_to_wind[observation[0]] = observation[1]
	r = {}
	for channel, forecasts in channel_to_forecasts_.iteritems():
		channel_score = 0
		for forecast_gui_datetime, forecast_real_datetime, forecast_wind in forecasts:
			if forecast_real_datetime in observation_datetime_to_wind:
				observation_wind = observation_datetime_to_wind[forecast_real_datetime]
				channel_score += (observation_wind - forecast_wind)**2
		if forecasts:
			channel_score /= len(forecasts)
			r[channel] = channel_score
		else:
			r[channel] = None
	return r

def get_xaxis_tick_step(num_days_):
	return int(math.ceil(get_range_val((20,1.0), (40,2.0), num_days_)))

def get_json_filename(target_time_, hours_in_advance_, stats_time_frame_days_):
	r = 'data___target_time_%02d___hours_in_advance_%d___stats_time_frame_days_%d.json' \
			% (target_time_, hours_in_advance_, stats_time_frame_days_)
	r = os.path.join(JSON_DIR, r)
	return r

def create_json_dir_if_necessary():
	full_dest_dir = os.path.join(os.path.dirname(sys.argv[0]), JSON_DIR)
	if not os.path.isdir(JSON_DIR):
		os.makedirs(JSON_DIR)

def write_json_file(filename_, contents_obj_):
	create_json_dir_if_necessary()
	tempfile_fd, tempfile_path = tempfile.mkstemp(dir=os.path.dirname(filename_))
	os.close(tempfile_fd)
	with open(tempfile_path, 'w') as fout:
		json.dump(contents_obj_, fout)
	os.chmod(tempfile_path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)
	os.rename(tempfile_path, filename_)

def get_file_contents_as_list_of_integers(filename_):
	r = []
	with open(os.path.join('config', filename_)) as fin:
		for line in fin:
			r.append(int(line.rstrip()))
	return r

def get_target_times():
	return get_file_contents_as_list_of_integers('target_times.txt')

def get_hours_in_advance():
	return get_file_contents_as_list_of_integers('hours_in_advance.txt')

def get_stats_time_frame_days():
	return get_file_contents_as_list_of_integers('stats_time_frame_days.txt')

def get_parsed_observations(channel_, min_time_, max_time_):
	sqlstr = '''select time_retrieved, base_wind, gust_wind from wind_observations_parsed where channel = %s
			and time_retrieved between %s and %s order by time_retrieved'''
	curs = db_conn().cursor()
	try:
		curs.execute(sqlstr, [channel_, min_time_, max_time_])
		r = []
		for row in curs:
			time_retrieved, base_wind, gust_wind = row
			r.append(Observation(channel_, time_retrieved, base_wind, gust_wind))
		return r
	finally:
		curs.close()

def get_graph_vals_from_observations(observations_):
	r = []
	for observation in observations_:
		r.append((em_to_datetime(observation.time_retrieved), observation.base_wind))
	return r

def make_observation_graph_envcan_vs_navcan():
	main_figure = plt.figure(1)
	fig, ax = plt.subplots()
	fig.set_size_inches(100, 8)
	start_date = datetime.date(2017, 1, 1)
	end_date = datetime.date(2017, 2, 1)
	envcan_observations = get_parsed_observations('envcan', date_to_em(start_date), date_to_em(end_date))
	navcan_observations = get_parsed_observations('navcan', date_to_em(start_date), date_to_em(end_date))

	envcan_graph_vals = get_graph_vals_from_observations(envcan_observations)
	navcan_graph_vals = get_graph_vals_from_observations(navcan_observations)

	def xvals(run__):
		return [e[0] for e in run__]

	def yvals(run__):
		return [e[1] for e in run__]

	plt.plot(xvals(navcan_graph_vals), yvals(navcan_graph_vals), markeredgecolor=(0,0,1), color=(0,0,1), 
			marker='4', markeredgewidth=2, markersize=9, linestyle='none')

	plt.plot(xvals(envcan_graph_vals), yvals(envcan_graph_vals), markeredgecolor=(0,1,0), color=(0,1,0), 
			marker='1', markeredgewidth=2, markersize=9, linestyle='none')

	min_xval = min(xvals(envcan_graph_vals + navcan_graph_vals))
	max_xval = max(xvals(envcan_graph_vals + navcan_graph_vals))
	max_yval = max(yvals(envcan_graph_vals + navcan_graph_vals))
	max_yval = round_up(int(math.ceil(max_yval))+5, 5)

	# Increasing the amount of domain shown, because otherwise the first and last 
	# data points are of the left and right borders of the image, and that looks 
	# bad. 
	x_margin = 1000*60*60*24
	plt.xlim(em_to_datetime(datetime_to_em(min_xval)-x_margin), em_to_datetime(datetime_to_em(max_xval)+x_margin))

	# Draw date labels on X-axis:
	fig.autofmt_xdate()
	date_format = ('%b %d %Y' if end_date < datetime.date(1990, 1, 1) else '%b %d') # Include year, for testing time frames 
	ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter(date_format))
	tick_datetimes = []
	tick_datetime = datetime_round_down_to_midnight(min_xval)
	while tick_datetime <= max_xval:
		tick_datetimes.append(tick_datetime)
		tick_datetime += datetime.timedelta(days=1)
	ax.xaxis.set_major_locator(matplotlib.ticker.FixedLocator(map(pylab.date2num, tick_datetimes)))

	for date1 in datetime_xrange(datetime_to_date(min_xval), datetime_to_date(max_xval), 
				datetime.timedelta(days=1)):
		for datetime2 in datetime_xrange(date_to_datetime(date1), date_to_datetime(date1) + datetime.timedelta(days=1), 
				datetime.timedelta(hours=3)):
			plt.axvline(datetime2, color=(0.5,0.5,0.5), alpha=0.5, linestyle='-')

	for y in range(0, max_yval, 5):
		plt.axhline(y, color=(0.5,0.5,0.5), alpha=0.5, linestyle='-')
	plt.yticks(np.arange(0, max_yval+5, 5)) # Do this /after/ the axhline() calls or else the min value might not be respected. 

	plt.ylim(-max_yval/15.0, max_yval)

	plt.ylabel('Average wind (knots)')

	buf = io.BytesIO()
	plt.savefig(buf, bbox_inches='tight')
	buf.seek(0)
	png_content = buf.read()
	png_content_base64 = base64.b64encode(png_content)
	main_figure.clf()
	plt.close()

	u.write_png_to_tmp('observations-compare---', png_content_base64)

def create_db_tables():
	stmts = readfile('db_create_table_stmts.txt')
	db_execute(stmts)

class UnitTests(unittest.TestCase):

	def test_simple(self):
		delete_all_other_test_schemas_first = True
		delete_this_test_schemas_after = False
		schema_name = self.create_and_use_db_schema_for_testing(delete_all_other_test_schemas_first)
		try:
			create_db_tables()
			year = 1980
			month = 1
			day = 1
			daystr = '%d-%02d-%02d' % (year, month, day)
			num_hours_in_advance = 24
			forecast_channel = 'wf_sup'
			for target_hour in range(24):
				target_time = str_to_em('%s %02d:00' % (daystr, target_hour))
				check_weather_time = target_time - 1000*60*60*num_hours_in_advance
				observation_wind = 10; forecast_wind = observation_wind + target_hour
				insert_parsed_observation_into_db(Observation('envcan', target_time, observation_wind, -1))
				insert_parsed_forecast_into_db(Forecast(forecast_channel, check_weather_time, target_time, forecast_wind, -1))
			for target_hour in (t for t in get_target_times() if t != -1):
				data = get_data(target_hour, 24, datetime.date(year, month, day+1), 15)
				score = data['channel_to_score'][forecast_channel]
				expected_score = target_hour**2
				self.assertEqual(score, expected_score)
		finally:
			if delete_this_test_schemas_after:
				db_execute('DROP SCHEMA %s CASCADE' % schema_name)

	def create_and_use_db_schema_for_testing(self, delete_all_other_test_schemas_first_=False):
		schema_name_prefix = 'windgraphs_test_'
		if delete_all_other_test_schemas_first_:
			for i in xrange(100):
				schema_name = '%s%d' % (schema_name_prefix, i)
				try:
					db_execute('DROP SCHEMA %s CASCADE' % schema_name)
				except psycopg2.ProgrammingError:
					pass
		for i in xrange(100):
			schema_name = '%s%d' % (schema_name_prefix, i)
			try:
				db_execute('CREATE SCHEMA %s' % schema_name)
				break
			except psycopg2.ProgrammingError:
				pass
		else:
			raise Exception("Couldn't create test schema (starting with '%s').  Do too many exist already?" % schema_name_prefix)
		db_execute('SET search_path TO %s' % schema_name)
		return schema_name

@lock
@trans
def db_execute(sql_):
	curs = db_conn().cursor()
	try:
		curs.execute(sql_)
	finally:
		curs.close()

if __name__ == '__main__':

	pass


