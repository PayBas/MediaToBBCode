#!/usr/bin/env python3
# coding=utf-8
# Copyright 2017 PayBas
# All Rights Reserved.

import copy
import os
import re
import sys
import unicodedata
from collections import OrderedDict
from hashlib import md5
from urllib.parse import urlparse
from zipfile import ZipFile, BadZipFile
from pymediainfo import MediaInfo
from mediatobbcode import config

cERR = '#F00'  # output color for errors
cWARN = '#F80'  # output color for warnings
tags = []


def set_paths_and_run():
	"""
	Sanitizes and sets the correct input and output directories, before starting the parsing process.
	"""
	# set the correct output_dir
	if not config.opts['output_dir'] and not config.opts['media_dir']:
		print('ERROR: no media directory specified!')
		return
	elif not config.opts['output_dir']:
		# no output_dir specified, so we will output to the media_dir
		config.opts['output_dir'] = os.path.normpath(os.path.expanduser(config.opts['media_dir']))
	else:
		config.opts['output_dir'] = os.path.normpath(os.path.expanduser(config.opts['output_dir']))

	# set the correct media_dir
	config.opts['media_dir'] = os.path.normpath(os.path.expanduser(config.opts['media_dir']))
	print('using media_dir  = ' + config.opts['media_dir'])
	print('using output_dir = ' + config.opts['output_dir'])

	parse_files()


def parse_files():
	"""
	Traverses the specified media_dir directory and detects all video-clips (and image-sets if specified).
	Depending on whether output_individual is used, it will call to output once or for each directory parsed.
	"""
	clips = []
	imagesets = []
	ran_at_all = False  # canary - general
	parsed_at_all = False  # canary - for when output_individual has cleared clips[] after sending to output

	media_ext = ['.3gp', '.amv', '.asf', '.avi', '.divx', '.f4v', '.flv', '.m2v', '.m4v', '.mkv', '.mp4', '.mpeg',
				'.mpg', '.mov', '.mts', '.ogg', '.ogv', '.qt', '.rm', '.rmvb', '.ts', '.vob', '.webm', '.wmv']
	zip_ext = ['.zip', '.zipx']

	if config.opts['parse_zip']:
		parse_ext = tuple(media_ext + zip_ext)
	else:
		parse_ext = tuple(media_ext)

	if config.opts['recursive'] and config.opts['output_separators'] and not config.opts['output_individual']:
		insert_separators = True
	else:
		insert_separators = False

	# start directory traversal
	for root, dirs, files in os.walk(config.opts['media_dir']):
		print('\nSWITCH dir: {}'.format(root))
		new_dir = True
		new_zip_dir = True
		ran_at_all = True
		current_relative_dir = os.path.relpath(root, config.opts['media_dir'])

		for file in files:
			# help the GUI to terminate the thread
			if config.kill_thread:
				config.kill_thread = False
				return

			# skip files with extensions we don't want to parse
			if not file.lower().endswith(parse_ext):
				print(' skipped file: {}'.format(file))
				continue

			# if parse_zip is enabled, check ZIP files to see if it's an image-set
			if config.opts['parse_zip'] and file.lower().endswith(tuple(zip_ext)):
				imgset = parse_zip_file(root, file)
				if imgset:
					# create a separator with the relative directory, but only if it's the first valid file in the dir
					if new_zip_dir and insert_separators and current_relative_dir is not '.':
						imagesets.append(Separator(current_relative_dir))
					new_zip_dir = False

					imagesets.append(imgset)
				continue

			# parse media file
			clip = parse_media_file(root, file)
			if clip:
				# create a separator with the relative directory, but only if it's the first valid file in the dir
				if new_dir and insert_separators and current_relative_dir is not '.':
					clips.append(Separator(current_relative_dir))
				new_dir = False

				clips.append(metadata_cleanup(clip))

		# break after top level if we don't want recursive parsing
		if not config.opts['recursive']:
			break
		elif config.opts['output_individual'] and (clips or imagesets):
			# output each dir as a separate file, so we need to reset the clips after each successfully parsed dir
			parsed_at_all = True
			generate_output(OrderedDict([('clips', clips), ('imagesets', imagesets)]), root)
			clips = []
			imagesets = []

	if not ran_at_all:
		print('ERROR: invalid directory for: {}'.format(config.opts['media_dir']))
	elif not clips and not imagesets and not parsed_at_all:
		print('ERROR: no valid media files found in: {}'.format(config.opts['media_dir']))
	elif not config.opts['output_individual']:
		generate_output(OrderedDict([('clips', clips), ('imagesets', imagesets)]), config.opts['media_dir'])


def parse_media_file(root, file):
	"""
	Uses the pymediainfo module to parse each file and extract media information from each video-clip.
	"""
	try:
		print(' attempt file: {}'.format(file))
		media_info = MediaInfo.parse(os.path.join(root, file))
	except OSError as error:
		print(error)
		return
	except:
		(errortype, value, traceback) = sys.exc_info()
		sys.excepthook(errortype, value, traceback)
		return

	track_general = track_video = track_audio = None

	try:
		# get the first video and audio tracks, the rest will be ignored
		for track in media_info.tracks:
			if track.track_type == 'General' and not track_general:
				track_general = track
			elif track.track_type == 'Video' and not track_video:
				track_video = track
			elif track.track_type == 'Audio' and not track_audio:
				track_audio = track

		# get the useful bits from the track objects
		if track_video:
			filepath = os.path.dirname(track_general.complete_name)
			filename = track_general.file_name + '.' + track_general.file_extension
			filesize = track_general.file_size
			length = track_general.duration

			vcodec = track_video.codec_id
			vcodec_alt = track_video.format
			vbitrate = track_video.bit_rate
			vbitrate_alt = track_general.overall_bit_rate
			vwidth = track_video.width
			vheight = track_video.height
			vscantype = track_video.scan_type
			vframerate = track_video.frame_rate
			vframerate_alt = track_video.nominal_frame_rate

			# crazy, I know, but some freaky videos don't have any audio tracks :S
			if not track_audio:
				acodec = abitrate = asample = aprofile = None
			else:
				acodec = track_audio.format
				abitrate = track_audio.bit_rate
				asample = track_audio.sampling_rate
				aprofile = track_audio.format_profile

			print(' parsed file : {}'.format(file))
			# create Clip object for easier manipulation and passing around
			return Clip(filepath, filename, filesize, length, vcodec, vcodec_alt, vbitrate, vbitrate_alt, vwidth,
						vheight, vscantype, vframerate, vframerate_alt, acodec, abitrate, asample, aprofile)
		else:
			print('ERROR parsing: {}  -  no video track detected'.format(file))

	except AttributeError:
		print('ERROR parsing: {}  -  malformed video file?'.format(file))


