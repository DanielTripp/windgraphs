#!/usr/bin/env python

import sys, os, os.path, time, math, datetime, calendar, bisect, tempfile, subprocess, StringIO, re, multiprocessing, heapq, random, functools, traceback
import profile, cProfile
from collections import Sequence, MutableSequence, defaultdict, MutableSet
from itertools import *
import pytz, dateutil.tz

# Workaround for http://bugs.python.org/issue7980 
time.strptime("2013-06-02", "%Y-%m-%d")

def es_to_str(t_):
	if t_ is None or t_ == 0:
		return None
	else:
		return em_to_str(long(t_*1000))

def em_to_str(t_):
	if t_ is None or t_ == 0:
		return None
	else:
		return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(t_/1000))

def em_to_str_ymdhms(t_):
	return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(t_/1000))

def em_to_str_ymdhm(t_):
	return time.strftime('%Y-%m-%d %H:%M', time.localtime(t_/1000))

def em_to_str_millis(t_):
	format = '%Y-%m-%d %H:%M:%S'
	secs_formatted = time.strftime(format, time.localtime(t_/1000))
	millis = t_ - time.mktime(time.strptime(secs_formatted, format))*1000  # Hack.
	return '%s.%03d' % (secs_formatted, millis)

def em_to_str_ymd(t_):
	return time.strftime('%Y-%m-%d', time.localtime(t_/1000))

def em_to_str_hm(t_):
	return time.strftime('%H:%M', time.localtime(t_/1000))

def em_to_str_hms(t_):
	return time.strftime('%H:%M:%S', time.localtime(t_/1000))

def now_em():
	return int(time.time()*1000)

def current_year():
	return int(time.strftime('%Y', time.localtime(now_em()/1000)))

def now_str():
	return em_to_str(now_em())

def now_str_millis():
	return em_to_str_millis(now_em())

def now_str_ymd():
	return em_to_str_ymd(now_em())

def frange(min_, max_, step_):
	x = min_
	while x < max_:
		yield x
		x += step_

def lrange(min_, max_, step_):
	assert step_ != 0
	x = min_
	while (x < max_ if step_ > 0 else x > max_):
		yield x
		x += step_

def m_to_str(m_):
	return '%.2f minutes' % (m_/(1000*60.0))

# eg. given [1, 2, 3, 4], this yields (1, 2), then (2, 3), then (3, 4) 
def hopscotch(iterable_, n=2, step=1):
	assert n >= 2
	it = iter(iterable_)
	try:
		e = ()
		for i in range(n):
			e += (it.next(),)
		while True:
			yield e
			for i in xrange(step):
				e = e[1:] + (it.next(),)
	except StopIteration:
		pass

# eg. given ['a', 'b', 'c', 'd'], this yields (0, 'a', 1, 'b'), then (1, 'b', 2, 'c'), then (2, 'c', 3, 'd')
def hopscotch_enumerate(iterable_, n=2, reverse=False):
	assert n >= 2
	if reverse:
		if not isinstance(iterable_, Sequence):
			raise Exception()
		for i in xrange(len(iterable_)-n, -1, -1):
			yield sum(((j, iterable_[j]) for j in xrange(i, i+n)), ())
	else:
		it = iter(iterable_)
		try:
			e = ()
			for i in range(n):
				e += (i, it.next())
			i = n
			while True:
				yield e
				e = e[2:] + (i, it.next(),)
				i += 1
		except StopIteration:
			pass

# This is the counterpart to common.js - encode_url_paramval(). 
def decode_url_paramval(str_):
	r = ''
	for i in range(0, len(str_), 2):
		group = ord(str_[i]) - ord('a')
		sub = int(str_[i+1])
		result_char = chr(group*10 + sub)
		r += result_char
	return r

def str_to_em(datetimestr_, format_=None):
	def impl(str__, format__):
		return int(time.mktime(time.strptime(str__, format__))*1000)
	if format_ is None:
		if len(datetimestr_) == 23 and datetimestr_[-4] == '.':
			try:
				return impl(datetimestr_[:-4], '%Y-%m-%d %H:%M:%S') + int(datetimestr_[-3:])
			except ValueError:
				pass
		for f in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d', '%Y-%m', '%Y']:
			try:
				return impl(datetimestr_, f)
			except ValueError:
				pass
		else:
			raise Exception('The date/time "%s" did not match any of the formats that this function recognizes.' % datetimestr_)
	else:
		return impl(datetimestr_, format_)

def printerr(*args):
	sys.stderr.write(' '.join((str(x) for x in args)) + os.linesep)

def is_sorted(iterable_, reverse=False, key=None):
	def get_key(elem__):
		return (elem__ if key==None else key(elem__))
	for a, b in hopscotch(iterable_):
		akey = get_key(a); bkey = get_key(b)
		if (akey < bkey if reverse else akey > bkey):
			return False
	return True

def filter_in_place(list_, predicate_):
	assert isinstance(list_, MutableSequence)
	list_[:] = (e for e in list_ if predicate_(e))

def none(iterable_):
	for e in iterable_:
		if e:
			return False
	return True

def implies(a_, b_):
	return not (a_ and not b_)

def fdiv(x_, y_):
	return int(math.floor(x_/y_))

# 'i' is for 'inclusive'
def intervalii(a_, b_):
	assert (isinstance(a_, int) or isinstance(a_, long)) and (isinstance(b_, int) or isinstance(b_, long))
	if a_ < b_:
		start = a_
		end = b_
	else:
		start = b_
		end = a_
	return range(start, end+1)


