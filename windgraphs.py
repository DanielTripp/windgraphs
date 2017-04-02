#!/usr/bin/env python

import sys, urllib2, json, pprint, re, datetime, os, threading, traceback, io, math, base64, StringIO, csv, tempfile, stat
import dateutil.parser, dateutil.tz
import BeautifulSoup, psycopg2, pytz
import matplotlib
matplotlib.use('Agg')
import matplotlib.dates
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import pylab
import numpy as np
from misc import *

with open('PARSED_WEATHER_CHANNELS.json') as fin:
	PARSED_WEATHER_CHANNELS = json.load(fin)
with open('WEATHER_CHANNEL_TO_COLOR.json') as fin:
	WEATHER_CHANNEL_TO_COLOR = json.load(fin)
with open('WEATHER_CHANNEL_TO_LONG_MULTILINE_NAME.json') as fin:
	WEATHER_CHANNEL_TO_LONG_MULTILINE_NAME = json.load(fin)

assert set(WEATHER_CHANNEL_TO_COLOR.keys()) == set(PARSED_WEATHER_CHANNELS) \
		== set(WEATHER_CHANNEL_TO_LONG_MULTILINE_NAME.keys())

PASSWORD = file_to_string(os.path.expanduser('~/.windgraphs/DB_PASSWORD')).strip()

JSON_DIR = 'static_graph_info'

DEV = os.path.exists('DEV')
DEV_READ_FROM_FILES = DEV and 0
DEV_WRITE_TO_FILES = DEV and 0

g_db_conn = None
g_lock = threading.RLock()


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


def windfindersuper_get_web_response():
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

def windfinderregular_get_web_response():
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

def windfinderregular_get_forecast_and_insert_into_db():
	web_response = windfinderregular_get_web_response()
	time_retrieved_em = now_em()
	insert_raw_forecast_into_db('wf_reg', web_response, time_retrieved_em)
	forecasts = windfinder_parse_web_response(web_response, 'wf_reg', time_retrieved_em)
	insert_parsed_forecasts_into_db(forecasts)

def windfindersuper_get_forecast_and_insert_into_db():
	web_response = windfindersuper_get_web_response()
	time_retrieved_em = now_em()
	insert_raw_forecast_into_db('wf_sup', web_response, time_retrieved_em)
	forecasts = windfinder_parse_web_response(web_response, 'wf_sup', time_retrieved_em)
	insert_parsed_forecasts_into_db(forecasts)

def windguru_get_forecast_and_insert_into_db():
	web_response = windguru_get_web_response()
	time_retrieved_em = now_em()
	insert_raw_forecast_into_db('wg', web_response, time_retrieved_em)
	forecasts = windguru_parse_web_response(web_response, time_retrieved_em)
	insert_parsed_forecasts_into_db(forecasts)

def parent(node_, n_):
	r = node_
	for i in xrange(n_):
		r = r.parent
	return r

# Possible bug - might not parse correctly forecast target times that are in next year 
# 
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
def windfinder_parse_web_response_by_lines(web_response_str_, weather_channel_, time_retrieved_):
	"""
	Return a list of Forecast objects. 
	The windfinder regular forecast and superforecast have different URLs but use the same HTML format. 
	"""
	fudge_for_dst = {'wf_reg':True, 'wf_sup':False}[weather_channel_]
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
			if fudge_for_dst and not is_in_dst(target_datetime):
				target_datetime += datetime.timedelta(hours=1)
			target_datetime_em = datetime_to_em(target_datetime)
			r.append(Forecast(weather_channel_, time_retrieved_, target_datetime_em, windspeed, windgusts))
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

def windfinder_parse_web_response(web_response_str_, weather_channel_, time_retrieved_):
	return windfinder_parse_web_response_by_lines(web_response_str_, weather_channel_, time_retrieved_)

def is_in_dst(dt_):
	assert isinstance(dt_, datetime.datetime)
	toronto_tzinfo = pytz.timezone('America/Toronto')
	dt_with_timezone = datetime.datetime.fromtimestamp(time.mktime(dt_.timetuple()), toronto_tzinfo)
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
								print 'Omitting WindGuru %s reading #%d (day=%s, hour=%s) on account of null data.  speed=%s, gusts=%s.' \
										% (model_to_weatherchannel[model], i, days[i], hours[i], speed, gusts)
								for l in (windspeeds, windgusts, days, hours):
									del l[i]
							elif speed is not None and gusts is None:
								print 'Fudging WindGuru %s reading #%d (day=%s, hour=%s) on account of null gusts.  Setting gusts to speed (%s).' \
										% (model_to_weatherchannel[model], i, days[i], hours[i], speed)
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
							fudge_for_dst = {'wg_gfs':True, 'wg_nam':True, 'wg_hrw':False}[weatherchannel]
							if fudge_for_dst and not is_in_dst(daytetyme):
								hour += 1
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
				r.append(Observation('gc.ca', time_retrieved, wind, gust))
	return r