def parse_zip_file(root, file):
	"""
	Processes a compressed archive and attempts to get information on the image-set located therein.
	We could have used MediaInfo for this too, but Pillow is easier and more reliable.
	Requires Pillow
	"""
	try:
		# TODO import once or switch to MediaInfo after all?
		from PIL import Image
	except ImportError:
		print('\nERROR: Couldn\'t import Pillow module!\n')
		return

	try:
		print(' attempt archive: {}'.format(file))
		# each archive is an entire image-set, so we'll get some basic information on the set
		with ZipFile(os.path.join(root, file)) as archive:
			img_count = 0
			max_resolution = (0, 0)
			filesize = os.path.getsize(os.path.join(root, file))
			orig_size = 0

			for member in archive.infolist():
				orig_size += member.file_size
				# parse each image in the archive to determine the highest image-resolution present
				with archive.open(member) as img:
					try:
						img = Image.open(img)
						img_count += 1
						if img.width > max_resolution[0]:
							max_resolution = img.size
						img.close()
					except IOError:
						# not an image file
						continue

			if img_count:
				filesize = readable_number(filesize)
				orig_size = readable_number(orig_size)
				print(' parsed archive : {}'.format(file))
				return ImageSet(root, file, filesize, orig_size, img_count, max_resolution)
			else:
				print(' ERROR parsing  : {}  -  no image files in archive?'.format(file))

	except BadZipFile:
		print(' ERROR parsing  : {}  -  unsupported archive type?'.format(file))


def generate_output(items, source):
	"""
	Takes the items (Clips and/or ImageSets) generated from a dir parsing session and determines the formatting to use.
	"""
	global tags

	# no items (clips/image-sets)? something is wrong
	if not items:
		print('ERROR: No media clips found! The script shouldn\'t even have gotten this far. o_O')
		return

	# stop if this combination is active, it will produce a mess
	if config.opts['whole_filename_is_link'] and config.opts['embed_images'] and not config.opts['output_as_table']:
		print('Using the parameters "whole_filename_is_link" and "embed_images" and not "output_as_table"'
			' is the only invalid combination\n\n')
		return

	# setup some file locations for input/output
	if config.opts['output_individual']:
		# When creating an output file for each parsed directory, we don't want to have to create directories to
		# the same depth as the source files (in order to keep the file structure). So for directories deeper than
		# media_dir + 1, we concatenate the dir-names into a long string.
		relpath = os.path.relpath(source, config.opts['media_dir'])

		if relpath == '.':
			working_file = os.path.join(config.opts['output_dir'], os.path.basename(source))
		else:
			working_file = os.path.join(config.opts['output_dir'], relpath.replace('\\', '__').replace('/', '__'))
	else:
		working_file = os.path.join(config.opts['output_dir'], os.path.basename(source))

	file_output = working_file + '_output.txt'
	file_output_html = working_file + '_output.html'

	if config.opts['imagelist_primary']:
		file_img_list = config.opts['imagelist_primary']
	else:
		file_img_list = working_file + '.txt'

	if config.opts['imagelist_alternative']:
		file_img_list_alt = config.opts['imagelist_alternative']
	else:
		file_img_list_alt = working_file + '_alt.txt'

	if config.opts['imagelist_fullsize']:
		file_img_list_fullsize = config.opts['imagelist_fullsize']
	else:
		file_img_list_fullsize = working_file + '_fullsize.txt'

	# make output file
	try:
		output = open(file_output, 'w+', encoding='utf-8')
	except (IOError, OSError):
		print('ERROR: Couldn\'t create output file: {}  (invalid directory?)'.format(file_output))
		return

	# get the image data for later use
	img_data = get_img_list(file_img_list)
	if not img_data:
		# just in case users use the script wrong (by only providing _fullsize.txt containing direct links)
		img_data = get_img_list(file_img_list_fullsize)

	# get a second set of image data to provide alternative image-links in case the primary image-host should die
	img_data_alt = get_img_list(file_img_list_alt, True)
	has_alts = True if img_data_alt else False

	# get the full-size image data (see format_fullsize_section())
	img_data_fullsize = None
	if config.opts['use_imagelist_fullsize'] and not config.opts['use_primary_as_fullsize']:
		img_data_fullsize = get_img_list(file_img_list_fullsize)

	# convert the dictionary of lists of objects, to a dictionary of lists of object/lists (with image data)
	prepared_items = prepare_items(items, img_data, img_data_alt, img_data_fullsize)

	# create a list of all the full-sized images (if present) for fast single-click browsing
	if config.opts['use_imagelist_fullsize']:
		for _type, _list in prepared_items.items():
			if not _list:
				continue
			output.write(format_fullsize_section(_list))

	# everything is set up, now we can finally output something useful
	if config.opts['all_layouts']:
		generate_all_layouts(output, prepared_items, has_alts)
	else:
		for _type, _list in prepared_items.items():
			if not _list:
				continue
			output.write(format_collection(_type, _list, has_alts))

	# append the generated performer tags to the output
	if tags:
		output.write('PERFORMER TAGS:  ' + ' '.join(tags) + '\n\n')
		tags = []  # reset global tags for next run (particularly in recursive/individual mode)
		print('Performer tags added')

	# finished succesfully
	output.close()
	print('Output written to: {}'.format(file_output))

	# convert the final output to HTML code for quicker testing
	if config.opts['output_html']:
		import output_html
		output_html.format_html_output(file_output, file_output_html)