def get_range_val(p1_, p2_, domain_val_):
	x1 = float(p1_[0]); y1 = float(p1_[1])
	x2 = float(p2_[0]); y2 = float(p2_[1])
	if abs(x2 - x1) < 0.000000001: # special case - would normally cause a divide-by-zero error - but we'll let the caller 
			# get away with it sometimes: 
		if abs(y2 - y1) < 0.0000000001 and abs(domain_val_ - x1) < 0.0000000001:
			return y1
		else:
			raise ZeroDivisionError()
	r = (y2 - y1)*(domain_val_ - x1)/(x2 - x1) + y1
	if any(type(x) == float for x in p1_ + p2_ + (domain_val_,)): # are any arguments floats?
		return r
	elif any(type(x) == long for x in p1_ + p2_ + (domain_val_,)): # are any arguments longs?
		return long(r)
	else:
		return int(r)

def avg(lo_, hi_, ratio_=0.5):
	r = lo_ + (hi_ - lo_)*ratio_
	if type(lo_) == int and type(hi_) == int:
		return int(r)
	elif type(lo_) == long or type(hi_) == long:
		return long(r)
	else:
		return r

def average(seq_):
	num_elems = 0
	sum = 0
	for e in seq_:
		sum += e
		num_elems += 1
	return sum/float(num_elems)

def file_under_key(list_, key_, assume_no_duplicate_keys_=False):
	assert callable(key_)
	if assume_no_duplicate_keys_:
		r = {}
		for e in list_:
			key = key_(e)
			if key in r:
				raise Exception('duplicate key "%s" found' % key)
			r[key] = e
		return r
	else:
		r = defaultdict(lambda: [])
		for e in list_:
			r[key_(e)].append(e)
		return dict(r)

# Return only elements for which predicate is true.  (It's a two-argument predicate.  It takes two elements.)
# Group them as they appeared in input list as runs of trues.
def get_maximal_sublists2(list_, predicate_):
	cur_sublist = None
	r = []
	for e1, e2 in hopscotch(list_):
		if predicate_(e1, e2):
			if cur_sublist is None:
				cur_sublist = [e1]
				r.append(cur_sublist)
			cur_sublist.append(e2)
		else:
			cur_sublist = None
	return r

# Return all input elements, but group them by runs of the same key.
def get_maximal_sublists3(list_, key_, returnidxes=False, keybyindex=False):
	assert callable(key_)
	if not list_:
		return list_
	cur_sublist = [0 if returnidxes else list_[0]]
	r = [cur_sublist]
	prev_elem_key = key_(0 if keybyindex else list_[0])
	for previ, curi in hopscotch(range(len(list_))):
		prev_elem = list_[previ]; cur_elem = list_[curi]
		cur_elem_key = key_(curi if keybyindex else cur_elem)
		if prev_elem_key == cur_elem_key:
			cur_sublist.append(curi if returnidxes else cur_elem)
		else:
			cur_sublist = [curi if returnidxes else cur_elem]
			r.append(cur_sublist)
		prev_elem_key = cur_elem_key
	return r

def uniq(seq_):
	first_elem = True
	prev_val = None
	r = []
	for e in seq_:
		if first_elem or (e != prev_val):
			r.append(e)
		prev_val = e
		first_elem = False
	return r

def mofrs_to_dir(start_mofr_, dest_mofr_):
	assert isinstance(start_mofr_, int) and isinstance(dest_mofr_, int)
	if start_mofr_ == -1 or dest_mofr_ == -1:
		return None
	elif dest_mofr_ > start_mofr_:
		return 0
	elif dest_mofr_ < start_mofr_:
		return 1
	else:
		return None

# param round_step_millis_ if 0, don't round down.  (Indeed, don't round at all.) 
def massage_time_arg(time_, round_step_millis_=0):
	if isinstance(time_, str):
		r = str_to_em(time_)
	elif time_==0:
		r = now_em()
	else:
		r = time_
	if round_step_millis_ != 0:
		r = round_down(r, round_step_millis_)
	return r

# 'off step' means 'steps shifted in phase by half the period, if you will'  
def round_up_off_step(x_, step_):
	r = round_down_off_step(x_, step_)
	return r if r == x_ else r+step_

def round_down_off_step(x_, step_):
	assert type(x_) == int and type(step_) == int
	return ((x_-step_/2)/step_)*step_ + step_/2

def round_up(x_, step_, ref_=0):
	r = round_down(x_, step_, ref_)
	if isinstance(x_, float):
		return r if abs(r - x_) < 0.00001 else r+step_
	else:
		return r if r == x_ else r+step_

def round_down(x_, step_, ref_=0):
	assert type(x_) in (int, long, float)
	x = x_ - ref_
	if type(x) in (int, long):
		r = (long(x)/step_)*step_
		if type(x) is int:
			r = int(r)
	else:
		r = fdiv(x, step_)*step_
	r += ref_
	return r

def roundbystep(x_, step_):
	rd = round_down(x_, step_)
	ru = round_up(x_, step_)
	return (rd if x_ - rd < ru - x_ else ru)

def first(iterable_, predicate_=None):
	for e in iterable_:
		if predicate_ is None or predicate_(e):
			return e
	return None

def firstidx(iterable_, predicate_):
	for i, e in enumerate(iterable_):
		if predicate_(e):
			return i
	raise Exception('Predicate was false for all elements.')

def round_down_by_minute(t_em_):
	dt = datetime.datetime.fromtimestamp(t_em_/1000.0)
	dt = datetime.datetime(dt.year, dt.month, dt.day, dt.hour, dt.minute) # Omitting second on purpose.  That's what
			# does the rounding down.
	r = datetime_to_em(dt)
	return r

def round_down_by_minute_step(t_em_, step_):
	dt = datetime.datetime.fromtimestamp(t_em_/1000.0)
	dt = datetime.datetime(dt.year, dt.month, dt.day, dt.hour, round_down(dt.minute, step_)) # Omitting second on purpose.  That's what
			# does the rounding down by minute.
	r = long(calendar.timegm(dt.timetuple())*1000)
	return r

