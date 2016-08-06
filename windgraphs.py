#!/usr/bin/env python

import sys, urllib2, json, pprint, re, datetime, os, threading
import dateutil.parser, dateutil.tz
import BeautifulSoup
import psycopg2
from misc import *

PASSWORD = file_to_string(os.path.expanduser('~/.windgraphs/DB_PASSWORD')).strip()

DEV = os.path.exists('DEV')
DEV_READ_FROM_FILES = DEV and 1
DEV_WRITE_TO_FILES = DEV and 0

g_db_conn = None
g_lock = threading.RLock()

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
		return 'Forecast(%s, %s, %s, wind=%d, gust=%d)' % \
				(self.weather_channel, em_to_str(self.time_retrieved), em_to_str(self.target_time), self.base_wind, self.gust_wind)

	def __repr__(self):
		return self.__str__()


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

def windfinderregular_get_forecast():
	web_response = windfinderregular_get_web_response()
	return windfinder_parse_web_response(web_response, 'wf_reg')

def parent(node_, n_):
	r = node_
	for i in xrange(n_):
		r = r.parent
	return r

def windfinder_parse_web_response(web_response_str_, weather_channel_, time_retrieved_):
	"""
	Return a list of Forecast objects. 
	The windfinder regular forecast and superforecast have different URLs but use the same HTML format. 
	"""
	# These lines seem to break BeautifulSoup parsing.  If we don't remove them, 
	# BeautifulSoup will silently omit the entire HTML body. 
	def keep(line__):
		return not('<!--[if' in line__ or '<![endif]' in line__)
	s = '\n'.join(x for x in web_response_str_.splitlines() if keep(x))

	r = []
	soup = BeautifulSoup.BeautifulSoup(s)
	for x in soup.findAll('div', {'class': 'speed'}):
		for y in x.findAll('span', {'class': 'units-ws'}):
			windspeed = int(y.string.strip())
			windgusts = int(parent(y, 4).findAll('div', {'class': re.compile('^data-gusts .*')})[0]\
					.findAll('span', {'class': 'units-ws'})[0].string)
			dayte = parent(y, 7).findAll('div', {'class': 'weathertable__header'}, recursive=False)[0].string.strip()
			dayte = re.sub('^.*? ', '', dayte)
			tyme = parent(y, 5).findAll('span', {'class': 'value'})[0].string
			cur_year = datetime.datetime.today().year
			daytetyme = datetime_to_em(datetime.datetime.strptime('%s %d %s:00' % (dayte, cur_year, tyme), '%b %d %Y %H:%M'))
			r.append(Forecast(weather_channel_, time_retrieved_, daytetyme, windspeed, windgusts))
	return r

def wg_get_web_response():
	if DEV_READ_FROM_FILES:
		with open('d-test-predictions-4') as fin:
			r = fin.read()
	else:
		url = 'http://www.windguru.cz/int/index.php?sc=64'
		r = urllib2.urlopen(url).read()
		if DEV_WRITE_TO_FILES:
			with open('d-test-predictions-4', 'w') as fout:
				fout.write(r)
	return r

def to_ints(strs_):
	return [int(x) for x in strs_]

def wg_parse_web_response(web_response_str_):
	soup = BeautifulSoup.BeautifulSoup(web_response_str_)
	# models: GFS = 3, NAM = 4, HRW = 38 
	desired_model = '3'
	for i, script_tag in enumerate(soup.findAll('script')):
		for c in script_tag.contents:
			s = c.string
			if 'var wg_fcst_tab_data' in s:
				json_str = re.search('{.*}', s).group(0)
				parsed_data = json.loads(json_str)
				if desired_model in parsed_data['fcst']:
					data = parsed_data['fcst'][desired_model]
					retrieved_datetime = data['update_last'].split(',')[1].lstrip()
					retrieved_datetime = ' '.join(retrieved_datetime.split(' ', 3)[:3])
					retrieved_datetime = datetime.datetime.strptime(retrieved_datetime, '%d %b %Y')
					retrieved_year = retrieved_datetime.year
					retrieved_month = retrieved_datetime.month
					retrieved_day = retrieved_datetime.day
					windspeeds = to_ints(data['WINDSPD'])
					windgusts = to_ints(data['GUST'])
					days = to_ints(data['hr_d'])
					hours = to_ints(data['hr_h'])
					assert len(windspeeds) == len(windgusts) == len(days) == len(hours) 
					for day, hour, windspeed in zip(days, hours, windspeeds):
						month = (retrieved_month if day >= retrieved_day else retrieved_month+1)
						daytetyme = datetime.datetime.strptime('%02d-%02d %02d:00 %d' % (month, day, hour, retrieved_year), '%m-%d %H:%M %Y')
						print daytetyme, windspeed 
				break