def prepare_items(items, img_data, img_data_alt, img_data_fullsize):
	"""
	Combine media items with image data (from 3 different image-list sources).
	"""
	global tags

	for _type, _list in items.items():
		if not _list:
			continue

		# iterate over each item, and add corresponding image data
		for _id, item in enumerate(_list):

			# separators don't require any processing
			if isinstance(item, Separator):
				continue

			img_match = img_match_alt = img_match_fullsize = None

			# get thumbnail data from image-list, alternative/backup image-list, and full-size image-list
			for _set, idata in enumerate([img_data, img_data_alt, img_data_fullsize]):
				if idata:
					if 'imagebam' in idata['host']:
						file_slug = get_screenshot_hash(item.filename, item.filepath, 'md5', 6)
					else:
						file_slug = slugify(item.filename, idata['host'])

					match = match_slug(idata['img_list'], file_slug, idata['file'])  # list, can be multiple!

					if _set == 0:
						img_match = match
					elif _set == 1:
						img_match_alt = match
					elif _set == 2:
						img_match_fullsize = match

			if config.opts['use_imagelist_fullsize'] and config.opts['use_primary_as_fullsize']:
				img_match_fullsize = img_match

			# try to generate performer tags for presentation, see generate_tags()
			generate_tags(item.filename)

			# convert the item object to a list, combining the object with its image matches
			items[_type][_id] = {'item': item,
								'img_match': img_match,
								'img_match_alt': img_match_alt,
								'img_match_fullsize': img_match_fullsize}

	return items


def format_collection(_type, _list, has_alts):
	"""
	Sets up the output for a collection (Clips or ImageSets).
	"""
	column_names = None
	output = ''

	# if we choose to output the data as a table, we need to set up the table headers before the data first row
	if config.opts['output_as_table']:

		# setup columns
		column_names = ['Filename{}'.format(' + IMG' if config.opts['embed_images'] else '')]
		if _type == 'clips':
			title = config.opts['tFileDetails']
			column_names += ['Size', 'Length', 'Codec', 'Resolution', 'Audio']
		elif _type == 'imagesets':
			title = config.opts['tImageSets']
			column_names += ['Images', 'Resolution', 'Size', 'Unpacked']
		else:
			title = '?'
		if has_alts:
			column_names += ['Alt.']

		# output table title
		if config.opts['output_table_titles']:
			tt = ('[table=100%][tr][td={1}][bg={2}][align=center][font={4}][size=5][color={3}]'
				'[b]{0}[/b][/color][/size][/font][/align][/bg][/td][/tr][/table]'
				.format(title, config.opts['cTHBD'], config.opts['cTHBG'], config.opts['cTHF'], config.opts['fTH']))
			output += tt

		# setup the main table
		th = '[size=0][align=center][table=100%,{}]\n[tr]'.format(config.opts['cTBBG'])
		th += '[th][align=left]{}[/align][/th]'.format(column_names[0])
		for name in column_names[1:]:
			th += '[th]{}[/th]'.format(name)
		th += '[/tr]\n'
		output += th

	items_parsed = 0

	# iterate over each item, and pass to row formatting
	for item in _list:

		if isinstance(item, Separator):
			output += format_row_separator(item, column_names)
			continue
		else:
			# don't count separators towards the final output
			items_parsed += 1

		# generate the item's content row
		output += format_row_common(item['item'], item['img_match'], item['img_match_alt'], has_alts)

	# if we choose to output the data as a table, we need to set up the table footer after the last data row
	if config.opts['output_as_table']:
		output += '[/table][/align][/size]'

	output += ('[size=0][align=right]File information for {} items generated by MediaInfo. {}[/align][/size]\n\n'
				.format(items_parsed, config.credits_bbcode))
	return output


def format_row_common(item, img_match, img_match_alt, has_alts=False):
	"""
	Generate the row output based on the input item (a Clip or an ImageSet). Here we mainly do all operations that are
	common to both 'table' and 'list' outputs, before calling the functions dealing with their differences.
	"""
	if img_match and len(img_match) == 1:
		# format the image link (and thumbnail) into correct BBCode for display
		img_match = img_match[0]
		if config.opts['embed_images']:
			if img_match['bburl']:
				img_code = '[url={1}][img]{0}[/img][/url]'.format(img_match['bbimg'], img_match['bburl'])
			elif config.opts['output_bbcode_thumb']:
				img_code = '[thumb]{0}[/thumb]'.format(img_match['bbimg'])
			else:
				img_code = '[img]{0}[/img]'.format(img_match['bbimg'])
		# since we don't want to embed the image (or thumbnail), just grab the url to the big version
		else:
			img_code = img_match['bburl'] if img_match['bburl'] else img_match['bbimg']
		img_msg = None
	elif img_match:
		img_code = False
		img_msg = '[color={}]Image conflict![/color]'.format(cWARN)  # multiple matches
	else:
		img_code = False
		img_msg = '[color={}]Image missing![/color]'.format(cERR)

	# get the url to the full-sized alternative/backup image
	if has_alts:
		if img_match_alt and len(img_match_alt) == 1:
			img_match_alt = img_match_alt[0]
			img_code_alt = img_match_alt['bburl'] if img_match_alt['bburl'] else img_match_alt['bbimg']
			img_msg_alt = '\n[url={}][b]> Backup Image <[/b][/url]'.format(img_code_alt)
		elif img_match_alt:
			img_code_alt = False
			img_msg_alt = '[color={}][b]Image conflict![/b][/color]'.format(cWARN)  # multiple matches
		else:
			img_code_alt = False
			img_msg_alt = '[color={}][b]Image missing![/b][/color]'.format(cERR)
	else:
		img_code_alt = False
		img_msg_alt = ''

	if config.opts['output_as_table']:
		# output BBCode as a table row
		output = format_row_table(item, img_code, img_msg, img_code_alt, img_msg_alt, has_alts)
	else:
		# output BBCode as a normal list row
		output = format_row_list(item, img_code, img_msg, img_code_alt, img_msg_alt)

	return output