def date_to_em(datetime_):
	return long(time.mktime(datetime_.timetuple())*1000)

def datetime_to_em(datetime_):
	return long(time.mktime(datetime_.timetuple())*1000) + datetime_.microsecond/1000

def em_to_datetime(em_):
	return datetime.datetime.fromtimestamp(em_/1000.0)

def round_up_by_minute(t_em_):
	dt = datetime.datetime.fromtimestamp(t_em_/1000.0)
	dt = datetime.datetime(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second)
	if dt.second > 0 or (0 < t_em_ - round_down_by_minute(t_em_) < 1000):
		dt -= datetime.timedelta(seconds=dt.second)
		dt += datetime.timedelta(minutes=1)
	r = datetime_to_em(dt)
	return r

def betweenii(a_, b_, c_):
	return (a_ <= b_ <= c_) or (c_ <= b_ <= a_)

# maintains a list of sorted keys available through sortedkeys().  also a floor*() method.
class sorteddict(dict):

	_pop_default_arg_not_supplied_sentinel_object = object()

	def __init__(self, *args, **kwargs):
		dict.__init__(self, *args, **kwargs)
		self.refresh_sortedkeys()

	# Making this a tuple because we don't want to have to make and return a copy in sortedkeys(), 
	# because that was too slow (took cumulatively half a second in a simple path-finding test case.)
	def refresh_sortedkeys(self):
		self._sortedkeys = tuple(sorted(self.keys()))

	def __setitem__(self, key, value):
		dict.__setitem__(self, key, value)
		self.refresh_sortedkeys()

	def __delitem__(self, key):
		dict.__delitem__(self, key)
		self.refresh_sortedkeys()

	def clear(self):
		dict.clear(self)
		self.refresh_sortedkeys()

	def copy(self):
		return sorteddict([(k, v) for k, v in self.iteritems()])

	def pop(self, key, default=_pop_default_arg_not_supplied_sentinel_object):
		try:
			return dict.pop(self, key)
		finally:
			self.refresh_sortedkeys()

	def popitem(self):
		try:
			return dict.popitem(self)
		finally:
			self.refresh_sortedkeys()

	def setdefault(self, key, default=None):
		try:
			return dict.setdefault(key, default)
		finally:
			self.refresh_sortedkeys()

	def sortedkeys(self):
		return self._sortedkeys

	def values_sorted_by_key(self):
		return [self[k] for k in self.sortedkeys()]

	def ceilitem(self, key_):
		assert len(self) == len(self._sortedkeys)
		if not self:
			raise KeyError('Can\'t call ceilitem on an empty sorteddict.')
		idx = bisect.bisect_left(self._sortedkeys, key_)
		if idx == len(self):
			raise KeyError('No key greater than or equal to "%s" was found in this sorteddict.' % key_)
		rkey = self._sortedkeys[idx]
		rval = self[rkey]
		return (rkey, rval)

	def flooritem(self, key_):
		assert len(self) == len(self._sortedkeys)
		if not self:
			raise KeyError('Can\'t call flooritem on an empty sorteddict.')
		idx = bisect.bisect_right(self._sortedkeys, key_)-1
		if idx < 0:
			raise KeyError('No key less than or equal to "%s" was found in this sorteddict.' % key_)
		rkey = self._sortedkeys[idx]
		rval = self[rkey]
		return (rkey, rval)

	# Returns items in the list immediately lesser and greater than given key.
	# If key arg exists in this dict, it is not returned.
	# eg. self = {0: '', 5: '', 10: ''}. boundingitems(5) = ((0, ''), (10, '')).  boundingitems(6) = ((5, ''), (10, ''))
	# boundingitems(11) = ((10, ''), None)
	# arg itempredicate takes 2 args (key and value) and should return True if that item indicated is acceptable to
	# return from this function.  If False then this function will keep searching, upward or downward.
	def boundingitems(self, key_, itempredicate=None):
		assert len(self) == len(self._sortedkeys)
		if len(self) == 0:
			return (None, None)

		idx = bisect.bisect_left(self._sortedkeys, key_)

		def get_acceptable_key(start_key_idx__, search_upward_aot_downward__):
			if not (0 <= start_key_idx__ < len(self)):
				return None
			if itempredicate is not None:
				idx = start_key_idx__
				while 0 <= idx < len(self):
					if itempredicate(self._sortedkeys[idx], self[self._sortedkeys[idx]]):
						return self._sortedkeys[idx]
						break
					idx += (1 if search_upward_aot_downward__ else -1)
				else:
					return None
			else:
				return self._sortedkeys[start_key_idx__]

		lo_key = get_acceptable_key(idx-1, False)
		hi_key = get_acceptable_key((idx if key_ not in self else idx+1), True)

		def get_item(key__):
			return ((key__, self[key__]) if key__ is not None else None)
		return (get_item(lo_key), get_item(hi_key))

	def boundingvalues(self, key_, itempredicate=None):
		ritems = self.boundingitems(key_, itempredicate=itempredicate)
		def get_value(item__):
			return (item__[1] if item__ is not None else None)
		return (get_value(ritems[0]), get_value(ritems[1]))

	def minkey(self):
		if len(self._sortedkeys) == 0:
			raise Exception('Dict is empty.  Can\'t get min key.')
		else:
			return self._sortedkeys[0]

	def maxkey(self):
		if len(self._sortedkeys) == 0:
			raise Exception('Dict is empty.  Can\'t get max key.')
		else:
			return self._sortedkeys[-1]