def kmph_to_knots(kmph_):
	return kmph_*0.539957

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
			insert_parsed_forecast_into_db(curs, forecast)
	finally:
		curs.close()

def insert_parsed_forecast_into_db(curs_, forecast_):
	cols = [forecast_.weather_channel, forecast_.time_retrieved, em_to_str(forecast_.time_retrieved), forecast_.target_time, 
			em_to_str(forecast_.target_time), forecast_.base_wind, forecast_.gust_wind]
	curs_.execute('INSERT INTO wind_forecasts_parsed VALUES (%s,%s,%s,%s,%s,%s,%s)', cols)

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
		if channel_ == 'gc.ca':
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
		if weather_channel_ == 'wg':
			forecasts = windguru_parse_web_response(web_response, t)
		elif weather_channel_ in ('wf_reg', 'wf_sup'):
			forecasts = windfinder_parse_web_response(web_response, weather_channel_, t)
		else:
			raise Exception()
		for forecast in forecasts:
			print forecast

def get_this_month_and_last_dates():
	today = datetime.date.today()
	last_month_date = datetime.date(today.year, today.month, today.day)
	while last_month_date.month == today.month:
		last_month_date -= datetime.timedelta(1)
	return (today, last_month_date)

def get_observations_and_insert_into_db(channel_, dry_run_, printlevel_):
	if channel_ == 'gc.ca':
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
		insert_success = insert_raw_observation_into_db('gc.ca', web_response)
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

def get_all_forecasts_and_insert_into_db():
	try:
		windfinderregular_get_forecast_and_insert_into_db()
	except:
		traceback.print_exc()
	try:
		windfindersuper_get_forecast_and_insert_into_db()
	except:
		traceback.print_exc()
	try:
		windguru_get_forecast_and_insert_into_db()
	except:
		traceback.print_exc()

def get_forecast_near_time_retrieveds(weather_channel_, time_retrieved_approx_, target_time_, sooner_aot_later_, maxrows_, time_span_):
	assert isinstance(time_retrieved_approx_, long)
	assert isinstance(target_time_, long)
	sign = ('>=' if sooner_aot_later_ else '<=')
	order = ('asc' if sooner_aot_later_ else 'desc')
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

def get_near_time_retrieveds(table_, channel_, time_em_, sooner_aot_later_, maxrows_, time_span_):
	assert table_.startswith('wind_observations_')
	sign = ('>=' if sooner_aot_later_ else '<=')
	order = ('asc' if sooner_aot_later_ else 'desc')
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

def get_near_time_retrieved(table_, channel_, time_em_, sooner_aot_later_):
	r = get_near_time_retrieveds(table_, channel_, time_em_, sooner_aot_later_, 1, None)
	assert len(r) <= 1
	return (None if len(r) == 0 else r[0])

def get_nearest_raw_forecast_time_retrieved(weather_channel_, datestr_):
	t = str_to_em(datestr_)
	lt_time = get_raw_forecast_near_time_retrieved(weather_channel_, t-1, False)
	gt_time = get_raw_forecast_near_time_retrieved(weather_channel_, t,   True)
	return vote_on_nearest_time(t, lt_time, gt_time)

def get_raw_forecast_near_time_retrieved(weather_channel_, t_, sooner_aot_later_):
	sign = ('>=' if sooner_aot_later_ else '<=')
	order = ('asc' if sooner_aot_later_ else 'desc')
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
			return Observation('gc.ca', t_, base_wind, gust_wind)
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

