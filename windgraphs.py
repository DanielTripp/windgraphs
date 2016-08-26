#!/usr/bin/env python

import sys, urllib2, json, pprint, re, datetime, os, threading, traceback
import dateutil.parser, dateutil.tz
import BeautifulSoup
import psycopg2
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mpldates # tdr?   not used? 
import matplotlib.ticker as ticker
import matplotlib.transforms # tdr?  not used? 
from misc import *

PARSED_WEATHER_CHANNELS = ['wf_reg', 'wf_sup', 'wg_gfs', 'wg_nam', 'wg_hrw'] 
WEATHER_CHANNEL_TO_COLOR = {'wf_reg':(0.6,0,0.1), 'wf_sup':(0.4,0,0.2), 
		'wg_gfs':(0,0,0.5), 'wg_nam':(0.2,0.3,0.6), 'wg_hrw':(0.2,0.4,0.6)}
assert set(WEATHER_CHANNEL_TO_COLOR.keys()) == set(PARSED_WEATHER_CHANNELS)

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
		return 'Forecast(%s, %s, %s, wind=%2d, gust=%2d)' % \
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
						retrieved_datetime = data['update_last'].split(',')[1].lstrip()
						retrieved_datetime = ' '.join(retrieved_datetime.split(' ', 3)[:3])
						retrieved_datetime = datetime.datetime.strptime(retrieved_datetime, '%d %b %Y')
						retrieved_year = retrieved_datetime.year
						retrieved_month = retrieved_datetime.month
						retrieved_day = retrieved_datetime.day
						windspeeds = data['WINDSPD']
						windgusts = data['GUST']
						days = to_ints(data['hr_d'])
						day_retrieved = retrieved_datetime.day
						# Sometimes data for days before today is included, and sometimes 
						# some of the speed / gust data for in those days is null.  eg.  
						# 2016-08-17 13:00.  We could ignore the null data.  But instead we 
						# ignore data for days before today.  
						for cutoff_idx, day in enumerate(days):
							if day == day_retrieved:
								break
						days = days[cutoff_idx:]
						hours = to_ints(data['hr_h'][cutoff_idx:])
						windspeeds = to_ints(windspeeds[cutoff_idx:])
						windgusts = to_ints(windgusts[cutoff_idx:])
						assert len(windspeeds) == len(windgusts) == len(days) == len(hours) 
						for day, hour, windspeed, windgust in zip(days, hours, windspeeds, windgusts):
							month = (retrieved_month if day >= retrieved_day else retrieved_month+1)
							daytetyme = datetime.datetime.strptime('%02d-%02d %02d:00 %d' % (month, day, hour, retrieved_year), '%m-%d %H:%M %Y')
							target_time = datetime_to_em(daytetyme)
							r.append(Forecast(model_to_weatherchannel[model], time_retrieved_, target_time, windspeed, windgust))
				break
	return r

def zip_filter(lists_, func_):
	assert len(set(len(l) for l in lists_)) == 1
	keep = [all(func_(l[i]) for l in lists_) for i in range(len(lists_[0]))]
	for l in lists_:
		l[:] = [e for i, e in enumerate(l) if keep[i]]

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
		return 'Observation(%s, wind=%2d, gust=%2d)' % (em_to_str(self.time_retrieved), self.base_wind, self.gust_wind)

	def __repr__(self):
		return self.__str__()