def get_dir_tag_int(dir_tag_str_):
	assert isinstance(dir_tag_str_, basestring)
	is0 = '_0_' in dir_tag_str_
	is1 = '_1_' in dir_tag_str_
	if is0 and is1:
		raise Exception('dir_tag seems to indicate both directions (0 and 1).  %s' % dir_tag_str_)
	elif is0:
		return 0
	elif is1:
		return 1
	else:
		return None

def is_valid_time_em(time_em_):
	return abs(now_em() - time_em_) < 1000*60*60*24*365*20

# I checked the NextBus schedules of about 10 routes and they all had the same set of
# serviceClass values: sat, sun, and wkd.
def time_to_serviceclass(time_em_):
	assert is_valid_time_em(time_em_) # asserting a reasonable epoch-time-in-millis argument.
	dt = datetime.date.fromtimestamp(time_em_/1000.0)
	if dt.weekday() == 5:
		return 'sat'
	elif dt.weekday() == 6:
		return 'sun'
	else:
		return 'wkd'

def get_time_millis_within_day(time_em_):
	assert is_valid_time_em(time_em_)
	dt = datetime.datetime.fromtimestamp(time_em_/1000.0)
	return dt.hour*60*60*1000 + dt.minute*60*1000 + dt.second*1000

# TODO: make sure we handle daylight savings time (this was written in winter), first day of DST in the spring,
# first day of non-DST in the fall, and if really keen - the dark of night on those DST-switching days.
# (What is the TTC's policy for it?)
# I don't know what all code would need to be changed in order to handle these things.

def round_down_to_midnight(time_em_):
	assert is_valid_time_em(time_em_)
	dt = datetime.datetime.fromtimestamp(time_em_/1000.0)
	dt = datetime.datetime(dt.year, dt.month, dt.day)
	return long(time.mktime(dt.timetuple())*1000)

def datetime_round_down_to_midnight(dt_):
	return em_to_datetime(round_down_to_midnight(datetime_to_em(dt_)))

def millis_within_day_to_str(m_):
	assert 0 <= m_ <= 1000*60*60*48 # NextBus schedules use values greater than 1000*60*60*24 for times after midnight.
		# The TTC service day seems to start around 5:00 or 6:00 AM.
	hour = m_/(1000*60*60)
	minute = (m_ - hour*1000*60*60)/(1000*60)
	second = (m_ - (hour*1000*60*60 + minute*1000*60))/(1000)
	while hour > 23:
		hour -= 24
	return '%02d:%02d:%02d' % (hour, minute, second)

def invert_dict(dict_):
	if dict_ is None:
		return None
	elif len(dict_) == 0:
		return {}
	else:
		if len(set(dict_.values())) != len(dict_):
			raise Exception('Can\'t invert dict.  Contains duplicate values.')
		return dict((v,k) for k, v in dict_.iteritems())

def get_opt(opts_, optname_):
	for e in opts_:
		if e[0] == '--'+optname_:
			if e[1] == '':
				return True
			else:
				return e[1]
	else:
		return None

def redirect_stdstreams_to_file(filename_prefix_):
	filename = os.path.expanduser('~/ttc-logs/%s%s.txt' % (filename_prefix_, datetime.datetime.now().strftime('%Y-%m-%d')))
	if not os.path.exists(os.path.dirname(filename)):
		os.makedirs(os.path.dirname(filename))
	fout = open(filename, 'a+')
	sys.stdout.close()
	sys.stderr.close()
	sys.stdout = fout
	sys.stderr = fout

def remove_consecutive_duplicates(list_, key=None):
	if len(list_) < 2:
		return
	def get_key(val_):
		return (val_ if key==None else key(val_))
	curkey = get_key(list_[0]); prevkey = None
	i = 1
	while i < len(list_):
		prevkey = curkey
		curkey = get_key(list_[i])
		if prevkey == curkey:
			del list_[i]
			i -= 1
			curkey = prevkey
		i += 1

def svg_to_png(svgstr_):
	svg_fileno, svg_filename = tempfile.mkstemp('.svg', 'ttc-temp-svg-to-png-', '.')
	svg_file = os.fdopen(svg_fileno, 'w')
	svg_file.write(svgstr_)
	svg_file.close()
	subprocess.check_call(['java', '-jar', 'batik-1.7/batik-rasterizer.jar', os.path.basename(svg_filename)], \
			stdout=open('/dev/null', 'w'), stderr=open('/dev/null', 'w'))

	assert svg_filename[-4:] == '.svg'
	png_filename = svg_filename[:-4] + '.png' # batik just created this .png file, with a name based on the svg filename. 

	with open(png_filename, 'rb') as png_fin:
		png_contents = png_fin.read()
	os.remove(svg_filename)
	os.remove(png_filename)
	return png_contents