def format_row_table(item, img_code, img_msg, img_code_alt, img_msg_alt, has_alts):
	"""
	Formats the output BBCode for an individual item (row) in the resulting table.
	"""
	if img_code:
		# make the entire file-name a spoiler link
		if config.opts['embed_images'] and config.opts['whole_filename_is_link']:
			bbsafe_filename = item.filename.replace('[', '{').replace(']', '}')
			col1 = '[spoiler={0}]{1}{2}[/spoiler]'.format(bbsafe_filename, img_code, img_msg_alt)
		# inline spoiler BBCode pushes trailing text to the bottom, so if we embed images, they have to be at the end
		elif config.opts['embed_images']:
			col1 = '{0}     [spoiler=IMG]{1}{2}[/spoiler]'.format(item.filename, img_code, img_msg_alt)
		elif config.opts['whole_filename_is_link']:
			col1 = '[b][url={1}]{0}[/url][/b]'.format(item.filename, img_code)
		else:
			col1 = '[b][b][url={1}]IMG[/url][/b]  {0}[/b]'.format(item.filename, img_code)
	elif config.opts['suppress_img_warnings']:
		col1 = item.filename
	else:
		col1 = '{0}     {1}'.format(item.filename, img_msg)

	col1 = '[td][align=left][size=2]{}[/size][/align][/td]'.format(col1)

	if isinstance(item, Clip):
		col2 = '[td]{}[/td]'.format(item.filesize)
		col3 = '[td]{}[/td]'.format(item.length)
		col4 = '[td]{0} @ {1}[/td]'.format(item.vcodec, item.vbitrate)
		col5 = '[td]{0}×{1} @ {2} {3}[/td]'.format(item.vwidth, item.vheight, item.vframerate, item.vscantype)
		col6 = '[td]{0} {1} @ {2}[/td]'.format(item.acodec, item.abitrate, item.asample)
	elif isinstance(item, ImageSet):
		col2 = '[td]{}[/td]'.format(item.img_count)
		col3 = '[td]{0}×{1} px[/td]'.format(item.resolution[0], item.resolution[1])
		col4 = '[td]{}[/td]'.format(item.filesize)
		col5 = '[td]{}[/td]'.format(item.orig_size)
		col6 = ''
	else:
		print('ERROR: script tried to parse an unknown object! This should never happen.')
		return ''

	if has_alts:
		if img_code_alt:
			col7 = '[td][url={0}]IMG[/url][/td]'.format(img_code_alt)
		elif 'conflict' in img_msg_alt:
			col7 = '[td][b][b][color={}]![/color][/b][/b][/td]'.format(cWARN)
		else:
			col7 = '[td][b][b][color={}]?[/color][/b][/b][/td]'.format(cERR)
	else:
		col7 = ''

	return '[tr]{0}{1}{2}{3}{4}{5}{6}[/tr]\n'.format(col1, col2, col3, col4, col5, col6, col7)


def format_row_list(item, img_code, img_msg, img_code_alt, img_msg_alt):
	"""
	Formats the output BBCode for an individual item (row) in the resulting list.
	This is messier to look at, but more flexible with images (and BBCode support).
	"""
	filename = item.filename

	if img_code:
		if config.opts['embed_images']:
			img_code = ' [spoiler=:]{0}{1}[/spoiler]'.format(img_code, img_msg_alt)
		elif config.opts['whole_filename_is_link']:
			filename = '[url={1}]{0}[/url]'.format(filename, img_code)
			if img_code_alt:
				filename += '  ([url={}]alt.[/url])'.format(img_code_alt)
			img_code = ''
		else:
			if img_code_alt:
				filename = '[b][url={1}]IMG[/url][/b] | [url={2}]aIMG[/url]  {0}'.format(filename, img_code, img_code_alt)
			else:
				filename = '[b][url={1}]IMG[/url][/b]  {0}'.format(filename, img_code)
			img_code = ''
	elif config.opts['suppress_img_warnings']:
		img_code = ''
	else:
		img_code = '     {0}'.format(img_msg)

	sep = ' || '

	if isinstance(item, Clip):
		fmeta = '{0} ~ {1}'.format(item.filesize, item.length)
		vinfo = '{0} {1} ~ {2}×{3} @ {4}'.format(item.vcodec, item.vbitrate, item.vwidth, item.vheight, item.vframerate)
		ainfo = '{0} {1} @ {2}'.format(item.acodec, item.abitrate, item.asample)

		return '[b]{1}[/b][size=0] {0} {3} {0} {4} {0} {5} [/size]{2}\n' \
			.format(sep, filename, img_code, fmeta, vinfo, ainfo)
	elif isinstance(item, ImageSet):
		fmeta = '{0}x ({1}×{2} px)'.format(item.img_count, item.resolution[0], item.resolution[1])
		fsize = '{}'.format(item.filesize)

		return '[b]{1}[/b][size=0] {0} {3} {0} {4} [/size]{2}\n' \
			.format(sep, filename, img_code, fmeta, fsize)
	else:
		print('ERROR: script tried to parse an unknown object! This should never happen.')
		return ''


def format_row_separator(separator, column_names):
	"""
	Formats a separator row with the current parsing directory. For prettier organizing of rows.
	"""
	dir_name = separator.directory

	if config.opts['output_as_table']:
		td_opts = 'nb'  # TODO nb support is common?
		if config.opts['cTSEPF']:
			td_inner = '[size=3][color={1}][b]{0}[/b][/color][/size]'.format(dir_name, config.opts['cTSEPF'])
		else:
			td_inner = '[size=3][b]{0}[/b][/size]'.format(dir_name)
		tr = ('[tr={1}][td={2}][align=left]{0}[/align][/td]'.format(td_inner, config.opts['cTSEPBG'], td_opts))
		for name in column_names[1:]:
			tr += '[td={1}]{0}[/td]'.format(name, td_opts)
		tr += '[/tr]\n'
		return tr
	else:
		# just a boring row with the directory name
		return '[size=2]- [b][i]{}[/i][/b][/size]\n'.format(dir_name)


