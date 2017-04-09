#!/usr/bin/env python

import sys, pprint, png, StringIO, array, io
import windgraphs, u
from dtpythonutil.misc import *
import matplotlib
import matplotlib.dates
import matplotlib.pyplot as plt

# return PNG bytes 
def make_marker_png_with_a_lot_of_empty_space(marker_, size_, edgewidth_, color_):
	main_figure = plt.figure(1)
	fig, ax = plt.subplots()
	fig.set_size_inches(8, 8)
	plt.axis('off')

	plt.plot([datetime.datetime(1980, 1, 1, 1, 1)], [5], markeredgecolor=color_, color=color_, 
			marker=marker_, markersize=size_, markeredgewidth=edgewidth_, linestyle='none')

	buf = io.BytesIO()
	plt.savefig(buf, bbox_inches='tight', pad_inches=0)
	buf.seek(0)
	png_content_bytes = buf.read()
	main_figure.clf()
	plt.close()

	return png_content_bytes

# param margin_ between 0.0 and 1.0 
def crop_png_around_to_non_empty_space(png_bytes_, margin_):
	with io.BytesIO(png_bytes_) as in_buf:
		in_width, in_height, in_pixel_rows, in_attrs = png.Reader(file=in_buf).read()
		in_plane_count = in_attrs['planes']
		min_x = sys.maxint; min_y = sys.maxint; max_x = None; max_y = None
		for y, in_row in enumerate(in_pixel_rows):
			if len(in_row) % in_plane_count != 0:
				raise Exception()
			ok = True
			for x, in_pixel in enumerate(hopscotch(in_row, n=4, step=4)):
				if any(v != 255 for v in in_pixel):
					min_x = min(min_x, x)
					min_y = min(min_y, y)
					max_x = max(max_x, x)
					max_y = max(max_y, y)

	x_margin = int((max_x - min_x)*margin_)
	min_x = max(0, min_x - x_margin)
	max_x = min(in_width-1, max_x + x_margin)
	y_margin = int((max_y - min_y)*margin_)
	min_y = max(0, min_y - y_margin)
	max_y = min(in_height-1, max_y + y_margin)

	if max_x is None or max_y is None:
		raise Exception('Found no non-blank pixels.')

	with io.BytesIO(png_bytes_) as in_buf:
		in_pixel_rows, in_attrs = png.Reader(file=in_buf).read()[2:4]
		out_width = max_x - min_x + 1
		out_height = max_y - min_y + 1
		out_attrs = in_attrs.copy()
		plane_count = in_attrs['planes']
		del out_attrs['size']
		with io.BytesIO() as out_buf:
			out_rows = []
			for y, in_row in enumerate(in_pixel_rows):
				if min_y <= y <= max_y:
					out_row = array.array(in_row.typecode, in_row.tolist()[min_x*plane_count:(max_x+1)*plane_count])
					out_rows.append(out_row)
			png_writer = png.Writer(out_width, out_height, **out_attrs)
			png_writer.write(out_buf, out_rows)
			out_buf.seek(0)
			out_png_bytes = out_buf.read()
			return out_png_bytes 

def write(out_filename_, marker_, size_, edgewidth_, color_):
	png_bytes = make_marker_png_with_a_lot_of_empty_space(marker_, size_, edgewidth_, color_)
	png_bytes = crop_png_around_to_non_empty_space(png_bytes, 0.1)
	with open(out_filename_, 'wb') as fout:
		fout.write(png_bytes)

def write_all():
	print 'observations...'
	write(os.path.join('img', 'observations.png'), windgraphs.OBSERVATION_MARKER, 
			windgraphs.OBSERVATION_MARKER_SIZE, windgraphs.OBSERVATION_MARKER_EDGE_WIDTH, windgraphs.OBSERVATION_COLOR)
	for channel in windgraphs.PARSED_WEATHER_CHANNELS:
		print '%s...' % channel
		write(os.path.join('img', '%s.png' % channel), windgraphs.WEATHER_CHANNEL_TO_MARKER[channel], 
				windgraphs.FORECAST_MARKER_SIZE, windgraphs.FORECAST_MARKER_EDGE_WIDTH, 
				windgraphs.WEATHER_CHANNEL_TO_COLOR[channel])

if __name__ == '__main__':

	write_all()