# Batch version.  Writes PNGs to files.  Returns nothing.  
# We want a batch version because starting up batik is slow.  (It takes about a 
# second to start up versus about 0.05 seconds to convert a single SVG.  Between vehicles and streetlabels, 
# we have thousands of these to deal with.) 
# arg: a list of 2-tuples: [(dest filename, svg string), ...]
def svgs_to_pngs(pngfilenames_and_svgstrs_):
	# Breaking argument list into chunks, because we can only pass so many command-line arguments to java (or any process 
	# for that matter).  Doing it badly - splitting by arguments while ignoring the length of those arguments.  (The operating 
	# system limit seems to be about the number of characters.  Run 'getconf ARG_MAX' to see.  Sample output on cygwin - 32000.
	CHUNK_SIZE = 1000
	for chunki, pngfilenames_and_svgstrs in enumerate(chunks(pngfilenames_and_svgstrs_, CHUNK_SIZE)):
		svg_filenames = [] # Writing SVG strings to files temporarily, because batik takes files as input. 
		for svgstr in [x[1] for x in pngfilenames_and_svgstrs]:
			svg_fileno, svg_filename = tempfile.mkstemp('.svg', 'temp_svgs_to_pngs_', '.')
			svg_filename = os.path.basename(svg_filename) # Trickery: removing directory part of path, because I want this to run 
				# on Windows under cygwin, where this script will be running under cygwin Python but the 'java' called below is 
				# a Windows version.  If we wrote this temp svg file to eg. /tmp, then we would need to convert that path (with 
				# cygpath presumably) before we pass it to java / batik.  I don't want to bother doing that, so I create these files 
				# in the current directory instead and get away with passing a directory-less filename to java. 
			assert svg_filename[-4:] == '.svg'
			svg_file = os.fdopen(svg_fileno, 'w')
			svg_file.write(svgstr)
			svg_file.close()
			svg_filenames.append(svg_filename)

		print 'Converting %d to %d of %d.' % (chunki*CHUNK_SIZE, (chunki+1)*CHUNK_SIZE, len(pngfilenames_and_svgstrs_))
		subprocess.check_call(['java', '-jar', 'batik-1.7/batik-rasterizer.jar'] + svg_filenames)
				#stdout=open('/dev/null', 'w'), stderr=open('/dev/null', 'w'))

		assert len(svg_filenames) == len(pngfilenames_and_svgstrs)
		for svg_filename, dest_png_filename in zip(svg_filenames, [x[0] for x in pngfilenames_and_svgstrs]):
			tmp_png_filename = svg_filename[:-4] + '.png' # batik just created this .png file, with a name based on the svg filename. 
			os.rename(tmp_png_filename, dest_png_filename)
			os.remove(svg_filename)

def values_sorted_by_key(dict_):
	for key in sorted(dict_.keys()):
		yield dict_[key]

# turn a list into a list of lists, each list length n_. 
def chunks(list_, n_):
	assert isinstance(list_, Sequence) and n_ > 0
	r = []
	start_idx = 0
	for start_idx in range(0, len(list_), n_):
		r.append(list_[start_idx:start_idx+n_])
	return r

def touch(filename_):
	with file(filename_, 'a'):
		os.utime(filename_, None)

def add_python_optimize_flag(file_):
	with open(file_) as fin:
		file_contents = fin.read()
	with open(file_, 'w') as fout:
		for linei, line in enumerate(StringIO.StringIO(file_contents)):
			if linei == 0:
				modified_line = re.sub('([\r\n]+)', ' -O\\1', line)
				fout.write(modified_line)
			else:
				fout.write(line)

def choose(n_, k_):
	return math.factorial(n_)/(math.factorial(k_)*math.factorial(n_-k_))

# Thanks to http://stackoverflow.com/questions/16994307/identityset-in-python/17039643#17039643 
class IdentitySet(MutableSet):
	key = id  # should return a hashable object

	def __init__(self, iterable=()):
		self.map = {} # id -> object
		self |= iterable  # add elements from iterable to the set (union)

	def __len__(self):  # Sized
		return len(self.map)

	def __iter__(self):  # Iterable
		return self.map.itervalues()

	def __contains__(self, x):  # Container
		return self.key(x) in self.map

	def add(self, value):  # MutableSet
		"""Add an element."""
		self.map[self.key(value)] = value

	def discard(self, value):  # MutableSet
		"""Remove an element.  Do not raise an exception if absent."""
		self.map.pop(self.key(value), None)

	def __repr__(self):
		if not self:
			return '%s()' % (self.__class__.__name__,)
		return '%s(%r)' % (self.__class__.__name__, list(self))

# intended for sets. 
def anyelem(iterable_):
	for e in iterable_:
		return e
	raise Exception('No elements.')

# iterate a dictionary according to a sort key. 
def iteritemssorted(dict_, key=None):
	keys = dict_.keys()
	keys.sort(key=key)
	for key, val in ((key, dict_[key]) for key in keys):
		yield (key, val)

def readfile(filename_):
	with open(filename_) as fin:
		return fin.read()

def writefile(filename_, contents_):
	with open(filename_, 'w') as fout:
		return fout.write(contents_)

# Like the builtin min() but returns None if the arg iterable is empty (instead of throwing a value error).
def min2(seq_, key=None):
	try:
		return min(seq_, key=(key if key is not None else lambda x: x))
	except ValueError: # not sure if I should depend on this behaviour. 
		return None

# Like the builtin max() but returns None if the arg iterable is empty (instead of throwing a value error).
def max2(seq_, key=None):
	try:
		return max(seq_, key=(key if key is not None else lambda x: x))
	except ValueError: # not sure if I should depend on this behaviour. 
		return None

def bisect_left_2(a_, x_, key=None, reverse=False):
	assert is_sorted(a_, key=key, reverse=reverse)
	key_n_vals = [((key(val) if key is not None else val), val) for val in a_]
	if reverse:
		key_n_vals.reverse()
	keys = [key for key, elem in key_n_vals]
	if reverse:
		return len(a_) - bisect.bisect_right(keys, x_)
	else:
		return bisect.bisect_left(keys, x_)

def is_close(a_, b_, tolerance_):
	return abs(a_ - b_) <= tolerance_

def sublist(list_, indexes_):
	return [e for i, e in enumerate(list_) if i in indexes_]

def get_local_minima_indexes(list_, key_):
	assert isinstance(list_, Sequence) and callable(key_)
	if len(list_) == 0:
		return []
	elif len(list_) == 1:
		return [0]
	else:
		keys = [key_(e) for e in list_]
		r = []
		for i in range(len(list_)):
			key = keys[i]
			if i == 0:
				is_minima = (keys[0] <= keys[1])
			elif i == len(list_)-1:
				is_minima = (keys[-1] < keys[-2])
			else:
				is_minima = (keys[i] < keys[i-1]) and (keys[i] <= keys[i+1])
			if is_minima:
				r.append(i)
		return r