def format_fullsize_section(_list):
	"""
	Create a list of all the full-sized images for fast single-click browsing. But requires support for [spoiler] tags.
	"""
	output = ''

	# set up the table header title before the actual content
	if config.opts['output_as_table'] and config.opts['output_table_titles']:
		output += ('[table=100%][tr][td={1}][bg={2}][align=center][font={4}][size=5][color={3}]'
					'[b]{0}[/b][/color][/size][/font][/align][/bg][/td][/tr][/table]'
					.format(config.opts['tFullSizeSS'], config.opts['cTHBD'], config.opts['cTHBG'],
							config.opts['cTHF'], config.opts['fTH']))

	content = ''
	previous_item_was_separator = False
	for _id, item in enumerate(_list):
		if isinstance(item, Separator):
			if _id > 0:
				content += '[/spoiler]\n\n'
			content += '[spoiler={}]'.format(item.directory)
			previous_item_was_separator = True
			continue
		elif _id == 0:
			content += '[spoiler={}]'.format(config.opts['tFullSizeShow'])
			previous_item_was_separator = True

		if not previous_item_was_separator:
			content += '\n'

		previous_item_was_separator = False
		img_match = item['img_match_fullsize']
		if img_match and len(img_match) == 1:
			content += '[img]{0}[/img]'.format(img_match[0]['bbimg'])
		elif img_match:
			content += '[color={}]Image conflict for: {}![/color]'.format(cWARN, item['item'].filename)
		else:
			content += '[color={}]Image missing for: {}![/color]'.format(cERR, item['item'].filename)

	content += '[/spoiler]'

	output += ('[bg={1}]\n[align=center][size=2]{0}[/size][/align]\n[/bg]\n\n'.format(content, config.opts['cTBBG']))

	return output


def metadata_cleanup(clip):
	"""
	Performs various steps in order to check the integrity of the data, as well as cleaning up ugly inputs.
	All this is very specific to MediaInfo, and might even break with versions other than MediaInfo 0.7.93. YMMV
	"""
	# some missing meta-data cleanup
	if clip.vbitrate_alt and (not clip.vbitrate or len(str(clip.vbitrate)) <= 5):
		setattr(clip, 'vbitrate', clip.vbitrate_alt)

	if clip.vframerate:
		setattr(clip, 'vframerate', clip.vframerate[:5])

	if clip.vframerate_alt:
		setattr(clip, 'vframerate_alt', clip.vframerate_alt[:5])
		# fix for some WMV/MKV files
		if not clip.vframerate or (clip.vframerate and len(str(clip.vframerate)) < 2):
			setattr(clip, 'vframerate', clip.vframerate_alt)

	if clip.vscantype:
		setattr(clip, 'vscantype', clip.vscantype[:1].lower())
	else:
		setattr(clip, 'vscantype', '')

	# vcodec cleanup
	if clip.vcodec:
		vcodec = clip.vcodec.upper()

		if 'AVC' in vcodec:
			vcodec = 'AVC'
		elif 'H264' in vcodec:
			vcodec = 'AVC'
		elif 'HEVC' in vcodec:
			vcodec = 'HEVC'
		elif 'XVID' in vcodec:
			vcodec = 'XviD'
		elif 'DIVX' in vcodec:
			vcodec = 'DivX'
		elif 'DX50' in vcodec:
			vcodec = 'DivX5'
		elif 'DIV3' in vcodec:
			vcodec = 'DivX3'
		elif 'MP43' in vcodec:
			vcodec = 'MP4v3'
		elif 'MP42' in vcodec:
			vcodec = 'MP4v2'
		elif '263' in vcodec:
			vcodec = 'H.263'
		elif len(vcodec) <= 2 and clip.vcodec_alt:
			vcodec = clip.vcodec_alt
	elif clip.vcodec_alt:
		vcodec = clip.vcodec_alt
	else:
		vcodec = '?'

	# final vcodec cleanup
	if 'Visual' in vcodec:
		vcodec = 'MP4v2'
	elif 'MPEG' in vcodec:
		vcodec = 'MPEG'
	setattr(clip, 'vcodec', vcodec)

	# acodec cleanup
	if clip.acodec and 'MPEG' in clip.acodec and clip.aprofile:
		# catches MP2 whereas codec_id_hint does not
		setattr(clip, 'acodec', 'MP' + clip.aprofile[-1:])
	elif clip.acodec and 'AC-3' in clip.acodec:
		setattr(clip, 'acodec', 'AC3')
	if not clip.abitrate:
		setattr(clip, 'abitrate', '?')

	# format video length
	if clip.length:
		length = clip.length / 1000
		seconds = int(length % 60)
		length /= 60
		minutes = int(length % 60)
		length /= 60
		hours = int(length % 24)
		setattr(clip, 'length', '{0:02d}:{1:02d}:{2:02d}'.format(hours, minutes, seconds))

	# format file size
	setattr(clip, 'filesize', readable_number(clip.filesize))

	# format video bit-rate
	setattr(clip, 'vbitrate', readable_number(clip.vbitrate, 'b/s', 1000.0, 10000.0, 1))

	# format audio bit-rate
	try:
		setattr(clip, 'abitrate', readable_number(clip.abitrate, 'b/s', 1000.0, 1000.0, 0))
	except TypeError:
		pass

	# format audio sample-rate
	if clip.asample:
		try:
			setattr(clip, 'asample', readable_number(clip.asample, 'Hz', 1000.0, 1000.0, 1))
		except TypeError:
			if '/' in clip.asample:
				clean_asample = int(clip.asample.split('/', 1)[0].strip())
				setattr(clip, 'asample', readable_number(clean_asample, 'Hz', 1000.0, 1000.0, 1))
			else:
				pass

	return clip