def backfill_reparse_raw_forecast_in_db(weather_channel_, datestr_, fail_on_dupe_):
	t = get_nearest_raw_forecast_time_retrieved(weather_channel_, datestr_)
	if t is None:
		print 'No rows found'
	else:
		print t
		print em_to_str(t)
		web_response = get_raw_forecast_from_db(weather_channel_, t)
		if weather_channel_ == 'wg':
			forecasts = windguru_parse_web_response(web_response, t)
		elif weather_channel_ in ('wf_reg', 'wf_sup'):
			forecasts = windfinder_parse_web_response(web_response, weather_channel_, t)
		else:
			raise Exception('unknown weather channel')
		print 'Got %d forecasts.' % len(forecasts)
		for forecast in forecasts:
			print forecast
		num_minutes_tolerance = 10
		if do_any_parsed_forecasts_exist_near_time_retrieved(weather_channel_, t, 1000*60*num_minutes_tolerance):
			msg = ('Some parsed forecasts near that time (channel: %s, w/ time_retrieved within %d minutes of %s) '
						+'already exist in the database.') % (weather_channel_, num_minutes_tolerance, em_to_str(t))
			if fail_on_dupe_:
				raise Exception(msg)
			else:
				print msg
		else:
			insert_parsed_forecasts_into_db(forecasts)
			print 'Inserted forecasts OK.'

def do_any_parsed_forecasts_exist_near_time_retrieved(weather_channel_, t_, tolerance_):
	curs = db_conn().cursor()
	try:
		sqlstr = '''select time_retrieved from wind_forecasts_parsed where time_retrieved between %s and %s and 
				weather_channel like %s limit 1'''
		cols = [t_ - tolerance_, t_ + tolerance_, weather_channel_+'%']
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
				insert_parsed_forecast_into_db(curs2, forecast)
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
	return {15:14, 30:14, 90:42, 180:84, 365:170}[num_days_]

def get_graph_info(target_time_of_day_, weather_check_num_hours_in_advance_, end_date_, num_days_):
	target_time_of_day = datetime.time(target_time_of_day_, 00)

	main_figure = plt.figure(1)
	fig, ax = plt.subplots()
	fig.set_size_inches(get_graph_width_inches(num_days_), 8)

	days = get_days(end_date_, num_days_)
	target_times = [datetime_to_em(datetime.datetime.combine(target_day, target_time_of_day)) for target_day in days]
	forecast_channel_to_runs = defaultdict(lambda: [[]])
	observation_runs = [[]]
	for target_t in target_times:
		check_weather_t = target_t - 1000*60*60*weather_check_num_hours_in_advance_

		observation = get_observation_from_db('gc.ca', target_t)
		if observation is None:
			observation_runs.append([])
		else:
			observation_runs[-1].append((em_to_datetime(target_t), observation.base_wind))
			for channel in PARSED_WEATHER_CHANNELS:
				forecast = get_forecast_parsed_near(channel, check_weather_t, target_t)
				if forecast is None:
					forecast_channel_to_runs[channel].append([])
				else:
					forecast_channel_to_runs[channel][-1].append((em_to_datetime(target_t), forecast.base_wind))

	observation_runs = [e for e in observation_runs if len(e) > 0]

	for forecast_runs in forecast_channel_to_runs.itervalues():
		forecast_runs[:] = [e for e in forecast_runs if len(e) > 0]

	def xvals(run__):
		return [e[0] for e in run__]

	def yvals(run__):
		return [e[1] for e in run__]

	# Draw "actual wind" lines and dots: 
	observation_color = 'black'
	for run in observation_runs:
		plt.plot(xvals(run), yvals(run), color=observation_color, marker='o', markersize=7, 
				linestyle='solid', linewidth=1)

	# Draw forecast channel lines and dots: 
	for channel in forecast_channel_to_runs.keys():
		color = WEATHER_CHANNEL_TO_COLOR[channel]
		for forecast_run in forecast_channel_to_runs[channel]:
			xs = xvals(forecast_run)
			ys = yvals(forecast_run)
			plt.plot(xs, ys, color=color, marker='o', markeredgecolor=color, markersize=7,
					linestyle='solid', linewidth=1)

	# Kludge.  Making room for our weather channel names. 
	xlim_margin = {15:4, 30:6, 90:8, 180:8, 365:8}[num_days_]*24*60*60*1000
	plt.xlim(em_to_datetime(target_times[0]-xlim_margin), em_to_datetime(target_times[-1]+1000*60*60*24))

	# Draw date labels on X-axis:
	fig.autofmt_xdate()
	date_format = ('%b %d %Y' if end_date_ < datetime.date(1990, 1, 1) else '%b %d') # Include year for testing time frames 
	ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter(date_format))
	ax.xaxis.set_major_locator(matplotlib.ticker.FixedLocator(
			[pylab.date2num(em_to_datetime(x)) for x in target_times[::get_xaxis_tick_step(num_days_)]]))

	# Draw horizontal lines, lining up with y-axis intervals: 
	min_xval = observation_runs[0][0][0]
	max_yval = 1
	for observation_run in observation_runs:
		min_xval = min(min_xval, min(xvals(observation_run)))
		max_yval = max(max_yval, max(yvals(observation_run)))
	for forecast_runs in forecast_channel_to_runs.itervalues():
		for forecast_run in forecast_runs:
			min_xval = min(min_xval, min(xvals(forecast_run)))
			max_yval = max(max_yval, max(yvals(forecast_run)))
	max_yval += 1
	for y in range(0, max_yval+5, 5):
		plt.axhline(y, color=(0.5,0.5,0.5), alpha=0.5, linestyle='-')
	plt.yticks(np.arange(0, max_yval+5, 5)) # Do this /after/ the axhline() calls or else the min value might not be respected. 

	# Draw text labelling each forecast channel and "Actual wind":
	series_to_first_run = {}
	series_to_first_run['actual'] = observation_runs[0]
	for forecast_channel, runs in forecast_channel_to_runs.iteritems():
		if runs:
			series_to_first_run[forecast_channel] = runs[0]
	series_to_color = WEATHER_CHANNEL_TO_COLOR.copy()
	series_to_color['actual'] = observation_color
	series_to_name = WEATHER_CHANNEL_TO_LONG_MULTILINE_NAME.copy()
	series_to_name['actual'] = 'Actual wind'
	serieses_in_y_order = sorted(series_to_first_run.keys(), key=lambda s: series_to_first_run[s][0][1])
	for seriesi, series in enumerate(serieses_in_y_order):
		color = series_to_color[series]
		texty_fraction = (seriesi+1)/float(len(series_to_first_run)+1)
		texty = texty_fraction*max_yval
		first_run = series_to_first_run[series]
		text = series_to_name[series]
		label = ax.annotate(text, xy=first_run[0], xytext=(min_xval - datetime.timedelta(milliseconds=xlim_margin*0.9), texty),  
				arrowprops=dict(arrowstyle='-', linestyle='dotted', linewidth=2, color=color), 
				horizontalalignment='left', verticalalignment='center', weight=('bold' if series == 'actual' else 'normal'), 
				color=color, fontsize=10, family='serif')

	plt.ylabel('Average wind (knots)')

	buf = io.BytesIO()
	plt.savefig(buf, bbox_inches='tight')
	buf.seek(0)
	png_content = buf.read()
	png_content_base64 = base64.b64encode(png_content)
	main_figure.clf()
	plt.close()

	channel_to_score = get_channel_to_score(observation_runs, forecast_channel_to_runs)

	return {'png': png_content_base64, 'channel_to_score': channel_to_score, 
			'channel_to_num_forecasts': get_channel_to_num_forecasts(forecast_channel_to_runs)}