def get_local_minima(list_, key_):
	return [list_[idx] for idx in get_local_minima_indexes(list_, key_)]

def permutation_2_indexes(list_):
	assert isinstance(list_, Sequence)
	for i in range(len(list_)):
		for j in range(len(list_)):
			if i != j:
				yield (i, j)

# Thanks to http://stackoverflow.com/questions/8977612/compose-function-and-functional-module 
#def compose(*funcs, unpack=False):
#	if not callable(func_1):
#		raise TypeError("First argument to compose must be callable")
#
#	if unpack:
#		if len(funcs) == 1:
#			def composition(*args, **kwargs):
#				return funcs[0](*args, **kwargs)
#		else:
#			def composition(*args, **kwargs):
#				return funcs[0](*func_2(*args, **kwargs))
#	else:
#		def composition(*args, **kwargs):
#			return func_1(func_2(*args, **kwargs))
#	return composition

# return a list of lists. 
def get_maximal_connected_groups(list_, is_connected_func_):
	assert isinstance(list_, Sequence) and callable(is_connected_func_)
	groups = [[x] for x in list_]
	while True:
		joined_something = False
		for idx1, idx2 in permutation_2_indexes(groups):
			group1 = groups[idx1]; group2 = groups[idx2]
			if any(is_connected_func_(x1, x2) for x1, x2 in product(group1, group2)):
				group1 += group2
				del groups[idx2]
				joined_something = True
				break
		if not joined_something:
			break
	return groups

def sliceii(list_, idx1_, idx2_):
	assert isinstance(list_, Sequence)
	assert idx1_ in range(len(list_)) and idx2_ in range(len(list_)) # -ve or too-high indexes are not supported here, 
	                                                                 # due to laziness by me. 
	if idx1_ < idx2_:
		return list_[idx1_:idx2_+1]
	else:
		r = []
		i = idx1_
		while i >= idx2_:
			r.append(list_[i])
			i -= 1
		return r

# Like python's built-in 'enumerate' function, but instead of yielding a numerical list index along with each element, 
# this yields two booleans indicating whether the elment is the first or last element of the list. 
# 
# So with this function, you could turn code like this: 
# 
# for i, e in enumerate(values):
# 	if i == 0:
# 		print 'BEGIN...', e
# 	elif i == len(values) - 1:
# 		print e, '... END'
# 	else:
# 		print e
# 
# ... into code like this: 
# 
# for i, e, isfirst, islast in enumerate2(values):
# 	if isfirst:
# 		print 'BEGIN...', e
# 	elif islast:
# 		print e, '... END'
# 	else:
# 		print e
def enumerate2(iterable_):
	it = iter(iterable_)
	try:
		e = it.next()
		isfirst = True
		i = 0
		try:
			while True:
				next_e = it.next()
				yield (i, e, isfirst, False)
				i += 1
				isfirst = False
				e = next_e
		except StopIteration:
			yield (i, e, isfirst, True)
	except StopIteration:
		pass

# Convenient for asserts or polymorphic function arguments, in some simple situations.  
# (I think polymorphic is the right word for this.  I'm not sure.) 
# 
# This let's you write something like this: 
# 	if is_seq_like(arg, (0, 0.0)): 
# 		... 
# instead of this: 
# 	if isinstance(arg, Sequence) and len(arg) == 2 \
# 			and type(arg[0]) == int and type(arg[1]) == float: 
# 		...
def is_seq_like(candidate_, reference_seq_):
	assert isinstance(reference_seq_, Sequence)
	if not (isinstance(candidate_, Sequence) and (len(candidate_) == len(reference_seq_))):
		return False
	else:
		for candidate_elem, reference_elem in zip(candidate_, reference_seq_):
			if type(candidate_elem) is not type(reference_elem):
				return False
		return True

def is_seq_of(obj_, type_or_types_):
	if isinstance(type_or_types_, Sequence):
		return isinstance(obj_, Sequence) and all(any(isinstance(e, tipe) for tipe in type_or_types_) for e in obj_)
	else:
		return isinstance(obj_, Sequence) and all(isinstance(e, type_or_types_) for e in obj_)

# Thanks to http://stackoverflow.com/questions/11263172/what-is-the-pythonic-way-to-find-the-longest-common-prefix-of-a-list-of-lists 
def get_common_prefix(seq1_, seq2_):
	return [i[0] for i in takewhile(lambda elems: len(set(elems)) == 1, izip(seq1_, seq2_))]

def is_prefix(short_, long_):
	return (get_common_prefix(short_, long_) == short_)

def rein_in(x_, min_, max_):
	if x_ < min_:
		return min_
	elif x_ > max_:
		return max_
	else:
		return x_

def kmph_to_mps(kmph_):
	return kmph_*1000.0/(60*60)

def mps_to_kmph(mps_):
	return mps_*60.0*60/1000;

# Like the built-in sum() function, but this one multiplies instead of adds. 
def mult(seq_):
	return reduce(lambda x, y: x*y, seq_)

def print_est_time_remaining(str_, t0_, i_, N_, every=1):
	if every == 1 or random.randrange(every) == 0:
		if i_ == 0:
			printerr('??? hours remaining.')
		else:
			time_elapsed_secs = time.time() - t0_
			rate = (i_+1)/time_elapsed_secs
			est_time_remaining_secs = (N_-(i_+1))/rate
			percent = i_*100/N_
			max_digits = len(str(N_))
			printerr(('%s%'+str(max_digits)+'d/%d - %2d%% done - %s elapsed - %s remaining - %.1f/sec.') \
					% (('%s: ' % str_ if str_ else ''), i_, N_, percent, time_span_str(time_elapsed_secs), 
					time_span_str(est_time_remaining_secs), rate))