def readable_number(num, suffix='iB', base=1024.0, ceiling=1024.0, decimals=2):
	"""
	Converts large numbers to human readable formats.
	"""
	for unit in ['', 'k', 'M', 'G', 'T', 'P', 'E', 'Z']:
		if abs(num) < ceiling:
			# just a small hack because I prefer 3 digits, so it will be "1.23 GiB", "45.9 MiB", and "768 MiB"
			if len(str(round(num))) >= 3 or decimals == 0:
				return '{0:.0f} {1}{2}'.format(num, unit, suffix)
			elif len(str(round(num))) >= 2 or decimals == 1:
				return '{0:.1f} {1}{2}'.format(num, unit, suffix)
			else:
				return '{0:.2f} {1}{2}'.format(num, unit, suffix)
		num /= base
	return "%.1f %s%s" % (num, 'Yi', suffix)


def get_img_list(file_img_list, is_alt=False):
	"""
	Generates an image-list based on a txt file provided by the user. The txt file's content should be copy-pasted
	from the output of the image-hosting website (after uploading the images as a batch). It should work, whether the
	output is BBCode or just a plain list of image-URLs. As requested, some more dubious image-hosts have been added ;).
	"""
	try:
		file = open(file_img_list)
	except (IOError, OSError):
		if is_alt:
			# We always check for the _alt.txt image-list. But if there doesn't appear to be a file to parse,
			# we should assume that the user simply doesn't with to use this feature, and just ignore it.
			print('NOTICE: No corresponding alternative image-list found. Looked for: {}'.format(file_img_list))
		else:
			print('WARNING: No corresponding image-list found! Looked for: {}'.format(file_img_list))
		return

	img_items = file.read().split()

	if not img_items:
		print('WARNING: Image-list file ({}) seems to be empty!'.format(file_img_list))
		return

	if 'imagebam.' in img_items[0]:
		img_host = 'imagebam'
	elif 'pixhost.' in img_items[0]:
		img_host = 'pixhost'
	elif 'postimg.' in img_items[0] or 'pixxxels.' in img_items[0]:  # same format
		img_host = 'postimg'
	elif 'imagevenue.' in img_items[0]:
		img_host = 'imagevenue'
	elif 'imagetwist.' in img_items[0]:
		img_host = 'imagetwist'
	elif 'imgchili.' in img_items[0]:
		img_host = 'imgchili'
	elif 'jerking.empornium.' in img_items[0]:
		img_host = 'jerking'
	elif 'fapping.empornium.' in img_items[0]:
		img_host = 'fapping'
	else:
		print('WARNING: Unsupported image-host used in {}!\n'
			'Only use imagebam.com, pixhost.org, postimg.org, imagetwist.com, imagevenue.com, imgchili.net, '
			'pixxxels.org, jerking.empornium.ph or fapping.empornium.sx'.format(file_img_list))
		if config.debug_imghost_slugs:
			img_host = 'unknown image-host'
		else:
			return

	img_list = []

	for item in img_items:
		# get the URL to the image to be displayed
		bbimg = re.search("\[(?:img|IMG)\](.*?)\[/(?:img|IMG)\]", item)
		if bbimg and bbimg.group(1) is not None:
			bbimg = bbimg.group(1).rstrip()
		else:
			bbimg = item.rstrip()

		# get the URL to the full-sized image (if using BBCode)
		bburl = re.search("\[(?:url|URL)=(.*?)\]\[(?:img|IMG)\]", item)
		if bburl and bburl.group(1) is not None:
			bburl = bburl.group(1).rstrip()
		else:
			bburl = False

		# Getting the slug. Different hosts all use different rules when it comes to generating their url slugs.
		# Basically we will ignore all the prepended and appended characters because we will match using the
		# index substring method in match_slug().

		# for ImageTwist, there is no reliable slug in the [img] tag, so we use the [url] tag instead
		slug = bburl if img_host == 'imagetwist' else bbimg

		# strip image extension (probably .jpg or .png)
		slug, ext = os.path.splitext(os.path.basename(urlparse(slug).path))

		# if the extension of the url isn't a common image extension, it's probably a link to a website or garbage.
		if ext.lower() not in ['.jpg', '.jpeg', '.png', '.gif']:
			continue

		# ImageBam uses part (the first 6 chars) of the MD5 hash of the uploaded file to generate its slug.
		# To prevent false positives during matching, we will truncate the slug to this length.
		if img_host == 'imagebam':
			slug = slug[:6]

		# populate the image list
		img_list.append({'slug': slug, 'bbimg': bbimg, 'bburl': bburl})

	file.close()

	if not img_list:
		print('WARNING: No valid image data in image-list! Check the contents of: {}'.format(file_img_list))
	else:
		return {'host': img_host, 'img_list': img_list, 'file': file_img_list}


def get_screenshot_hash(filename, filepath, algorithm, strlen):
	"""
	Most image-hosts like ImageBam randomize the image's file-name after uploading, making the matching of video-clip
	file-names with the online image location very difficult or completely impossible. Luckily, some of them use (parts)
	of the file-hash to generate the file-name. We can exploit this and still match files.
	"""
	# screenshot generators can sometimes strip the clip file-extension, so we have to check both variants
	filename_variants = [os.path.splitext(filename)[0], filename]

	# make all the variants of file-names to look for (case-sensitive Unix is a PITA here)
	common_ss_ext = ['.jpg', '.jpeg', '.gif', '.png', '.JPG', '.JPEG', '.GIF', '.PNG']
	search_variants = []
	for filename_variant in filename_variants:
		for ss_ext in common_ss_ext:
			search_variants.append(filename_variant + ss_ext)

	# all the directories we should traverse when searching for images (case-sensitive Unix is a PITA again)
	common_ss_subdirs = ['ss', 'scr', 'screens', 'screenshots', 'th', 'thumbs', 'thumbnails',
						'SS', 'SCR', 'Screens', 'Screenshots', 'TH', 'Thumbs', 'Thumbnails']
	search_dirs = [filepath]  # same path as the actual video file, so the image would be in the same dir

	for ss_subdir in common_ss_subdirs:
		# commonly named sub-dirs of the same path as the actual video file
		search_dirs.append(os.path.join(filepath, ss_subdir))

	# path of video relative to master path
	relpath = os.path.relpath(filepath, config.opts['media_dir'])
	if relpath is not '.':
		for ss_subdir in common_ss_subdirs:
			# for when screenshots are located at the top level dir, but have the same dir structure as the clips
			search_dirs.append(os.path.join(config.opts['media_dir'], ss_subdir, relpath))

	for ss_subdir in common_ss_subdirs:
		# commonly named sub-dirs of the top level media_dir (when recursive clip searching is used)
		search_dirs.append(os.path.join(config.opts['media_dir'], ss_subdir))

	# perform the actual search by traversing all the directories listed, and test all file-name variants in those dirs
	ss_found = None
	for path in search_dirs:
		for variant in search_variants:
			img_path = os.path.join(path, variant)
			if os.path.isfile(img_path):
				ss_found = img_path
				break
		else:
			continue
		break

	# generate the hash for the found image
	if ss_found:
		try:
			img = open(ss_found, 'rb').read()
		except (IOError, OSError):
			print('ERROR: Couldn\'t open the following image to calculate hash: {}'.format(ss_found))
			return

		if 'md5' in algorithm:
			print('calculating MD5 hash for: {}'.format(ss_found))
			return md5(img).hexdigest()[:strlen]
	else:
		print('WARNING: Couldn\'t find screenshot file for: {}'.format(filename))