# Unlike forecasts, we get a "time retrieved" from the web content on parse 
# here, so we insert that into the "parsed observations" table, so the "time 
# retrieved" values will not match between the "raw observations" and "parsed 
# observations" table.  It's unclear if there are any strong reasons for this.  
def parse_observation_web_response(web_response_):
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
	for forecast in forecasts_:
		curs = db_conn().cursor()
		cols = [forecast.weather_channel, forecast.time_retrieved, em_to_str(forecast.time_retrieved), forecast.target_time, 
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

def get_raw_observation_from_db(t_):
	sqlstr = 'select content from wind_observations_raw where time_retrieved = %d' % (t_)
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

def print_parsed_observation_from_db(datestr_):
	t = get_nearest_time_retrieved('wind_observations_raw', datestr_)
	if t is None:
		print 'No rows found'
	else:
		content = get_raw_observation_from_db(t)
		print t
		print em_to_str(t)
		print 
		print parse_observation_web_response(content)

def print_parsed_forecasts_from_db(weather_channel_, datestr_):
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

def get_observations_and_insert_into_db():
	web_response = get_observations_web_response()
	insert_raw_observation_into_db(web_response)
	parsed_observation = parse_observation_web_response(web_response)
	insert_parsed_observation_into_db(parsed_observation)

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
	table = 'wind_forecasts_parsed'
	sqlstr = '''select time_retrieved from %s where target_time = %d and time_retrieved %s %d and weather_channel = '%s' 
			order by time_retrieved %s limit %d''' % (table, target_time_, sign, time_retrieved_approx_, weather_channel_, 
			order, maxrows_)
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

def get_near_time_retrieveds(table_, time_em_, sooner_aot_later_, maxrows_, time_span_):
	sign = ('>=' if sooner_aot_later_ else '<=')
	order = ('asc' if sooner_aot_later_ else 'desc')
	sqlstr = '''select time_retrieved from %s  
			where time_retrieved %s %d order by time_retrieved %s limit %d''' % (table_, sign, time_em_, order, maxrows_)
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

def get_nearest_time_retrieveds(table_, time_em_, maxrows_each_side_, time_span_each_side_):
	less_thans = get_near_time_retrieveds(table_, time_em_, False, maxrows_each_side_, time_span_each_side_)
	greater_thans = get_near_time_retrieveds(table_, time_em_, True, maxrows_each_side_, time_span_each_side_)
	r = list(reversed(less_thans)) + greater_thans
	return r

def get_near_time_retrieved(table_, time_em_, sooner_aot_later_):
	r = get_near_time_retrieveds(table_, time_em_, sooner_aot_later_, 1, None)
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

def get_nearest_time_retrieved(table_, datestr_):
	time_em = str_to_em(datestr_)
	lt_time = get_near_time_retrieved(table_, time_em-1, False)
	gt_time = get_near_time_retrieved(table_, time_em, True)
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
	
def print_raw_observation_from_db(datestr_):
	t = get_nearest_time_retrieved('wind_observations_raw', datestr_)
	if t is None:
		print 'No rows found'
	else:
		content = get_raw_observation_from_db(t)
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
		print t
		print em_to_str(t)
		print 
		print content

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


def get_averaged_observation_from_db(t_):
	assert isinstance(t_, long)
	obs_times = get_nearest_time_retrieveds('wind_observations_parsed', t_, 3, 1000*60*25)
	base_winds = []
	gust_winds = []
	for obs_time in obs_times:
		sqlstr = 'select base_wind, gust_wind from wind_observations_parsed where time_retrieved = %d' % (obs_time)
		curs = db_conn().cursor()
		try:
			curs.execute(sqlstr)
			row = curs.next()
			base_winds.append(row[0])
			gust_winds.append(row[1])
		finally:
			curs.close()
	assert len(base_winds) == len(gust_winds)
	if len(base_winds) == 0:
		return None
	else:
		return Observation(t_, int(average(base_winds)), max(gust_winds))

def get_days(start_date_, num_days_):
	r = []
	r.append(start_date_)
	for i in xrange(num_days_-1):
		r.append(r[-1] - datetime.timedelta(1))
	r = r[::-1]
	return r

def get_averaged_observations_from_db(target_time_, start_date_, num_days_):
	assert isinstance(target_time_, datetime.time)
	assert isinstance(start_date_, datetime.date)
	r = {}
	for dayte in dates(start_date_, num_days_):
		daytetyme = datetime.datetime.combine(dayte, target_time_)
		observation = get_averaged_observation_from_db(datetime_to_em(daytetyme))
		if observation is not None:
			r[daytetyme] = observation
	return r

def get_forecast_parsed(weather_channel_, time_retrieved_exact_, target_time_):
	sqlstr = '''select base_wind, gust_wind from wind_forecasts_parsed where target_time = %d and time_retrieved = %d 
			and weather_channel = '%s' ''' % (target_time_, time_retrieved_exact_, weather_channel_)
	curs = db_conn().cursor()
	try:
		curs.execute(sqlstr)
		for row in curs:
			base_wind, gust_wind = row
			break
		else:
			raise Exception()
	finally:
		curs.close()
	r = Forecast(weather_channel_, time_retrieved_exact_, target_time_, base_wind, gust_wind)
	return r

def backfill_reparse_raw_forecast_in_db(weather_channel_, datestr_):
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
			raise Exception('unknown weather channel')
		print 'Got %d forecasts.' % len(forecasts)
		for forecast in forecasts:
			print forecast
		if do_any_parsed_forecasts_exist_near_time_retrieved(weather_channel_, t, 1000*60*10):
			raise Exception('Some parsed forecasts near that time already exist in the database.')
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

def t_plot(): # tdr 
	target_time_of_day = datetime.time(17, 00)
	weather_check_hours_in_advance = 28
	num_target_days = 20

	plt.figure(1)
	fig, ax = plt.subplots()
	fig.set_size_inches(15, 8)

	days = get_days(datetime.date.today(), num_target_days)
	target_times = [datetime_to_em(datetime.datetime.combine(target_day, target_time_of_day)) for target_day in days]
	channel_to_xvals = defaultdict(lambda: [])
	channel_to_yvals = defaultdict(lambda: [])
	observation_xvals = []
	observation_yvals = []
	for target_t in target_times:
		check_weather_t = target_t - 1000*60*60*weather_check_hours_in_advance

		print 'target time:', em_to_str(target_t)
		observation = get_averaged_observation_from_db(target_t)
		if observation is not None:
			observation_xvals.append(em_to_datetime(target_t))
			observation_yvals.append(observation.base_wind)
			for channel in PARSED_WEATHER_CHANNELS:
				print channel 
				time_retrieved = get_forecast_nearest_time_retrieved(channel, check_weather_t, target_t)
				if time_retrieved is not None:
					forecast = get_forecast_parsed(channel, time_retrieved, target_t)
					channel_to_xvals[channel].append(em_to_datetime(target_t))
					channel_to_yvals[channel].append(forecast.base_wind)
		print '---'

	for channel in channel_to_xvals.keys():
		color = WEATHER_CHANNEL_TO_COLOR[channel]
		plt.plot(channel_to_xvals[channel], channel_to_yvals[channel], color=color, 
				marker='o', markeredgewidth=6, markeredgecolor=color, linestyle='solid', linewidth=4)

	plt.plot(observation_xvals, observation_yvals, color='black', marker='o', markeredgewidth=6, 
			linestyle='solid', linewidth=6)

	plt.xlim(em_to_datetime(target_times[0]-1000*60*60*24), em_to_datetime(target_times[-1]+1000*60*60*24))

	fig.autofmt_xdate()

	out_png_filename = 'd-plot.png'
	output_directory = '.'
	plt.savefig(os.path.join(output_directory, out_png_filename), bbox_inches='tight')

if __name__ == '__main__':

	pass


