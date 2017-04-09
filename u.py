#!/usr/bin/env python

import sys, os, stat, datetime, pprint, base64, tempfile, shutil
import windgraphs

def write_png_to_tmp(png_filename_prefix_, png_content_in_base64_):
	png_dir=os.path.join(os.path.dirname(sys.argv[0]), 'tmp')
	try:
		os.mkdir(png_dir)
	except OSError:
		pass
	with tempfile.NamedTemporaryFile(prefix=png_filename_prefix_, suffix='.png', dir=png_dir, delete=False) as fout:
		fout.write(base64.b64decode(png_content_in_base64_))
		png_file = fout.name
		os.chmod(png_file, stat.S_IRWXU | stat.S_IRWXO)
	copy_of_png_file = os.path.join(os.path.dirname(png_file), 'latest.png')
	shutil.copyfile(png_file, copy_of_png_file)
	copy_stat = os.stat(copy_of_png_file)
	os.utime(copy_of_png_file, (copy_stat.st_atime, copy_stat.st_mtime+1))
	return png_file

