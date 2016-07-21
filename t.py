#!/usr/bin/env python

import urllib2, json, pprint, re, datetime
import BeautifulSoup

def wf_get_web_response():
	if 0:
		url = 'https://www.windfinder.com/forecast/toronto_island'
		r = urllib2.urlopen(url).read()
		if 0:
			with open('d-test-predictions-wf', 'w') as fout:
				fout.write(r)
	else:
		with open('d-test-predictions-wf') as fin:
			r = fin.read()
	return r

def wf_get_forecast():
	web_response = wf_get_web_response()
	return wf_parse_web_response(web_response)

def parent(node_, n_):
	r = node_
	for i in xrange(n_):
		r = r.parent
	return r

def wf_parse_web_response(web_response_str_):
	# These lines seem to break BeautifulSoup parsing.  If we don't remove them, 
	# BeautifulSoup will silently omit the entire HTML body. 
	def keep(line__):
		return not('<!--[if' in line__ or '<![endif]' in line__)
	s = '\n'.join(x for x in web_response_str_.splitlines() if keep(x))

	soup = BeautifulSoup.BeautifulSoup(s)
	for x in soup.findAll('div', {'class': 'speed'}):
		for y in x.findAll('span', {'class': 'units-ws'}):
			windspeed = int(y.string.strip())
			dayte = parent(y, 7).findAll('div', {'class': 'weathertable__header'}, recursive=False)[0].string.strip()
			dayte = re.sub('^.*? ', '', dayte)
			tyme = parent(y, 5).findAll('span', {'class': 'value'})[0].string
			cur_year = datetime.datetime.today().year
			daytetyme = datetime.datetime.strptime('%s %d %s:00' % (dayte, cur_year, tyme), '%b %d %Y %H:%M')
			print daytetyme, windspeed 

def wgfrontpage_get_web_response():
	if 0:
		url = 'http://www.windguru.cz/int/index.php?sc=64'
		r = urllib2.urlopen(url).read()
		if 0:
			with open('d-test-predictions-4', 'w') as fout:
				fout.write(r)
	else:
		with open('d-test-predictions-4') as fin:
			r = fin.read()
	return r

def wgfrontpage_get_forecast_windspeed_from_web_response(web_response_str_, day_of_week_, hour_):
	desired_hourstr = '%02d' % hour_ 
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
					windspeed = data['WINDSPD']
					windgusts = data['GUST']
					days_of_week = data['hr_weekday']
					hours = data['hr_h']
					for i, (day_of_week, hour) in enumerate(zip(days_of_week, hours)):
						if day_of_week == day_of_week_ and hour == desired_hourstr:
							break
					else:
						raise Exception('day/hour not found')
					return windspeed[i]

def wgfrontpage_get_forecast_windspeed(day_of_week_, hour_):
	web_response = wgfrontpage_get_web_response()
	return wgfrontpage_get_forecast_windspeed_from_web_response(web_response, day_of_week_, hour_)

def wgwidget_get_web_response():
	if 1:
		url = 'http://widget.windguru.cz/int/widget_json.php?s=64&m=3&lng=en'
		r = urllib2.urlopen(url).read()
		r = r.strip('(').strip(')')
		if 0:
			with open('d-test-predictions-3', 'w') as fout:
				fout.write(r)
	else:
		with open('d-test-predictions-3') as fin:
			r = fin.read()
	return r

def wgwidget_get_forecast_windspeed_from_web_response(web_response_str_, day_of_week_, hour_):
	parsed_response = json.loads(web_response_str_)
	data = parsed_response['fcst']['fcst']['3']
	windspeed = data['WINDSPD']
	windgusts = data['GUST']
	days_of_week = data['hr_weekday']
	hours = data['hr_h']
	for i, (day_of_week, hour) in enumerate(zip(days_of_week, hours)):
		if day_of_week == day_of_week_ and hour == hour_:
			break
	else:
		raise Exception('day/hour not found')
	return windspeed[i]
	#pprint.pprint(days_of_week)

def wgwidget_get_forecast_windspeed(day_of_week_, hour_):
	web_response = wgwidget_get_web_response()
	return wgwidget_get_forecast_windspeed_from_web_response(web_response, day_of_week_, hour_)

print wf_get_forecast()