def slugify(filename, img_host):
	"""
	Generate a filename slug similar to that used by the image-host so we can compare them.
	These rules were derived by trial and error, using as many possible file-name characters as possible.
	But they probably don't match the host's rules perfectly.
	"""
	# remove the file-extension
	slug = os.path.splitext(filename)[0]
	slug_unicode = unicodedata.normalize('NFKD', slug).encode('ascii', 'ignore').decode('ascii')

	if img_host == 'pixhost':
		slug = re.sub('[^\w]', '-', slug_unicode[:80].lower())
		slug = re.sub('-+', '-', slug).strip('-')
	elif img_host == 'postimg':
		slug = re.sub('[^a-zA-Z0-9]', '_', slug[:48])
		# PostImg has some weird behavior, it changes every occurrence of 'aB', to 'a_B'
		slug = re.sub(r'([a-z])([A-Z])', r'\1_\2', slug)
		slug = re.sub('_+', '_', slug).strip('_')
	elif img_host == 'imagetwist':
		slug = re.sub('#+', '#', slug_unicode)
		slug = re.sub('[^\w\s.\-]', '_', slug).strip()
		slug = re.sub('[\s]+', '_', slug)
	elif img_host == 'imagevenue':
		slug = re.sub('[^\w\s.\-]', '', slug_unicode).replace('-', '_').strip()
		slug = re.sub('[\s]+', '', slug)
	elif img_host == 'imgchili':
		# imgChili seems to have the weirdest url generator yet, they probably use a different decoder
		slug = re.sub('[&]', '__', slug.lower())
		slug = re.sub('[, %#+=@$-]', '_', slug[:29].encode('ascii', 'ignore').decode('ascii'))
	elif img_host == 'jerking':
		slug = re.sub('[^\w\s.-]', '', slug_unicode).strip()
		slug = re.sub('[\s]+', '', slug)
	elif img_host == 'fapping':
		slug = re.sub('[^\w\s-]|[_]', '', slug_unicode).strip()
		slug = re.sub('[\s]+', '_', slug)
	elif config.debug_imghost_slugs:
		# best guess for an unsupported host
		slug = re.sub('[^\w\s.-]', '', slug_unicode).strip()
		slug = re.sub('[\s]+', '_', slug)
	else:
		return

	return slug


def match_slug(img_list, file_slug, file_img_list):
	"""
	Lookup the online url(s) for the corresponding slug in the local image list (see get_img_list()).
	Returns (all) matches, including false-positives unfortunately.
	"""
	# file slugs can be None when get_screenshot_hash() isn't successful
	if not file_slug:
		return

	matches = []
	for img in img_list:
		try:
			match_pos = img['slug'].index(file_slug)
			img['match_pos'] = match_pos
			matches.append(img)
		except ValueError:
			continue

	if len(matches) > 1:
		print('WARNING: Multiple corresponding image-urls found for "{}" in: {}'.format(file_slug, file_img_list))
		return matches
	elif matches:
		return matches
	else:
		print('WARNING: No corresponding image-url found for "{}" in: {}'.format(file_slug, file_img_list))


