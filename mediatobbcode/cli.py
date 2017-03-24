#!/usr/bin/env python3
# coding=utf-8
# Copyright 2017 PayBas
# All Rights Reserved.

import getopt
import sys
import config
import core


def main(argv):
	"""
	Process command-line inputs
	"""
	# set the default opts as initial values
	config.populate_opts()

	h = 'cli.py\n' \
		'- parse current dir using default options\n\n' \
		'cli.py -m <media dir>\n' \
		'- parse all media files in dir -m and output to -m\n\n' \
		'cli.py -m <media dir> -o <output dir>\n' \
		'- parse all media files in dir -m and output to -o\n\n' \
		'cli.py -m <media dir> -r -o <output dir>\n' \
		'- parse all media files in -m recursively and output to -o\n\n' \
		'cli.py -c <config file>\n' \
		'- use previously saved config file to set script options\n\n' \
		'For a full list of command-line options, see the online documentation.'

	try:
		options, args = getopt.getopt(argv, 'hm:o:rzlbifuntsawzc:x',
			['help', 'mediadir=', 'outputdir=', 'recursive', 'zip', 'list', 'bare', 'individual', 'flat',
			'url', 'nothumb', 'tinylink', 'suppress', 'all', 'webhtml', 'fullsize', 'config=', 'xdebug'])
		if not options:
			print('No command-line options specified. Run using default settings on local directory.')

	except getopt.GetoptError:
		print(h)
		sys.exit(2)

	for opt, arg in options:
		if opt in ('-h', '--help'):
			print(h)
			sys.exit()

		elif opt in ('-m', '--mediadir'):
			config.opts['media_dir'] = arg
		elif opt in ('-o', '--outputdir'):
			config.opts['output_dir'] = arg
		elif opt in ('-r', '--recursive'):
			config.opts['recursive'] = True
		elif opt in ('-z', '--zip'):
			config.opts['parse_zip'] = True

		elif opt in ('-l', '--list'):
			config.opts['output_as_table'] = False
		elif opt in ('-b', '--bare'):
			config.opts['output_table_titles'] = False
		elif opt in ('-i', '--individual'):
			config.opts['output_individual'] = True
		elif opt in ('-f', '--flat'):
			config.opts['output_separators'] = False

		elif opt in ('-u', '--url'):
			config.opts['embed_images'] = False
		elif opt in ('-n', '--nothumb'):
			config.opts['output_bbcode_thumb'] = False
		elif opt in ('-t', '--tinylink'):
			config.opts['whole_filename_is_link'] = False
		elif opt in ('-s', '--suppress'):
			config.opts['suppress_img_warnings'] = True

		elif opt in ('-z', '--fullsize'):
			config.opts['use_imagelist_fullsize'] = True
		elif opt in ('-a', '--all'):
			config.opts['all_layouts'] = True
		elif opt in ('-w', '--webhtml'):
			config.opts['output_html'] = True

		elif opt in ('-c', '--config'):
			success = config.load_config_file(arg)
			if not success:
				sys.exit()
		elif opt in ('-x', '--xdebug'):
			# if we just want to debug image-host matching for development
			config.debug_imghost_slugs = True
			core.debug_imghost_matching()
			sys.exit()

	# initialize the script using the command-line arguments
	core.set_paths_and_run()


# hi there :)
if __name__ == '__main__':
	main(sys.argv[1:])