def time_span_str(secs_):
	if secs_ > 60*60*48:
		return '%.1f days' % (secs_/(60*60*24))
	elif secs_ > 60*60:
		return '%.1f hours' % (secs_/(60*60))
	else:
		return '%.1f minutes' % (secs_/(60))

# Thanks to http://stackoverflow.com/questions/23598973/intercepting-heapq 
# http://stackoverflow.com/questions/1465662/how-can-i-implement-decrease-key-functionality-in-pythons-heapq 
# and http://hg.python.org/cpython/file/2.7/Lib/heapq.py 
class Heap(list):
	
	def __init__(self, list_):
		assert isinstance(list_, list)
		for e in list_:
			assert len(e) == 2 and (isinstance(e[0], int) or isinstance(e[0], float))
		self[:] = list_
		heapq.heapify(self)
		self._value_to_listindex = {}
		for i, (priority, value) in enumerate(self):
			self._value_to_listindex[value] = i

	def __setitem__(self,i,v):
		super(Heap,self).__setitem__(i,v)
		self._value_to_listindex[v[1]] = i

	def pop(self):
		lastelt = super(Heap,self).pop()		# raises appropriate IndexError if heap is empty
		del self._value_to_listindex[lastelt[1]]
		if self:
			returnitem = self[0]
			self[0] = lastelt
			heapq._siftup(self, 0)
		else:
			returnitem = lastelt
		return returnitem[1]

	def push(self, priority_, value_):
		assert isinstance(priority_, int) or isinstance(priority_, float)
		self.append((priority_, value_))
		idx = len(self)-1
		self._value_to_listindex[value_] = idx
		heapq._siftdown(self, 0, idx)

	def __contains__(self, item):
		return item in self._value_to_listindex

	def decrease_priority(self, new_priority_, value_):
		listidx = self._value_to_listindex[value_]
		if new_priority_ > self[listidx][0]:
			raise Exception()
		self[listidx] = (new_priority_, value_)
		heapq._siftdown(self, 0, listidx)

# Thanks to http://en.wikipedia.org/wiki/Longest_common_substring_problem#Pseudocode 
def get_longest_common_subseq(S, T):
	m = len(S); n = len(T)
	L = [[0]*n for x in xrange(m)]
	z = 0
	ret = []
	for i in xrange(m):
		for j in xrange(n):
			if S[i] == T[j]:
				if i == 0 or j == 0:
					L[i][j] = 1
				else:
					L[i][j] = L[i-1][j-1] + 1
				if L[i][j] > z:
					z = L[i][j]
					ret = [S[i-z+1:i+1]]
				elif L[i][j] == z:
					ret.append(S[i-z+1:i+1])
			else:
				L[i][j] = 0
	return (ret[0] if ret else [])

# Returns the starting index if found, like str.find(), but accepts sequences 
# of arbitrary objects instead of just strings.
def find_subseq(subseq_, seq_):
	if len(subseq_) > len(seq_):
		return -1
	def get_length_n_slices(n):
		for i in xrange(len(seq_) + 1 - n):
			yield seq_[i:i+n]
	for i, slyce in enumerate(get_length_n_slices(len(subseq_))):
		if slyce == subseq_:
			return i
	return -1

def find(seq_, val_, key_):
	for i, e in enumerate(seq_):
		if key_(e) == val_:
			return i
	else:
		return -1

def are_lists_equal(list1_, list2_, eq_func_):
	if len(list1_) != len(list2_):
		return False
	else:
		for e1, e2 in zip(list1_, list2_):
			if not eq_func_(e1, e2):
				return False
		return True

# This is limited.  For example, it won't handle item deletions in the source list unless they're in the 
# viewed part of the list.
# Thanks to http://stackoverflow.com/a/3485490/321556
class ListView(MutableSequence):

	def __init__(self, srclist, startidx, ourlen_):
		self.srclist = srclist
		self.startidx = startidx
		self.ourlen = (ourlen_ if ourlen_ is not None else len(srclist) - startidx)
		self.srclist_len = len(srclist)

	def __len__(self):
		self._deal_with_srclist_size_change()
		return self.ourlen

	def _adj(self, i, needstoexist=True):
		if i < 0:
			i += self.ourlen
		r = i + self.startidx
		if needstoexist and (r < self.startidx or r >= self.startidx + self.ourlen):
			raise IndexError()
		return r

	def __getitem__(self, i):
		self._deal_with_srclist_size_change()
		if isinstance(i, slice):
			start = 0 if i.start is None else (i.start if i.start >= 0 else self.ourlen + i.start)
			stop = self.ourlen if i.stop is None else (i.stop if i.stop >= 0 else self.ourlen + i.stop)
			step = 1 if i.step is None else i.step
			return self.srclist[self._adj(start, False) : self._adj(stop, False) : step]
		else:
			return self.srclist[self._adj(i)]

	def __setitem__(self, i, v):
		self._deal_with_srclist_size_change()
		if isinstance(i, slice):
			start = 0 if i.start is None else (i.start if i.start >= 0 else self.ourlen + i.start)
			stop = self.ourlen if i.stop is None else (i.stop if i.stop >= 0 else self.ourlen + i.stop)
			if i.step not in (1, None):
				raise Exception('step not supported.')
			slicelen = stop - start
			if slicelen > 0:
				numvals = 0
				for idx, val in enumerate(v):
					numvals += 1
					if idx >= slicelen:
						self.insert(start+idx, val)
					else:
						self[start+idx] = val
				for j in range(slicelen - numvals):
					del self[start + numvals]
		else:
			self.srclist[self._adj(i)] = v

	def __delitem__(self, i):
		self._deal_with_srclist_size_change()
		del self.srclist[self._adj(i)]
		self.ourlen -= 1

	def insert(self, i, v):
		self._deal_with_srclist_size_change()
		self.srclist.insert(self._adj(i, False), v)
		self.ourlen += 1

	def __str__(self):
		self._deal_with_srclist_size_change()
		return list(self).__str__()

	def __repr__(self):
		self._deal_with_srclist_size_change()
		return list(self).__repr__()

	def sort(self, key=None):
		self._deal_with_srclist_size_change()
		copy = list(self)
		copy.sort(key=key)
		for i, v in enumerate(copy):
			self[i] = v

	def _deal_with_srclist_size_change(self):
		new_srclist_len = len(self.srclist)
		if new_srclist_len != self.srclist_len:
			self.ourlen += (new_srclist_len - self.srclist_len)
			self.srclist_len = new_srclist_len

