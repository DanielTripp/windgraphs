import os, json

def read_var_from_json_file(var_name_):
	filename = os.path.join('config', '%s.json' % var_name_)
	with open(filename) as fin:
		globals()[var_name_] = json.load(fin)

read_var_from_json_file('FORECAST_PARSED_CHANNELS')
read_var_from_json_file('FORECAST_PARSED_CHANNEL_TO_LONG_MULTILINE_NAME')

for d in [FORECAST_PARSED_CHANNEL_TO_LONG_MULTILINE_NAME]:
	assert set(d.keys()) == set(FORECAST_PARSED_CHANNELS)

FORECAST_PARSED_CHANNEL_TO_SINGLE_LINE_HTML_NAME = {
		c: FORECAST_PARSED_CHANNEL_TO_LONG_MULTILINE_NAME[c].replace('\n', ' ') \
		for c in FORECAST_PARSED_CHANNEL_TO_LONG_MULTILINE_NAME}

METEOBLUE_DAYS = tuple(range(1, 7))
METEOBLUE_RAW_CHANNEL_PREFIX = 'mb-day'
METEOBLUE_DAY_TO_RAW_CHANNEL = dict((day, '%s%d' % (METEOBLUE_RAW_CHANNEL_PREFIX, day)) for day in METEOBLUE_DAYS)
METEOBLUE_RAW_CHANNELS = METEOBLUE_DAY_TO_RAW_CHANNEL.values()

# For sailfow, the list of _raw_ channel names is the same as the list of _parsed_ channel names. 
SAILFLOW_RAW_CHANNELS = ['sf_q', 'sf_nam12', 'sf_gfs', 'sf_nam3', 'sf_cmc']

FORECAST_RAW_CHANNELS = ['wf_reg', 'wf_sup', 'wg'] + SAILFLOW_RAW_CHANNELS + METEOBLUE_RAW_CHANNELS

FORECAST_RAW_CHANNEL_TO_PARSED = {
	'wf_reg': ['wf_reg'], 
	'wf_sup': ['wf_sup'], 
	'wg': ['wg_nam', 'wg_gfs', 'wg_hrw'], 
 	'sf_q': ['sf_q'], 
	'sf_nam12': ['sf_nam12'], 
	'sf_gfs': ['sf_gfs'], 
	'sf_nam3': ['sf_nam3'], 
	'sf_cmc': ['sf_cmc'],
	'mb-day1': ['mb'], 
	'mb-day2': ['mb'], 
	'mb-day3': ['mb'], 
	'mb-day4': ['mb'], 
	'mb-day5': ['mb'], 
	'mb-day6': ['mb']
}

assert set(FORECAST_RAW_CHANNEL_TO_PARSED.keys()) == set(FORECAST_RAW_CHANNELS)
assert set(sum(FORECAST_RAW_CHANNEL_TO_PARSED.values(), [])) == set(FORECAST_PARSED_CHANNELS)

