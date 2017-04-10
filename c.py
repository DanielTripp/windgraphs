import json

def read_var_from_json_file(var_name_):
	filename = '%s.json' % var_name_
	with open(filename) as fin:
		globals()[var_name_] = json.load(fin)

read_var_from_json_file('FORECAST_PARSED_CHANNELS')
read_var_from_json_file('FORECAST_PARSED_CHANNEL_TO_COLOR')
read_var_from_json_file('WEATHER_CHANNEL_TO_MARKER')
read_var_from_json_file('FORECAST_MARKER_SIZE')
read_var_from_json_file('FORECAST_MARKER_EDGE_WIDTH')
read_var_from_json_file('WEATHER_CHANNEL_TO_LONG_MULTILINE_NAME')
read_var_from_json_file('OBSERVATION_COLOR')
read_var_from_json_file('OBSERVATION_MARKER')
read_var_from_json_file('OBSERVATION_MARKER_SIZE')
read_var_from_json_file('OBSERVATION_MARKER_EDGE_WIDTH')

assert set(FORECAST_PARSED_CHANNEL_TO_COLOR.keys()) == set(FORECAST_PARSED_CHANNELS) \
		== set(WEATHER_CHANNEL_TO_LONG_MULTILINE_NAME.keys())

METEOBLUE_DAYS = tuple(range(1, 7))
METEOBLUE_RAW_CHANNEL_PREFIX = 'mb-day'
METEOBLUE_DAY_TO_RAW_CHANNEL = dict((day, '%s%d' % (METEOBLUE_RAW_CHANNEL_PREFIX, day)) for day in METEOBLUE_DAYS)
METEOBLUE_RAW_CHANNELS = METEOBLUE_DAY_TO_RAW_CHANNEL.values()

# For sailfow, the list of _raw_ channel names is the same as the list of _parsed_ channel names. 
SAILFLOW_RAW_CHANNELS = ['sf_q', 'sf_nam12', 'sf_gfs', 'sf_nam3', 'sf_cmc']

FORECAST_RAW_CHANNELS = ['wf_reg', 'wf_sup', 'wg'] + SAILFLOW_RAW_CHANNELS + METEOBLUE_RAW_CHANNELS