def string_to_file(filename_, str_):
	with open(filename_, 'w') as fout:
		fout.write(str_)

def file_to_string(filename_):
	with open(filename_) as fin:
		return fin.read()

def seq_endswith(a_, b_):
	return a_[-len(b_):] == b_

def profile_data_to_svg_file(profile_data_filename_):
	profile_moniker = re.sub('^(.*)\..*$', r'\1', os.path.basename(profile_data_filename_))
	p1 = subprocess.Popen(['gprof2dot.py', '-n', '2', '-e', '2', '-f', 'pstats', profile_data_filename_], stdout=subprocess.PIPE)
	if not os.path.exists('profiler-output'):
		os.mkdir('profiler-output')
	svg_out_filename = 'profiler-output/%s.svg' % (profile_moniker)
	p2 = subprocess.Popen(['dot', '-Tsvg', '-o', svg_out_filename], stdin=p1.stdout)
	p1.stdout.close()
	p2.communicate()
	if p2.returncode != 0:
		sys.exit('"dot" exited with return code %d' % (p2.returncode))
	#subprocess.check_call(['./add-panzoom-to-svg.py', svg_out_filename])

def dump_profiler_to_svg_file(profiler_, profile_moniker_):
	assert isinstance(profiler_, profile.Profile) or isinstance(profiler_, cProfile.Profile)
	profiler_.create_stats()
	profile_data_filename = '/tmp/%s.profile' % (profile_moniker_ or os.getenv('PROFILE_MONIKER') or now_str().replace(' ', '_'))
	profiler_.dump_stats(profile_data_filename)
	profile_data_to_svg_file(profile_data_filename)

def cpu_prof_exit_early_maybe():
	if int(os.getenv('PROF_EXIT_EARLY', '0')):
		printerr('> cpu prof - exiting early.')
		sys.exit(0)

def cpu_prof_disable_opt(level_=0):
	return int(os.getenv('PROF_DISABLE_OPT_LEVEL_%d' % level_, '0'))

def count_lines(filename_):
	with open(filename_) as fin:
		r = 0
		for line in fin:
			r += 1
		return r

# Like dict.update() but this doesn't modify any of the arguments, and returns the result.
def updated(*args_):
	r = args_[0].copy()
	for d in args_[1:]:
		r.update(d)
	return r

def minmax(seq_, key=None):
	if key is None:
		def keycmp(x__, y__):
			return cmp(x__, y__)
	else:
		def keycmp(x__, y__):
			return cmp(key(x__), key(y__))

	got_elem = False
	for e in seq_:
		if not got_elem:
			minimum = maximum = e
		elif keycmp(e, minimum) < 0: 
			minimum = e 
		elif keycmp(e, maximum) > 0: 
			maximum = e
		got_elem = True

	if not got_elem:
		raise ValueError("Can't get min/max of an empty sequence.")

	return (minimum, maximum)

class TimeWindow(object):

	def __init__(self, start_, end_):
		assert (0 < start_ < end_) and (end_ - start_ < 1000*60*60*3) and (abs(now_em() - start_) < 1000*60*60*24*365*50)
		#         ^^ important             ^^ not as important                 ^^ not as important  
		self.start = start_
		self.end = end_

	def __hash__(self):
		return hash(self.start) + hash(self.end)

	def __eq__(self, other_):
		if self is other_:
			return True
		elif type(self) != type(other_):
			return False
		else:
			return self.start == other_.start and self.end == other_.end

	@property
	def span(self):
		return self.end - self.start

	def __str__(self):
		return 'TimeWindow(%s, %s)' % (em_to_str_millis(self.start), em_to_str_millis(self.end))

	def __repr__(self):
		return self.__str__()

	def trim_vilist(self, vilist_):
		vilist_[:] = [vi for vi in vilist_ if self.start < vi.time_retrieved <= self.end]

	def trimmed_vilist(self, vilist_):
		vilist_copy = vilist_[:]
		self.trim_vilist(vilist_copy)
		return vilist_copy

	def gt_trimmed_vilist(self, vilist_):
		return [vi for vi in vilist_ if vi.time_retrieved > self.end]

def now_str_iso8601():
	local_tzinfo = dateutil.tz.tzlocal()
	dt = datetime.datetime.now()
	dt_with_timezone = datetime.datetime.fromtimestamp(time.mktime(dt.timetuple()), local_tzinfo)
	return dt_with_timezone.strftime('%Y-%m-%dT%H:%M:%S%z')

def datetime_xrange(dt1_, dt2_, timedelta_):
	x = dt1_
	while x < dt2_:
		yield x
		x += timedelta_

if __name__ == '__main__':

	pass