def wg_get_forecast():
	web_response = wg_get_web_response()
	return wg_parse_web_response(web_response)

def get_observations_web_response():
	if DEV_READ_FROM_FILES:
		with open('d-current-conditions') as fin:
			r = fin.read()
	else:
		url = 'http://atm.navcanada.ca/atm/iwv/CYTZ'
		r = urllib2.urlopen(url).read()
		if DEV_WRITE_TO_FILES:
			with open('d-current-conditions', 'w') as fout:
				fout.write(r)
	return r

class Observation(object):

	def __init__(self, time_retrieved_, base_wind_, gust_wind_):
		self.time_retrieved = time_retrieved_
		self.base_wind = base_wind_
		self.gust_wind = gust_wind_

	def __str__(self):
		return 'Observation(%s, wind=%d, gust=%d)' % (em_to_str(self.time_retrieved), self.base_wind, self.gust_wind)

	def __repr__(self):
		return self.__str__()

def parse_observation_web_response(web_response_):
	soup = BeautifulSoup.BeautifulSoup(web_response_)
	wind = None
	gust = None
	for x in soup.findAll('td', {'class': 'stat-cell'}):
		for content in x.contents:
			if 'Gusting' in content:
				gust = x.span.string
			elif 'Wind Speed' in content:
				wind = x.span.string
			elif 'Updated' in content:
				time_retrieved = x.span.string
	if gust == '--':
		gust = wind
	else:
		gust = gust.lstrip('G')
	time_retrieved = datetime_to_em(dateutil.parser.parse(time_retrieved).astimezone(dateutil.tz.tzlocal()))
	wind = int(wind)
	gust = int(gust)
	return Observation(time_retrieved, wind, gust)

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
	time_retrieved_em = now_em()
	time_retrieved_str = em_to_str(time_retrieved_em )
	for forecast in forecasts_:
		curs = db_conn().cursor()
		cols = [forecast.weather_channel, time_retrieved_em, time_retrieved_str, forecast.target_time, 
				em_to_str(forecast.target_time), forecast.base_wind, forecast.gust_wind]
		curs.execute('INSERT INTO wind_forecasts_parsed VALUES (%s,%s,%s,%s,%s,%s,%s)', cols)
		curs.close()

@lock
@trans
def insert_raw_observation_into_db(web_response_str_):
	curs = db_conn().cursor()
	time_em = now_em()
	time_str = em_to_str(time_em)
	cols = [time_em, time_str, web_response_str_]
	curs.execute('INSERT INTO wind_observations_raw VALUES (%s,%s,%s)', cols)
	curs.close()

@lock
@trans
def insert_parsed_observation_into_db(obs_):
	curs = db_conn().cursor()
	time_retrieved_str = em_to_str(obs_.time_retrieved)
	cols = [obs_.time_retrieved, time_retrieved_str, obs_.base_wind, obs_.gust_wind]
	curs.execute('INSERT INTO wind_observations_parsed VALUES (%s,%s,%s,%s)', cols)
	curs.close()

@lock
def get_raw_observation_from_db(time_retrieved_):
	sqlstr = 'select content from wind_observations_raw where time_retrieved = %d' % (time_retrieved_)
	curs = db_conn().cursor()
	curs.execute(sqlstr)
	all_vis = []
	for row in curs:
		content = row[0]
		r = content
		break
	else:
		raise Exception('no rows')
	curs.close()
	return r

def parse_observation_in_db(time_retrieved_):
	return parse_observation_web_response(get_raw_observation_from_db(time_retrieved_))

def get_observations_and_insert_into_db():
	web_response = get_observations_web_response()
	insert_raw_observation_into_db(web_response)
	parsed_observation = parse_observation_web_response(web_response)
	insert_parsed_observation_into_db(parsed_observation)

def get_forecasts_and_insert_into_db():
	pass

if __name__ == '__main__':

	pass


