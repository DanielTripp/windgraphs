#!/usr/bin/env python

import sys, pprint, png, StringIO, array
from windgraphs import *
import u
from dtpythonutil.misc import *

if __name__ == '__main__':

	def f():
		main_figure = plt.figure(1)
		fig, ax = plt.subplots()
		fig.set_size_inches(8, 8)
		#ax.get_xaxis().set_visible(False)
		#ax.get_yaxis().set_visible(False)
		plt.axis('off')

		observation_color = OBSERVATION_COLOR
		plt.plot([datetime.datetime(1980, 1, 1, 1, 1)], [5], markeredgecolor=observation_color, color=observation_color, 
				marker=OBSERVATION_MARKER, markersize=12, linestyle='none')

		#plt.xlim(em_to_datetime(target_times[0]-x_margin), em_to_datetime(target_times[-1]+x_margin))

		#plt.ylim(-5, 10)

		buf = io.BytesIO()
		plt.savefig(buf, bbox_inches='tight', pad_inches = 0)
		#plt.savefig(buf)
		#plt.savefig(buf, bbox_inches=0)
		buf.seek(0)
		png_content_bytes = buf.read()
		#png_content_base64 = base64.b64encode(png_content)
		main_figure.clf()
		plt.close()

		return png_content_bytes

	if 0: # tdr 
		l = [10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21]
		for i, x in enumerate(hopscotch(l, n=4, step=4)):
			print i, x 

	if 1:
		png_content_bytes = f()
		with io.BytesIO(png_content_bytes) as in_buf:
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

		x_margin = (max_x - min_x)/10
		min_x = max(0, min_x - x_margin)
		max_x = min(in_width-1, max_x + x_margin)
		y_margin = (max_y - min_y)/10
		min_y = max(0, min_y - y_margin)
		max_y = min(in_height-1, max_y + y_margin)

		if max_x is None or max_y is None:
			raise Exception('Found no non-blank pixels.')

		with io.BytesIO(png_content_bytes) as in_buf:
			in_pixel_rows, in_attrs = png.Reader(file=in_buf).read()[2:4]
			print min_x , min_y , max_x , max_y 
			out_width = max_x - min_x + 1
			out_height = max_y - min_y + 1
			out_attrs = in_attrs.copy()
			plane_count = in_attrs['planes']
			del out_attrs['size']
			with open('tmp/out.png', 'wb') as fout:
				out_rows = []
				for y, in_row in enumerate(in_pixel_rows):
					if min_y <= y <= max_y:
						out_row = array.array(in_row.typecode, in_row.tolist()[min_x*plane_count:(max_x+1)*plane_count]) # tdr 
						out_rows.append(out_row)
				png_writer = png.Writer(out_width, out_height, **out_attrs)
				png_writer.write(fout, out_rows)
			#print u.write_png_to_tmp('marker---', png_content_in_base64)


