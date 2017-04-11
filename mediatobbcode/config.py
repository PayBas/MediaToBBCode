#!/usr/bin/env python3
# coding=utf-8
# Copyright 2017 PayBas
# All Rights Reserved.

import configparser
import copy
import os
from collections import OrderedDict

# all configurable config options, with defaults and additional information for the GUI
config = OrderedDict([
	('iopts', OrderedDict([
		('media_dir', ['', 'Media dir']),
		('output_dir', ['', 'Output dir']),
		('recursive', [False, 'Recursive']),
		('parse_zip', [False, 'Parse ZIP']),
	])),
	('oopts', OrderedDict([
		('output_as_table', [True, 'Output as table using [table] tag.']),
		('output_table_titles', [True, 'Output title(s) above the table(s).']),
		('output_individual', [False, 'Output each directory as an individual file (when using "recursive").']),
		('output_separators', [True, 'Output separators for each parsed directory (when using "recursive").']),
		('embed_images', [True, 'Embed images using the [spoiler] tag (otherwise output a simple link).']),
		('output_bbcode_thumb', [True, 'Use the [thumb] tag when embedding images.']),
		('whole_filename_is_link', [True, 'Make the whole file-name a [spoiler] (or url-link) to the image/url.']),
		('suppress_img_warnings', [False, 'Suppress error and warning messages for missing images.']),
		('all_layouts', [False, 'Output all layout combinations in a single file (for easy testing).']),
		('output_html', [False, 'Output to HTML. The output BBCode will be converted (for easy testing).'])
	])),
	('mopts', OrderedDict([
		('imagelist_primary', ['', 'string', 'Primary image-list file']),
		('imagelist_alternative', ['', 'string', 'Secondary image-list file']),
		('imagelist_fullsize', ['', 'string', 'Full-size image-list file']),
		('use_imagelist_fullsize', [False, 'bool', 'Add list of full-sized images to output']),
		('use_primary_as_fullsize', [False, 'bool', 'Use primary image-list for full-sized output'])
	])),
	('dopts', OrderedDict([
		('cTHBG', ['#003875', 'color', 'table header background']),
		('cTHBD', ['#0054B0', 'color', 'table header border']),
		('cTHF', ['#FFF', 'color', 'table header font color']),
		('fTH', ['Verdana', 'font', 'table header font']),
		('cTBBG', ['#F4F4F4', 'color', 'table body background']),
		('cTSEPBG', ['#B0C4DE', 'color', 'table body separator background']),
		('cTSEPF', ['', 'color', 'table body separator font color']),
		('tFileDetails', ['FILE DETAILS', 'text', 'file-details table title']),
		('tImageSets', ['IMAGE-SET DETAILS', 'text', '(when using the "Parse ZIP" option)']),
		('tFullSizeSS', ['SCREENS (inline)', 'text', '(when using the full-size images option)']),
		('tFullSizeShow', ['SCREENS', 'text', '(when using the full-size images option)'])
	]))
])

opts = dict()  # Don't touch! See populate_opts()
opts_saved = dict()  # Don't touch! Only used to determine if opts have changed since initializing/loading/saving
debug_imghost_slugs = False  # For debugging. Only available from the command-line.
kill_thread = False  # Flag for killing the parsing process, since terminating a QThread is unreliable

author = 'PayBas'
author_url = 'https://github.com/PayBas'
script = 'MediaToBBCode.py'
script_url = 'https://github.com/PayBas/MediaToBBCode'
version = '1.2.5'
compile_date = '08-04-2017'
credits_bbcode = 'Output script by [url={}]PayBas[/url].'.format(script_url)


def populate_opts():
	"""
	Put all the config options into one big (but simple) dictionary which can be manipulated by the command-line or GUI.
	This is much easier to work with than the full _config_ dictionary.
	Also checks to see if mediatobbcode-config.ini exists, and loads opts from it if it is.
	"""
	global opts, opts_saved

	for group in config.values():
		for opt, values in group.items():
			opts[opt] = values[0]

	opts_saved = copy.copy(opts)

	# load mediatobbcode-config.ini to overrule hard-coded defaults, in case the user has modified it
	if os.path.exists('mediatobbcode-config.ini'):
		load_config_file('mediatobbcode-config.ini')
	elif os.path.exists(os.path.normpath('../dist/mediatobbcode-config.ini')):
		load_config_file(os.path.normpath('../dist/mediatobbcode-config.ini'))


def save_config_file(file):
	global opts_saved
	print('Saving config to: {}'.format(file))

	parser = configparser.ConfigParser(allow_no_value=True)

	# use the structure of 'config', but use the values of 'opts'
	try:
		for key, group in config.items():
			parser[key] = {}
			for opt in group:
				parser[key][opt] = str(opts[opt])
	except (KeyError, IndexError) as error:
		print('ERROR: mismatch for option: {}'.format(error))
		return

	try:
		with open(file, 'w', encoding='utf-8') as stream:
			parser.write(stream)
			opts_saved = copy.copy(opts)
	except (IOError, OSError):
		print('ERROR: Couldn\'t save config file: {}'.format(file))
		return


def load_config_file(file):
	global opts, opts_saved
	print('Loading config from: {}'.format(file))

	try:
		config_file = configparser.ConfigParser()
		success = config_file.read(os.path.normpath(file))

		if not success:
			print('ERROR: Couldn\'t open config file: {}'.format(file))
			return
		elif not config_file.sections():
			print('ERROR: empty or corrupt config file!')
			return

		try:
			for key, group in config.items():
				for opt in group:
					# since .INI files only support string values, we try to detect other datatypes
					if isinstance(opts[opt], bool):
						opts[opt] = config_file[key].getboolean(opt)
					elif isinstance(opts[opt], int):
						opts[opt] = config_file[key].getint(opt)
					else:
						opts[opt] = config_file[key][opt]
		except (KeyError, IndexError, ValueError) as error:
			print('ERROR: {}'.format(error))
			return

	except (IOError, OSError, configparser.Error) as error:
		print('ERROR: {}'.format(error))
		return

	print('Loaded config from: {}'.format(file))
	opts_saved = copy.copy(opts)
	return True
