#!/usr/bin/env python

import sys, urllib2, json, pprint, re, datetime
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

def wg_get_web_response():
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

def get_current_conditions_web_response():
	if 1:
		with open('d-current-conditions') as fin:
			r = fin.read()
		return r
	url = 'http://atm.navcanada.ca/atm/iwv/CYTZ'
	r = urllib2.urlopen(url).read()
	if 0:
		with open('d-current-conditions', 'w') as fout:
			fout.write(r)
	return r

def parse_current_conditions_web_response(web_response_):
	soup = BeautifulSoup.BeautifulSoup(web_response_)
	wind = None
	gust = None
	for x in soup.findAll('td', {'class': 'stat-cell'}):
		for content in x.contents:
			if 'Gusting' in content:
				gust = x.span.string
			elif 'Wind Speed' in content:
				wind = x.span.string
	if gust == '--':
		gust = wind
	wind = int(wind)
	gust = int(gust)
	print wind, gust 

def get_current_conditions():
	web_response = get_current_conditions_web_response()
	parse_current_conditions_web_response(web_response)

if __name__ == '__main__':

	pass


