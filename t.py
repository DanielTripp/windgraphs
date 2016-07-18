#!/usr/bin/env python

import urllib2, json, pprint

def wg_get_web_response():
	if 0:
		url = 'http://widget.windguru.cz/int/widget_json.php?s=64&m=3&lng=en'
		r = urllib2.urlopen(url).read()
		r = resp.strip('(').strip(')')
		if 0:
			with open('d-test-predictions-3', 'w') as fout:
				fout.write(r)
	else:
		with open('d-test-predictions-3') as fin:
			r = fin.read()
	return r

def wg_get_forecast_windspeed_from_web_response(web_response_str_, day_of_week_, hour_):
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

def wg_get_forecast_windspeed(day_of_week_, hour_):
	web_response = wg_get_web_response()
	return wg_get_forecast_windspeed_from_web_response(web_response, day_of_week_, hour_)

print wg_get_forecast_windspeed(1, '11')

