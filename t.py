#!/usr/bin/env python

import urllib2, json, pprint

if 1:
	url = 'http://widget.windguru.cz/int/widget_json.php?s=64&m=3&lng=en'
	resp = urllib2.urlopen(url).read()
	resp = resp.strip('(').strip(')')
	#with open('d-test-predictions', 'w') as fout:
	#	fout.write(resp)
else:
	with open('d-test-predictions') as fin:
		resp = fin.read()
data = json.loads(resp)
d2 = data['fcst']['fcst']['3']
windspeed = d2['WINDSPD']
windgusts = d2['GUST']
pprint.pprint(d2)