def debug_imghost_matching(_dir='../tests/image-hosts/'):
	"""
	Debug method for easier testing of image-host output. Compares a the file-names of a collection of images to 
	the output of various image-hosts and provides digestible information on how the slugs are formed.
	"""
	img_dir = os.path.normpath(os.path.join(_dir, 'images'))

	# from: https://svn.blender.org/svnroot/bf-blender/trunk/blender/build_files/scons/tools/bcolors.py
	c = {
		'HEAD': '\033[95m',
		'OKBL': '\033[94m',
		'OKGR': '\033[92m',
		'WARN': '\033[93m',
		'FAIL': '\033[91m',
		'ENDC': '\033[0m',
		'BOLD': '\033[1m',
		'ULIN': '\033[4m'
	}

	try:
		test_names = os.listdir(img_dir)
	except (IOError, OSError):
		print('{1}ERROR: "{0}" doesn\'t exist!{2}'.format(img_dir, c['FAIL'], c['ENDC']))
		return

	# test_names = test_names.read().splitlines()
	if not test_names:
		print('{1}ERROR: No image-files found for testing in:{2} {0}'.format(img_dir, c['FAIL'], c['ENDC']))
		return

	# try each image-host output file
	for host_file in os.listdir(_dir):
		if host_file.lower().endswith('.txt'):
			print('\n{1}TEST HOST{2}  : {0}'.format(host_file, c['HEAD'], c['ENDC']))

			img_data = get_img_list(os.path.join(_dir, host_file))
			if not img_data:
				continue

			# for each file-name specified in the test file, we will check the host's output to find a match
			index = 0
			for name in test_names:
				print('{1}file-name{2}  : {0}'.format(name, c['ULIN'], c['ENDC']))

				# get the file-name slug
				if 'imagebam' in img_data['host']:
					file_slug = get_screenshot_hash(name, img_dir, 'md5', 6)
				else:
					file_slug = slugify(name, img_data['host'])

				if not file_slug:
					print('{0}NO FILE-SLUG! - check message{1}'.format(c['FAIL'], c['ENDC']))
					continue

				# check_singular = True: will try to match each individual index/row of the file-names with the same
				# index/row of the host's output. This will eliminate any false positives. Better for developing.
				#
				# check_singular = False: will try to match each file-name with all items in the img_list (the hosts's
				# output). This can include false positives (multiple matches). Better for debugging.

				check_singular = False

				try:
					host_slug = dict(img_data['img_list'][index])['slug']
					print('host-slug  : {}'.format(host_slug))
				except (IndexError, KeyError):
					host_slug = False
					print('host-slug  : {2}ERROR: No image-host found at index [{0}] for:{3} {1}'
						.format(index, name, c['FAIL'], c['ENDC']))
					if check_singular:
						continue

				if check_singular:
					img_list = [{'slug': host_slug, 'bbimg': None, 'bburl': None}]
				else:
					img_list = img_data['img_list']

				# do the matching, and output something understandable (hopefully)
				matches = match_slug(img_list, file_slug, host_file)

				if matches and len(matches) == 1:
					print('file-slug  : {1}{0}'.format(file_slug, ' ' * matches[0]['match_pos']))
					print('{}MATCH!{}'.format(c['OKGR'], c['ENDC']))
				elif matches and len(matches) >= 2:
					match_index = 0
					for match in list(matches):
						print('host-slug {1}: {0}'.format(match['slug'], match_index))
						print('file-slug {1}: {2}{0}'.format(file_slug, match_index, ' ' * match['match_pos']))
						match_index += 1
					print('{}MULTIPLE MATCHES!{}'.format(c['WARN'], c['ENDC']))
				else:
					print('file-slug  : {}'.format(file_slug))
					print('{0}NO MATCH!{1}'.format(c['FAIL'], c['ENDC']))

				index += 1


def generate_tags(filename):
	"""
	Generates tags for all performers present in the file-names as a whole (YMMV).
	This is handy for music videos, which often have credited performers in the file-name rather than the meta-data.
	All tags will be common format. So "Michael Jackson ft. Bruno Mars - Song" outputs "michael.jackson bruno.mars"
	Note that this will NOT capture "avicii" in something like: Performer - Song (Avicii Remix)
	"""
	global tags
	segments = []

	# find the names located before the movie title (everything before the " - " separator)
	if ' - ' in filename:
		match_begin = filename.split(' - ', 1)[0]
		if match_begin is not None:
			segments.append(match_begin)

	# find the names located in parenthesis using the "(w. ###)" or "(ft. ###)" or "(feat. ###)" format
	match_in_parenthesis = re.findall('\((?:featuring|feat.|ft.|with|w.)(.*?)\)', filename)
	if match_in_parenthesis:
		for match in match_in_parenthesis:
			segments.append(match)

	if segments:
		segments = ', '.join(segments)
		segments = re.split(' and |[&,;]', segments)
		for tag in segments:
			if len(tag) > 2:
				tag = re.sub('\.+', '.', tag.strip().lower().replace(' ', '.'))
				ignored_tags = ('various', 'others', 'multiple', 'downloaded', 'mixed')

				# some tags to exclude, and performers generally don't have underscores in their names
				if '_' in tag:
					continue
				elif any(test in tag for test in ignored_tags):
					continue
				elif tag not in tags:
					tags.append(tag)


def generate_all_layouts(output, prepared_items, has_alts):
	"""
	Runs format_collection() multiple times with differing settings to generate all possible layouts.
	"""
	original_opts = copy.copy(config.opts)

	variants = [[True, True, True],
				[True, False, True],
				[True, True, False],
				[True, False, False],
				[False, False, True],
				[False, True, False],
				[False, False, False]]

	for opts in variants:
		config.opts['output_as_table'] = opts[0]
		config.opts['embed_images'] = opts[1]
		config.opts['whole_filename_is_link'] = opts[2]

		# output the corresponding command-line options if we are doing an all_layouts loop, for easy reference
		command_line_options = ''
		if not config.opts['output_as_table']:
			command_line_options += '-l '
		if not config.opts['embed_images']:
			command_line_options += '-u '
		if not config.opts['whole_filename_is_link']:
			command_line_options += '-t '

		output.write('\n\nCommand-line options: [size=3][b]{}[/b][/size]\n\n'.format(command_line_options))

		for _type, _list in prepared_items.items():
			if not _list:
				continue
			output.write(format_collection(_type, _list, has_alts))

	config.opts = original_opts


class Clip(object):
	def __init__(self, filepath, filename, filesize, length, vcodec, vcodec_alt, vbitrate, vbitrate_alt,
				vwidth, vheight, vscantype, vframerate, vframerate_alt,
				acodec, abitrate, asample, aprofile):

		self.filepath = filepath
		self.filename = filename
		self.filesize = filesize
		self.length = length

		self.vcodec = vcodec
		self.vcodec_alt = vcodec_alt
		self.vbitrate = vbitrate
		self.vbitrate_alt = vbitrate_alt
		self.vwidth = vwidth
		self.vheight = vheight
		self.vscantype = vscantype
		self.vframerate = vframerate
		self.vframerate_alt = vframerate_alt

		self.acodec = acodec
		self.abitrate = abitrate
		self.asample = asample
		self.aprofile = aprofile


class ImageSet(object):
	def __init__(self, filepath, filename, filesize, orig_size, img_count, resolution):

		self.filepath = filepath
		self.filename = filename
		self.filesize = filesize

		self.orig_size = orig_size
		self.img_count = img_count
		self.resolution = resolution


class Separator(object):
	def __init__(self, directory):

		self.directory = directory