def get_channel_to_num_forecasts(forecast_channel_to_runs_):
	r = {}
	for channel, forecast_runs in forecast_channel_to_runs_.iteritems():
		r[channel] = sum(len(run) for run in forecast_runs)
	return r

def get_channel_to_score(observation_runs_, forecast_channel_to_runs_):
	observations = sum(observation_runs_, [])
	observation_datetime_to_val = {}
	for observation in observations:
		observation_datetime_to_val[observation[0]] = observation[1]
	channel_to_forecasts = {}
	for channel, runs in forecast_channel_to_runs_.iteritems():
		channel_to_forecasts[channel] = sum(runs, [])
	r = {}
	for channel, forecasts in channel_to_forecasts.iteritems():
		channel_score = 0
		for forecast in forecasts:
			forecast_datetime, forecast_val = forecast
			if forecast_datetime in observation_datetime_to_val:
				observation_val = observation_datetime_to_val[forecast_datetime]
				channel_score += (observation_val - forecast_val)**2
		if forecasts:
			channel_score /= len(forecasts)
			r[channel] = channel_score
		else:
			r[channel] = None
	return r

def get_xaxis_tick_step(num_days_):
	return int(math.ceil(get_range_val((20,1.0), (40,2.0), num_days_)))

def get_json_filename(target_time_, hours_in_advance_, graph_domain_num_days_):
	r = 'graph_info___target_time_%02d___hours_in_advance_%d___graph_domain_num_days_%d.json' \
			% (target_time_, hours_in_advance_, graph_domain_num_days_)
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
	with open(filename_) as fin:
		for line in fin:
			r.append(int(line.rstrip()))
	return r

def get_target_times():
	return get_file_contents_as_list_of_integers('target_times.txt')

def get_hours_in_advance():
	return get_file_contents_as_list_of_integers('hours_in_advance.txt')

def get_graph_domain_num_days():
	return get_file_contents_as_list_of_integers('graph_domain_num_days.txt')

if __name__ == '__main__':

	pass


