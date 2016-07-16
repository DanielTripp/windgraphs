#!/usr/bin/env python

import urllib2, json, pprint

url = 'http://widget.windguru.cz/int/widget_json.php?s=64&m=3&lng=en'
resp = urllib2.urlopen(url).read()
resp = resp.strip('(').strip(')')
data = json.loads(resp)
pprint.pprint(data)





