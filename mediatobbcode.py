# encoding: utf-8

import getopt
import os
import re
import sys
import unicodedata
import webbrowser
from collections import OrderedDict
from copy import deepcopy
from hashlib import md5
from ruamel import yaml
from urllib.parse import urlparse

from PyQt5.QtCore import Qt, QObject, QThread, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QColor, QFont, QIcon, QTextCursor
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QGridLayout, QHBoxLayout, QGroupBox, QTabWidget,\
	QLabel, QLineEdit, QPlainTextEdit, QCheckBox, QPushButton, QFrame, QFileDialog, QColorDialog

"""
[input options]

@ media_dir
The directory to use when looking for media files to process.

@ output_dir
The output/working directory, where image-host data should be located, and _output.txt files are written.

@ recursive
Will enable recursive searching for files. Meaning it will include all sub-directories of "media_dir".

@ parse_zip
Enables parsing of compressed (ZIP) archives for image-sets. All image-sets will be output below other parsed media.
Requires Pillow.

[output options]

@ output_as_table
Generate table output. If not, a simpler (ugly) flat list will be generated.
Requires support for [table] tags by the BBCode engine used by your website.

@ output_table_titles
Generate nice heading title(s) above the table/list.
Requires support for [table] tags by the BBCode engine used by your website.

@ output_individual
Generate a separate output file for each directory successfully traversed recursively.
Only applies if "recursive = True".

@ output_separators
Generate separators (with the directory name) when switching directories in recursive mode.
Only applies if "recursive = True" and "output_individual = False"

@ embed_images
Embed the image/thumbnails in the output. Otherwise a link to the image will be embedded.
I strongly advise using small/medium thumbnail images if you want to embed them _and_ your website doesn't support
the [thumb] BBCode tag, or they will break the table layout.
Requires support for [spoiler] tags by the BBCode engine used by your website.

@ output_bbcode_thumb
Determines if embedded images will use the [thumb] BBCode tag, or [img].

@ whole_filename_is_link
Instead of having a small link next to the file-name, to the full-sized image, the whole title will be a link.
When combined with "embed_images", this will make the whole file-name a spoiler tag.

@ suppress_img_warnings
Prevents error/warning messages from appearing in the output if no suitable image/link was found.

@ all_layouts
Will output all 7 different layout options below each other, easy for testing and picking your favorite.
Note that this will include layouts with [table] and [spoiler] tags, so be careful if these aren't supported.

@ output_html
Converts the output BBCode directly to HTML. This can be used for rapid testing.
Requires bbcode module.

[image-list options]

@imagelist_pri
Path to the primary image-list file. This txt file contains BBCode output from the primary image-host.

@imagelist_alt
Path to the secondary (alternative) image-list file. This txt file contains BBCode output from the secondary image-host.

@imagelist_fsz
Path to the full-size image-list file. This can be used to output all images in-line above the normal output.

@use_imagelist_fsz
Whether to use the full-size image-list to display all full-sized images in-line.

@use_primary_as_fsz
Will switch to using the primary image-list as the full-sized image-list, which may be suitable in some situaitons.
"""

# default config with additional information for the GUI
config = OrderedDict([
	('iopts', OrderedDict([
		('media_dir', ['./videos', 'Media dir']),
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
		('imagelist_pri', ['', 'string', 'Primary image-list file']),
		('imagelist_alt', ['', 'string', 'Secondary image-list file']),
		('use_imagelist_fsz', [False, 'bool', 'Add list of full-sized images to output']),
		('use_primary_as_fsz', [False, 'bool', 'Use primary image-list for full-sized output']),
		('imagelist_fsz', ['', 'string', 'Full-size image-list file'])
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

opts = dict()  # Don't touch!
layouts_busy = False  # Don't touch! Used to determine if we are still in the all_layouts loop.
layouts_last = False  # Don't touch! Used to only run format_html_output once.
debug_imghost_slugs = False  # For debugging. Only available from the command-line.
cERR = '#F00'  # output color for errors
cWARN = '#F80'  # output color for warnings

author = 'PayBas'
author_url = 'https://github.com/PayBas'
script = 'MediaToBBCode.py'
script_url = 'https://github.com/PayBas/MediaToBBCode'
version = '1.2.0'
compile_date = '16-03-2017'
credits_bbcode = 'Output script by [url={}]PayBas[/url].'.format(script_url)


def populate_opts():
	"""
	Put all the config options into one big (but simple) dictionary which can be manipulated by the command-line or GUI.
	This is much easier to work with than the full _config_ dictionary.
	"""
	global opts

	for group in config.values():
		for opt, values in group.items():
			opts[opt] = values[0]


def set_paths_and_run():
	"""
	Sanitizes and sets the correct input and output directories, before starting the parsing process.
	"""
	global opts

	# set the correct output_dir
	if not opts['output_dir'] and not opts['media_dir']:
		print('ERROR: no media directory specified!')
		return
	elif not opts['output_dir']:
		# no output_dir specified, so we will output to the media_dir
		opts['output_dir'] = os.path.normpath(os.path.expanduser(opts['media_dir']))
	else:
		opts['output_dir'] = os.path.normpath(os.path.expanduser(opts['output_dir']))

	# set the correct media_dir
	opts['media_dir'] = os.path.normpath(os.path.expanduser(opts['media_dir']))
	print('using media_dir  = ' + opts['media_dir'])
	print('using output_dir = ' + opts['output_dir'])

	parse_media_files()


def parse_media_files():
	"""
	Uses the pymediainfo module to parse each file in a directory (recursively), and extract media information from
	each video-clip. It creates Clip objects and stores it in a clips list for later use. Also detects image-sets.
	Requires MediaInfo and pymediainfo
	"""
	try:
		from pymediainfo import MediaInfo
	except ImportError:
		print('\nERROR: Couldn\'t import MediaInfo module from pymediainfo!\n')
		return

	clips = []
	imagesets = []
	ran_at_all = False  # canary - general
	parsed_at_all = False  # canary - for when output_individual has cleared clips[] after sending to output

	# ignore some common file-extensions often found alongside videos
	# TODO unix is case-sensitive :( and switch to include rather than exclude
	skip_ext = ['.jpg', '.JPG', '.jpeg', 'JPEG', '.png', '.PNG', '.gif', '.GIF', '.psd', '.ai',
				'.txt', '.nfo', '.NFO', '.doc', '.xml', '.csv', '.pdf', '.part',
				'.flac', '.mp3', '.acc', '.wav', '.pls', '.m3u', '.torrent']
	zip_ext = ['.zip', '.ZIP', '.7z', '.7Z', '.gz', '.GZ', '.tar', '.TAR', '.rar', '.RAR']
	if opts['parse_zip']:
		zip_ext = tuple(zip_ext)
	else:
		skip_ext.extend(zip_ext)
	skip_ext = tuple(skip_ext)

	for root, dirs, files in os.walk(opts['media_dir']):
		print('\nSWITCH dir: {}'.format(root))
		new_dir = True
		ran_at_all = True

		for file in files:
			# quickly ignore non-video files to save resources
			if file.endswith(skip_ext):
				print(' skipped file: {}'.format(file))
				continue
			# if parse_zip is enabled, check ZIP files to see if it's an image-set
			elif opts['parse_zip'] and file.endswith(zip_ext):
				imgset = parse_zip_files(root, file)
				if imgset:
					imagesets.append(imgset)
				continue

			media_info = MediaInfo.parse(os.path.join(root, file))
			track_gen = track_vid = track_aud = None

			# get the first video and audio tracks, the rest will be ignored
			for track in media_info.tracks:
				if track.track_type == 'General' and not track_gen:
					track_gen = track
				elif track.track_type == 'Video' and not track_vid:
					track_vid = track
				elif track.track_type == 'Audio' and not track_aud:
					track_aud = track

			# get the useful bits from the track objects
			if track_vid:
				print(' attempt file: {}'.format(file))

				# create a separator with the relative directory, but only if it's the first valid file in the dir
				if new_dir and opts['recursive'] and opts['output_separators'] and not opts['output_individual']:
					current_dir = os.path.relpath(root, opts['media_dir'])
					if current_dir is not '.':
						clips.append(current_dir)
					new_dir = False

				filepath = os.path.dirname(track_gen.complete_name)
				filename = track_gen.file_name + '.' + track_gen.file_extension
				filesize = track_gen.file_size
				length = track_gen.duration

				vcodec = track_vid.codec_id
				vcodec_alt = track_vid.format
				vbitrate = track_vid.bit_rate
				vbitrate_alt = track_gen.overall_bit_rate
				vwidth = track_vid.width
				vheight = track_vid.height
				vscantype = track_vid.scan_type
				vframerate = track_vid.frame_rate
				vframerate_alt = track_vid.nominal_frame_rate

				# crazy, I know, but some freaky videos don't have any audio tracks :S
				if not track_aud:
					acodec = abitrate = asample = aprofile = None
				else:
					acodec = track_aud.format
					abitrate = track_aud.bit_rate
					asample = track_aud.sampling_rate
					aprofile = track_aud.format_profile

				# create Clip object for easier manipulation and passing around
				clip = Clip(filepath, filename, filesize, length, vcodec, vcodec_alt,
							vbitrate, vbitrate_alt, vwidth, vheight, vscantype, vframerate, vframerate_alt,
							acodec, abitrate, asample, aprofile)
				clips.append(metadata_cleanup(clip))
				print(' parsed file : {}'.format(file))
			else:
				print('ERROR parsing: {}  -  not a video file?'.format(file))

		# break after top level if we don't want recursive parsing
		if not opts['recursive']:
			break
		elif opts['output_individual'] and (clips or imagesets):
			# output each dir as a separate file, so we need to reset the clips after each successfully parsed dir
			parsed_at_all = True
			format_final_output(clips + imagesets, root)
			clips = []
			imagesets = []

	if not ran_at_all:
		print('ERROR: invalid directory for: {}'.format(opts['media_dir']))
	elif not clips and not imagesets and not parsed_at_all:
		print('ERROR: no valid media files found in: {}'.format(opts['media_dir']))
	elif not opts['output_individual']:
		format_final_output(clips + imagesets, opts['media_dir'])


def parse_zip_files(root, file):  # TODO add support for rar, 7z, tar, etc.
	"""
	Processes a compressed archive and attempts to get information on the image-set located therein.
	We could have used MediaInfo for this too, but Pillow is easier and more reliable.
	Requires Pillow
	"""
	from zipfile import ZipFile, BadZipFile
	try:
		from PIL import Image
	except ImportError:
		print('\nERROR: Couldn\'t import Pillow module!\n')
		return False

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

	return False


def format_final_output(items, source):
	"""
	Takes the items (Clips and/or ImageSets) generated from a dir parsing session and determines the formatting to use,
	combines them with image-host data, and finally writing to the output.
	"""
	# no items (clips/image-sets)? something is wrong
	if not items:
		print('ERROR: No media clips found! The script shouldn\'t even have gotten this far. o_O')
		return

	# setup some file locations for input/output
	if opts['output_individual']:
		# When creating an output file for each parsed directory, we don't want to have to create directories to
		# the same depth as the source files (in order to keep the file structure). So for directories deeper than
		# media_dir + 1, we concatenate the dir-names into a long string.
		relpath = os.path.relpath(source, opts['media_dir'])

		if relpath == '.':
			working_file = os.path.join(opts['output_dir'], os.path.basename(source))
		else:
			working_file = os.path.join(opts['output_dir'], relpath.replace('\\', '__').replace('/', '__'))
	else:
		working_file = os.path.join(opts['output_dir'], os.path.basename(source))

	file_output = working_file + '_output.txt'
	file_output_html = working_file + '_output.html'
	file_img_list = opts['imagelist_pri'] if opts['imagelist_pri'] else working_file + '.txt'
	file_img_list_alt = opts['imagelist_alt'] if opts['imagelist_alt'] else working_file + '_alt.txt'
	file_img_list_fullsize = opts['imagelist_fsz'] if opts['imagelist_fsz'] else working_file + '_fullsize.txt'

	# create an output loop for generating all different layouts
	if opts['all_layouts'] and not layouts_busy:
		try:
			open(file_output, 'w+').close()  # clear the current output file before starting the loop
		except (IOError, OSError):
			print('ERROR: Couldn\'t create output file: {}  (invalid directory?)'.format(file_output))
			return
		generate_all_layouts(items, source)
		return

	# append the output of every cycle rather than truncating the entire output file
	write_mode = 'a+' if opts['all_layouts'] else 'w+'
	try:
		output = open(file_output, write_mode, encoding='utf-8')
	except (IOError, OSError):
		print('ERROR: Couldn\'t create output file: {}  (invalid directory?)'.format(file_output))
		return

	# stop if this combination is active, it will produce a mess
	if opts['whole_filename_is_link'] and opts['embed_images'] and not opts['output_as_table']:
		print('Using the parameters "whole_filename_is_link" and "embed_images" and not "output_as_table"'
			' is the only invalid combination\n\n')
		output.close()
		return

	# TODO: create a spoiler for each dir when using recursive
	# try to create a list of all the full-sized images (if present) for fast single-click browsing
	if opts['use_imagelist_fsz'] and not opts['all_layouts']:
		if opts['use_primary_as_fsz']:
			file_img_list_fullsize = file_img_list
		try:
			fs_file = open(file_img_list_fullsize)
			fs_list = fs_file.read().split()

			# set up the table header title before the actual content
			if opts['output_as_table'] and opts['output_table_titles']:
				output.write('[table=100%][tr][td={1}][bg={2}][align=center][font={4}][size=5][color={3}]'
							'[b]{0}[/b][/color][/size][/font][/align][/bg][/td][/tr][/table]'
							.format(opts['tFullSizeSS'], opts['cTHBD'], opts['cTHBG'], opts['cTHF'], opts['fTH']))
			fs_content = ''
			first = True
			for line in fs_list:
				if first:
					fs_content += line
					first = False
				else:
					fs_content += '\n' + line

			output.write('[bg={2}]\n[align=center][size=2][spoiler={1}]{0}[/spoiler][/size][/align]\n[/bg]\n\n'
						.format(fs_content, opts['tFullSizeShow'], opts['cTBBG']))

		except (IOError, OSError):
			print('NOTICE: No full-size image-list detected. Looked for: {}'.format(file_img_list_fullsize))
			pass

	# get the image data for later use; img_data is a string with error details if no compatible image data was found
	img_data = get_img_list(file_img_list)
	if isinstance(img_data, str):
		img_error_msg = img_data
		# just in case users use the script wrong (by only providing _fullsize.txt containing direct links)
		img_data = get_img_list(file_img_list_fullsize)
		if isinstance(img_data, str):
			output.write(img_error_msg + '\n\n')
			img_data = None

	# get a second set of image data to provide alternative image-links in case the primary image-host should die
	has_alts = False
	img_data_alt = get_img_list(file_img_list_alt, True)
	if isinstance(img_data_alt, str):
		output.write(img_data_alt + '\n\n')
		img_data_alt = None
	elif img_data_alt:
		has_alts = True

	# output the corresponding command-line options if we are doing an all_layouts loop, for easy reference
	if opts['all_layouts'] and layouts_busy:
		command_line_options = ''
		if not opts['output_as_table']:
			command_line_options += '-l '
		if not opts['embed_images']:
			command_line_options += '-u '
		if not opts['whole_filename_is_link']:
			command_line_options += '-t '

		output.write('\n\nCommand-line options: [size=3][b]{}[/b][/size]\n\n'.format(command_line_options))

	# if we choose to output the data as a table, we need to set up the table header before the data first row
	if opts['output_as_table'] and opts['output_table_titles']:
		output.write('[table=100%][tr][td={1}][bg={2}][align=center][font={4}][size=5][color={3}]'
					'[b]{0}[/b][/color][/size][/font][/align][/bg][/td][/tr][/table]'
					.format(opts['tFileDetails'], opts['cTHBD'], opts['cTHBG'], opts['cTHF'], opts['fTH']))
	if opts['output_as_table']:
		output.write('[size=0][align=center][table=100%,{bgc}]\n[tr][th][align=left]Filename + IMG[/align][/th]'
					'[th]Size[/th][th]Length[/th][th]Codec[/th][th]Resolution[/th][th]Audio[/th]{alt}[/tr]\n'
					.format(alt="[th]Alt.[/th]" if has_alts else '', bgc=opts['cTBBG']))

	# everything seems okay, now we can finally output something usefulz
	tags = []
	items_parsed = 0
	imagesets = []

	# iterate over each item, and do some magic
	for item in items:

		# if the item is a string, it represents the parsing dir of the following clips/image-sets, i.e. a separator
		if isinstance(item, str):
			output.write(format_row_separator(item, has_alts))
			continue

		# get thumbnail data from image-list and alternative/backup image-list
		img_match = img_match_alt = None

		for idata in (img_data, img_data_alt):
			if idata:
				if 'imagebam' in idata['host']:
					file_slug = get_screenshot_hash(item.filename, item.filepath, 'md5', 6)
				else:
					file_slug = slugify(item.filename, idata['host'])

				match = match_slug(idata['img_list'], file_slug, idata['file'])  # list, can be multiple!

				# not ideal, but we can't use enumerate() on None object-types
				if img_match:
					img_match_alt = match
				else:
					img_match = match

		# try to generate performer tags for presentation, see  generate_tags()
		tags = generate_tags(tags, item.filename)

		# split off all image-sets, since they will be processed later
		if isinstance(item, ImageSet):
			imagesets.append({'item': item, 'img_match': img_match, 'img_match_alt': img_match_alt})
			continue

		# generate and output the item's content row
		output.write(format_row_output(item, img_match, img_match_alt, has_alts))

		# don't count separators towards the final output
		if not isinstance(item, str):
			items_parsed += 1

	# if we choose to output the data as a table, we need to set up the table footer after the last data row
	if opts['output_as_table']:
		output.write('[/table][/align][/size]')

	output.write('[size=0][align=right]File information for {} items generated by MediaInfo. {}[/align][/size]'
				.format(items_parsed, credits_bbcode))

	# process the image-sets we split-off earlier, and create a separate table/list for them at the bottom
	if imagesets:
		if opts['output_as_table'] and opts['output_table_titles']:
			output.write('\n[table=100%][tr][td={1}][bg={2}][align=center][font={4}][size=5][color={3}]'
						'[b]{0}[/b][/color][/size][/font][/align][/bg][/td][/tr][/table]'
						.format(opts['tImageSets'], opts['cTHBD'], opts['cTHBG'], opts['cTHF'], opts['fTH']))
		if opts['output_as_table']:
			output.write('[size=0][align=center][table=100%,{bgc}]\n[tr][th][align=left]Filename + IMG[/align][/th]'
						'[th]Images[/th][th]Resolution[/th][th]Size[/th][th]Unpacked[/th]{alt}[/tr]\n'
						.format(alt="[th]Alt.[/th]" if has_alts else '', bgc=opts['cTBBG']))

		imagesets_parsed = 0
		for imgset in imagesets:
			# TODO include separators for image-sets as well
			output.write(format_row_output(imgset['item'], imgset['img_match'], imgset['img_match_alt'], has_alts))
			imagesets_parsed += 1

		if opts['output_as_table']:
			output.write('[/table][/align][/size]')

		output.write('[size=0][align=right]File information for {} archives generated. {}[/align][/size]'
					.format(imagesets_parsed, credits_bbcode))

	# append the generated performer tags (if successful) to the output
	if tags:
		output.write('\n\nPERFORMER TAGS:  ' + ' '.join(tags) + '\n\n')
		print('PERFORMER TAGS:  ' + ' '.join(tags))

	# finished succesfully
	output.close()
	print('Output written to: {}'.format(file_output))

	# convert the final output to HTML code for quicker testing
	if (opts['output_html'] and not opts['all_layouts']) or (opts['output_html'] and opts['all_layouts'] and layouts_last):
		format_html_output(file_output, file_output_html)


def format_row_output(item, img_match, img_match_alt, has_alts=False):
	"""
	Generate the row output based on the input item (a Clip or an ImageSet). Here we mainly do all operations that are
	common to both 'table' and 'list' outputs, before calling the functions dealing with their differences.
	"""
	if img_match and len(img_match) == 1:
		# format the image link (and thumbnail) into correct BBCode for display
		img_match = img_match[0]
		if opts['embed_images']:
			if img_match['bburl']:
				img_code = '[url={1}][img]{0}[/img][/url]'.format(img_match['bbimg'], img_match['bburl'])
			elif opts['output_bbcode_thumb']:
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

	if opts['output_as_table']:
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
		if opts['embed_images'] and opts['whole_filename_is_link']:
			bbsafe_filename = item.filename.replace('[', '{').replace(']', '}')
			col1 = '[spoiler={0}]{1}{2}[/spoiler]'.format(bbsafe_filename, img_code, img_msg_alt)
		# inline spoiler BBCode pushes trailing text to the bottom, so if we embed images, they have to be at the end
		elif opts['embed_images']:
			col1 = '{0}     [spoiler=IMG]{1}{2}[/spoiler]'.format(item.filename, img_code, img_msg_alt)
		elif opts['whole_filename_is_link']:
			col1 = '[b][url={1}]{0}[/url][/b]'.format(item.filename, img_code)
		else:
			col1 = '[b][b][url={1}]IMG[/url][/b]  {0}[/b]'.format(item.filename, img_code)
	elif opts['suppress_img_warnings']:
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
	This is messier to look at, but more flexible with images (and BBCode support)
	"""
	filename = item.filename

	if img_code:
		if opts['embed_images']:
			img_code = ' [spoiler=:]{0}{1}[/spoiler]'.format(img_code, img_msg_alt)
		elif opts['whole_filename_is_link']:
			filename = '[url={1}]{0}[/url]'.format(filename, img_code)
			if img_code_alt:
				filename += '  ([url={}]alt.[/url])'.format(img_code_alt)
			img_code = ''
		else:
			if img_code_alt:
				filename = '[b][url={1}]IMG[/url][/b] | [url={2}]aIMG[/url]  {0}' \
					.format(filename, img_code, img_code_alt)
			else:
				filename = '[b][url={1}]IMG[/url][/b]  {0}'.format(filename, img_code)
			img_code = ''
	elif opts['suppress_img_warnings']:
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


def format_row_separator(dir_name, has_alts):
	"""
	Formats a separator row with the current parsing directory. For prettier organizing of rows.
	"""
	if opts['output_as_table']:
		# most BBCode engines don't support col-span  # TODO nb support is common?
		return '[tr={2}][td=nb][align=left][size=3][color={3}][b]{0}[/b][/color][/size][/align][/td]' \
			'{1}{1}{1}{1}{1}{alt}[/tr]\n' \
			.format(dir_name, '[td=nb][/td]', opts['cTSEPBG'], opts['cTSEPF'], alt="[td=nb][/td]" if has_alts else '')
	else:
		# just a boring row with the directory name
		return '[size=2]- [b][i]{}[/i][/b][/size]\n'.format(dir_name)


def format_html_output(file_output, file_output_html):
	"""
	Converts the BBCode output directly to HTML. This can be useful for rapid testing purposes.
	requires bbcode module ( http://bbcode.readthedocs.io/ )
	"""
	try:
		import bbcode
	except ImportError:
		print('ERROR: Couldn\'t import bbcode module! No HTML output will be generated.')
		return

	try:
		bbcinput = open(file_output, encoding='utf-8')
	except (IOError, OSError):
		print('ERROR: Couldn\'t reopen file for conversion to HTML: {}'.format(file_output))
		return

	try:
		html_file = open(file_output_html, 'w+', encoding='utf-8')
	except (IOError, OSError):
		print('ERROR: Couldn\'t create HTML output file: {}  (invalid directory?)'.format(file_output_html))
		return

	content = bbcinput.read()
	content = content.replace('\'', '±')  # temporary replacement, parser doesn't like '

	# only simple width and background-color options supported for now
	def render_table(tag_name, value, options, parent, context):
		width = background = border = ''

		if 'table' in options:
			args = options['table'].split(',')
			for opt in args:
				if '#' in opt:
					background = 'background: {};'.format(opt)
				elif '%' in opt or 'px' in opt:
					width = 'width: {};'.format(opt)
				elif 'nball' in opt:
					border = ' class="noborder"'

		return '<table style="{}{}"{}>{}</table>'.format(width, background, border, value)

	# only simple background-color options supported for now
	def render_tr(tag_name, value, options, parent, context):
		background = ''

		if 'tr' in options:
			args = options['tr'].split(',')
			for opt in args:
				if '#' in opt:
					background = 'background: {};'.format(opt)

		return '<tr style="{}">{}</tr>'.format(background, value)

	# only simple background-color options supported for now
	def render_td(tag_name, value, options, parent, context):
		background = border = ''

		if 'td' in options:
			args = options['td'].split(',')
			for opt in args:
				if '#' in opt:
					background = 'background: {};'.format(opt)
				if 'nb' in opt:
					border = 'border: none;'.format(opt)

		return '<td style="{}{}">{}</td>'.format(background, border, value)

	def render_align(tag_name, value, options, parent, context):
		align = ''

		if 'align' in options:
			align = 'text-align: {};'.format(options['align'])

		return '<div style="{}">{}</div>'.format(align, value)

	# only simple hex supported for now
	def render_bg(tag_name, value, options, parent, context):
		color = ''

		if 'bg' in options:
			color = 'background: {};'.format(options['bg'])

		return '<div style="{}">{}</div>'.format(color, value)

	# ranges from 0.75em (0) up to 3.25em (10)
	def render_size(tag_name, value, options, parent, context):
		if 'size' in options:
			size = (int(options['size']) - 1) * 0.25 + 1
		else:
			size = '1'
		return '<span style="font-size: {}em;">{}</span>'.format(size, value)

	def render_font(tag_name, value, options, parent, context):
		if 'font' in options:
			font_value = options['font']
		else:
			font_value = 'inherit'
		return '<span style="font-family: {};">{}</span>'.format(font_value, value)

	# hide/show is handled with CSS
	def render_spoiler(tag_name, value, options, parent, context):
		if 'spoiler' in options:
			link = options['spoiler']
		else:
			link = 'HTML parsing error?'
		return '<strong>{}</strong>: <a href="javascript:void(0);" class="sp">Show</a>' \
			'<blockquote class="bq">{}</blockquote>'.format(link, value)

	parser = bbcode.Parser(newline='<br />\n')
	parser.add_simple_formatter('th', '<th>%(value)s</th>')
	parser.add_simple_formatter('img', '<img src="%(value)s">', replace_links=False)
	parser.add_simple_formatter('thumb', '<img class="thumb" src="%(value)s">', replace_links=False)
	parser.add_formatter('table', render_table, transform_newlines=False)
	parser.add_formatter('tr', render_tr)
	parser.add_formatter('td', render_td)
	parser.add_formatter('align', render_align)
	parser.add_formatter('bg', render_bg)
	parser.add_formatter('size', render_size)
	parser.add_formatter('font', render_font)
	parser.add_formatter('spoiler', render_spoiler)

	html_content = parser.format(content).replace('±', '\'')
	html_css = \
		'body {font: normal 10pt "Lucida Grande", Helvetica, Arial, sans-serif; max-width: 1200px; margin: 0 auto;}\n' \
		'table {border-collapse: collapse;}\n' \
		'table, td {border: 1px solid #aaa;}\n' \
		'table.noborder, table.noborder td {border: none}\n' \
		'th, td {padding: 3px 5px;}\n' \
		'.bq {display: none;}\n' \
		'.thumb {max-width: 400px;}\n' \
		'a.sp:focus ~ .bq, .bq:focus {display: block;}\n'
	html_file.write('<!DOCTYPE html>\n<html>\n<head>\n<meta charset="UTF-8">\n<title>Test</title>\n'
					'<style type="text/css">\n{1}\n</style>\n</head>\n<body>\n{0}\n</body>\n</html>\n'
					.format(html_content, html_css))
	print('HTML output written to: {}'.format(file_output_html))

	bbcinput.close()
	html_file.close()

	webbrowser.open(file_output_html, new=2)


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
			return None
		else:
			error = ('WARNING: No corresponding image-list found! Looked for: {}'.format(file_img_list))
			print(error)
			return error

	img_items = file.read().split()

	if not img_items:
		error = ('WARNING: Image-list file ({}) seems to be empty!'.format(file_img_list))
		print(error)
		return error

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
		error = 'WARNING: Unsupported image-host used in {}!\n' \
				'Only use imagebam.com, pixhost.org, postimg.org, imagetwist.com, imagevenue.com, imgchili.net, ' \
				'pixxxels.org, jerking.empornium.ph or fapping.empornium.sx'\
				.format(file_img_list)
		print(error)
		if debug_imghost_slugs:
			img_host = 'unknown image-host'
		else:
			return error

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
		error = ('WARNING: No valid image data in image-list! Check the contents of: {}'.format(file_img_list))
		print(error)
		return error
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
	relpath = os.path.relpath(filepath, opts['media_dir'])
	if relpath is not '.':
		for ss_subdir in common_ss_subdirs:
			# for when screenshots are located at the top level dir, but have the same dir structure as the clips
			search_dirs.append(os.path.join(opts['media_dir'], ss_subdir, relpath))

	for ss_subdir in common_ss_subdirs:
		# commonly named sub-dirs of the top level media_dir (when recursive clip searching is used)
		search_dirs.append(os.path.join(opts['media_dir'], ss_subdir))

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
			return None
		if 'md5' in algorithm:
			print('calculating MD5 hash for: {}'.format(ss_found))
			return md5(img).hexdigest()[:strlen]
		else:
			return None
	else:
		print('WARNING: Couldn\'t find screenshot file for: {}'.format(filename))
		return None


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
	elif debug_imghost_slugs:
		# best guess for an unsupported host
		slug = re.sub('[^\w\s.-]', '', slug_unicode).strip()
		slug = re.sub('[\s]+', '_', slug)
	else:
		return False

	return slug


def match_slug(img_list, file_slug, file_img_list):
	"""
	Lookup the online url(s) for the corresponding slug in the local image list (see get_img_list()).
	Returns (all) matches, including false-positives unfortunately.
	"""
	# file slugs can be None when get_screenshot_hash() isn't successful
	if not file_slug:
		return False

	matches = []
	for img in img_list:
		try:
			match_pos = img['slug'].index(file_slug)
			img['match_pos'] = match_pos
			matches.append(img)
		except ValueError:
			continue

	if len(matches) > 1:
		print('WARNING: Multiple corresponding image-urls found for "{0}" in: {1}'.format(file_slug, file_img_list))
		return matches
	elif matches:
		return matches
	else:
		print('WARNING: No corresponding image-url found for "{0}" in: {1}'.format(file_slug, file_img_list))
		return False


def debug_imghost_matching(ifile='./testing/input.txt', hdir='./testing/image-hosts/', mdir='./testing/upload/'):
	"""
	Debug method for easier testing of image-host output. Compares a predefined list of file-names to the output of
	various image-hosts and provides digestible information on how the slugs are formed.
	"""
	ifile = os.path.normpath(ifile)
	hdir = os.path.normpath(hdir)
	mdir = os.path.normpath(mdir)

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
		test_names = open(ifile)
	except (IOError, OSError):
		print('{1}ERROR: No input file found for testing! Looked for:{2} {0}'.format(ifile, c['FAIL'], c['ENDC']))
		return

	test_names = test_names.read().splitlines()
	if not test_names:
		print('{1}ERROR: No file-names found for testing in:{2} {0}'.format(ifile, c['FAIL'], c['ENDC']))
		return

	# try each image-host output file
	for hfile in os.listdir(hdir):
		if hfile.endswith('.txt') or hfile.endswith('.TXT'):
			print('\n{1}TEST HOST{2}  : {0}'.format(hfile, c['HEAD'], c['ENDC']))

			img_data = get_img_list(os.path.join(hdir, hfile))
			if not img_data or isinstance(img_data, str):
				continue

			# for each file-name specified in the test file, we will check the host's output to find a match
			index = 0
			for name in test_names:
				print('{1}file-name{2}  : {0}'.format(name, c['ULIN'], c['ENDC']))

				# get the file-name slug
				if 'imagebam' in img_data['host']:
					file_slug = get_screenshot_hash(name, mdir, 'md5', 6)
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
				matches = match_slug(img_list, file_slug, hfile)

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


def generate_tags(tags, filename):
	"""
	Generates tags for all performers present in the file-names as a whole (YMMV).
	This is handy for music videos, which often have credited performers in the file-name rather than the meta-data.
	All tags will be common format. So "Michael Jackson ft. Bruno Mars - Song" outputs "michael.jackson bruno.mars"
	Note that this will NOT capture "avicii" in something like: Performer - Song (Avicii Remix)
	"""
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

	return tags


def generate_all_layouts(items, source):
	"""
	Hijacks the output function and runs it multiple times with differing settings to generate all possible layouts.
	"""
	global opts, layouts_busy, layouts_last
	original_opts = opts
	layouts_busy = True
	layouts_last = False

	opts['output_as_table'] = True
	opts['embed_images'] = True
	opts['whole_filename_is_link'] = True
	format_final_output(items, source)

	opts['output_as_table'] = True
	opts['embed_images'] = False
	opts['whole_filename_is_link'] = True
	format_final_output(items, source)

	opts['output_as_table'] = True
	opts['embed_images'] = True
	opts['whole_filename_is_link'] = False
	format_final_output(items, source)

	opts['output_as_table'] = True
	opts['embed_images'] = False
	opts['whole_filename_is_link'] = False
	format_final_output(items, source)

	opts['output_as_table'] = False
	opts['embed_images'] = False
	opts['whole_filename_is_link'] = True
	format_final_output(items, source)

	opts['output_as_table'] = False
	opts['embed_images'] = True
	opts['whole_filename_is_link'] = False
	format_final_output(items, source)

	layouts_last = True

	opts['output_as_table'] = False
	opts['embed_images'] = False
	opts['whole_filename_is_link'] = False
	format_final_output(items, source)

	layouts_busy = False
	opts = original_opts


def save_config_file(file):
	print('Saving config to: {}'.format(file))

	# use the structure of 'config', but use the values of 'opts'
	simplified_config = deepcopy(config)

	try:
		for key, group in simplified_config.items():
			for opt in group:
				simplified_config[key][opt] = opts[opt]

	except (KeyError, IndexError) as error:
		print('ERROR: mismatch for option: {}'.format(error))
		return

	try:
		with open(file, 'w', encoding='utf-8') as stream:
			stream.write('# Config file for MediaToBBCode.py\n')
			yaml.dump(simplified_config, stream, default_flow_style=False)

	except (IOError, OSError):
		print('ERROR: Couldn\'t save config file: {}'.format(file))


def load_config_file(file):
	global opts
	print('Loading config from: {}'.format(file))

	try:
		with open(os.path.normpath(os.path.expanduser(file))) as stream:
			try:
				config_file = yaml.safe_load(stream)
				if not config_file:
					print('ERROR: empty or corrupt config file!')
					return

				try:
					for key, group in config.items():
						for opt in group:
							opts[opt] = config_file[key][opt]

				except (KeyError, IndexError) as error:
					print('ERROR: missing option: {}'.format(error))
					return

			except yaml.YAMLError as error:
				print(error)
				return

	except (IOError, OSError):
		print('ERROR: Couldn\'t open config file: {}'.format(file))
		return

	print('Loaded config from: {}'.format(file))
	return True


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


# noinspection PyArgumentList,PyUnresolvedReferences,PyCallByClass,PyTypeChecker
class QtGUI(QMainWindow):
	def __init__(self):
		super().__init__()

		self.widgets = {}  # dictionary of some mutable widgets, for easier manipulation
		self.parse_thread = None  # defined here just to appease PEP

		central_widget = QWidget(self)
		central_layout = QGridLayout(central_widget)

		# INPUT OPTIONS
		frame_iops = QGroupBox('Input options', central_widget)
		layout_iops = QGridLayout(frame_iops)

		label_mdir = QLabel(config['iopts']['media_dir'][1], frame_iops)
		label_mdir.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
		layout_iops.addWidget(label_mdir, 0, 0)

		label_odir = QLabel(config['iopts']['output_dir'][1], frame_iops)
		label_odir.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
		layout_iops.addWidget(label_odir, 1, 0)

		self.widgets['media_dir'] = QLineEdit(frame_iops)
		self.widgets['media_dir'].editingFinished.connect(self.update_gui_mopts)
		layout_iops.addWidget(self.widgets['media_dir'], 0, 1)

		self.widgets['output_dir'] = QLineEdit(frame_iops)
		self.widgets['output_dir'].editingFinished.connect(self.update_gui_mopts)
		layout_iops.addWidget(self.widgets['output_dir'], 1, 1)

		button_mdir = QPushButton('Browse', frame_iops)
		button_mdir.clicked.connect(lambda event: self.select_dir('media_dir'))
		layout_iops.addWidget(button_mdir, 0, 2)

		button_odir = QPushButton('Browse', frame_iops)
		button_odir.clicked.connect(lambda event: self.select_dir('output_dir'))
		layout_iops.addWidget(button_odir, 1, 2)

		self.widgets['recursive'] = QCheckBox(config['iopts']['recursive'][1], frame_iops)
		self.widgets['recursive'].stateChanged.connect(self.update_gui_oopts)
		self.widgets['recursive'].stateChanged.connect(self.update_gui_mopts)
		layout_iops.addWidget(self.widgets['recursive'], 0, 3)

		self.widgets['parse_zip'] = QCheckBox(config['iopts']['parse_zip'][1], frame_iops)
		self.widgets['parse_zip'].stateChanged.connect(self.update_gui_oopts)
		layout_iops.addWidget(self.widgets['parse_zip'], 1, 3)

		central_layout.addWidget(frame_iops, 0, 0)

		# TABS
		tabs = QTabWidget(central_widget)

		# OUTPUT OPTIONS
		tab_oopts = QWidget(tabs)
		layout_oopts = QGridLayout(tab_oopts)

		row = 0
		for oopt, values in config['oopts'].items():
			self.widgets[oopt] = QCheckBox(values[1], tab_oopts)
			self.widgets[oopt].stateChanged.connect(self.update_gui_oopts)
			layout_oopts.addWidget(self.widgets[oopt], row, 0)

			# separators
			if 'output_table_titles' in oopt or 'output_separators' in oopt or 'suppress_img_warnings' in oopt:
				row += 1
				line = QFrame(tab_oopts)
				line.setFrameShape(QFrame.HLine)
				line.setFrameShadow(QFrame.Sunken)
				layout_oopts.addWidget(line, row, 0)

			# disable/enable the image-list options based on this (and 'recursive')
			if 'output_individual' in oopt:
				self.widgets[oopt].stateChanged.connect(self.update_gui_mopts)

			row += 1

		tabs.addTab(tab_oopts, 'Output options')

		# IMAGE-LIST OPTIONS
		tab_mopts = QWidget(tabs)
		layout_mopts = QGridLayout(tab_mopts)

		note_mopts = QGroupBox('Note', tab_mopts)
		layout_note_mopts = QGridLayout(note_mopts)

		label_mopts = 'You do not need to use these options if your image-list files are set correctly (see ' \
			'documentation), because the script will automatically look for the appropriate .txt files. ' \
			'But you can manually specify them here if the automatic feature doesn\'t work for you.'
		self.label_mopts = QLabel(label_mopts, note_mopts)
		self.label_mopts.setWordWrap(True)
		layout_note_mopts.addWidget(self.label_mopts)

		label_mopts_disabled = 'You are using the option to output each directory as an individual file. ' \
			'This means you will have to rely on the automated script. It will try to find the correct image-list ' \
			'files for each directory. Carefully check the output log for potential problems.'
		self.label_mopts_disabled = QLabel(label_mopts_disabled, note_mopts)
		self.label_mopts_disabled.setWordWrap(True)
		self.label_mopts_disabled.setVisible(True)
		layout_note_mopts.addWidget(self.label_mopts_disabled)

		layout_mopts.addWidget(note_mopts, 0, 0, 1, 2)

		self.imagelist_buttons = {}
		row = 1
		for mopt, values in config['mopts'].items():
			if 'string' in values[1]:
				label = QLabel(values[2] + ':', tab_mopts)
				layout_mopts.addWidget(label, row, 0)
				row += 1

				self.widgets[mopt] = QLineEdit(tab_mopts)
				layout_mopts.addWidget(self.widgets[mopt], row, 0)

				self.imagelist_buttons[mopt] = QPushButton('Browse', tab_mopts)
				self.imagelist_buttons[mopt].clicked.connect(lambda event, opt=mopt: self.select_file(opt))
				layout_mopts.addWidget(self.imagelist_buttons[mopt], row, 1)

			elif 'bool' in values[1]:
				self.widgets[mopt] = QCheckBox(values[2], tab_mopts)
				self.widgets[mopt].stateChanged.connect(self.update_gui_mopts)
				layout_mopts.addWidget(self.widgets[mopt], row, 0)

			# separators
			if 'imagelist_alt' in mopt:
				row += 1
				line = QFrame(tab_oopts)
				line.setFrameShape(QFrame.HLine)
				line.setFrameShadow(QFrame.Sunken)
				layout_mopts.addWidget(line, row, 0, 1, 2)

			row += 1

		self.tab_mopts = tab_mopts  # so we can disable the entire tab easily
		tabs.addTab(tab_mopts, 'Image lists')

		# DISPLAY OPTIONS
		tab_dopts = QWidget(tabs)
		layout_dopts = QGridLayout(tab_dopts)

		self.color_buttons = {}
		row = 0
		for dopt, values in config['dopts'].items():
			self.widgets[dopt] = QLineEdit(tab_dopts)
			layout_dopts.addWidget(self.widgets[dopt], row, 1)

			label = QLabel(values[2], tab_dopts)
			layout_dopts.addWidget(label, row, 2)

			if values[1] == 'color':
				self.color_buttons[dopt] = QPushButton(tab_dopts)
				self.color_buttons[dopt].clicked.connect(lambda event, opt=dopt: self.pick_color(opt))
				self.widgets[dopt].editingFinished.connect(lambda opt=dopt: self.update_gui_dopts(opt))
				layout_dopts.addWidget(self.color_buttons[dopt], row, 0)

			row += 1

		tabs.addTab(tab_dopts, 'Display options')

		# SAVE/LOAD CONFIG
		tab_config = QWidget(tabs)
		layout_config = QHBoxLayout(tab_config)

		button_save = QPushButton('Save Config', tab_config)
		button_save.clicked.connect(self.save_config)
		button_load = QPushButton('Load Config', tab_config)
		button_load.clicked.connect(self.load_config)
		button_reset = QPushButton('Reset Config', tab_config)
		button_reset.clicked.connect(self.reset_config)

		layout_config.addStretch()
		layout_config.addWidget(button_save)
		layout_config.addWidget(button_load)
		layout_config.addWidget(button_reset)
		layout_config.addStretch()

		tabs.addTab(tab_config, 'Save/Load config')

		# ABOUT
		tab_about = QWidget(tabs)
		layout_about = QGridLayout(tab_about)

		script_display = QLabel(script, tab_about)
		script_font = QFont()
		script_font.setPointSize(20)
		script_display.setFont(script_font)
		script_display.setAlignment(Qt.AlignCenter | Qt.AlignVCenter)
		script_display.mousePressEvent = lambda event: self.visit_website(script_url)
		layout_about.addWidget(script_display, 1, 1, 1, 2)

		author_label = QLabel('author:', tab_about)
		author_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
		layout_about.addWidget(author_label, 2, 1)

		author_content = QLabel(author, tab_about)
		author_content.mousePressEvent = lambda event: self.visit_website(author_url)
		layout_about.addWidget(author_content, 2, 2)

		version_label = QLabel('version:', tab_about)
		version_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
		layout_about.addWidget(version_label, 3, 1)

		version_content = QLabel(version, tab_about)
		layout_about.addWidget(version_content, 3, 2)

		compile_label = QLabel('compile date:', tab_about)
		compile_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
		layout_about.addWidget(compile_label, 4, 1)

		compile_content = QLabel(compile_date, tab_about)
		layout_about.addWidget(compile_content, 4, 2)

		layout_about.setColumnStretch(0, 10)
		layout_about.setColumnStretch(3, 10)
		layout_about.setRowStretch(0, 5)
		layout_about.setRowStretch(5, 10)
		tabs.addTab(tab_about, 'About')

		# FINISH TABS
		tabs.setCurrentIndex(0)
		tabs.setTabShape(QTabWidget.Rounded)
		central_layout.addWidget(tabs, 1, 0)

		# MASTER BUTTON(S)
		frame_run = QWidget(central_widget)
		layout_run = QHBoxLayout(frame_run)

		self.button_run = QPushButton('Run', frame_run)
		self.button_run.clicked.connect(self.run_start)

		layout_run.addStretch()
		layout_run.addWidget(self.button_run)
		layout_run.addStretch()
		central_layout.addWidget(frame_run, 2, 0)

		# LOG WINDOW
		self.log_text = QPlainTextEdit()
		log_font = QFont('Monospace', 8)
		log_font.setStyleHint(QFont.TypeWriter)
		self.log_text.setFont(log_font)
		self.log_text.setPlaceholderText('Started GUI.')
		self.log_text.setReadOnly(True)
		# self.log_text.setLineWrapMode(QPlainTextEdit.NoWrap)
		self.log_text.ensureCursorVisible()
		central_layout.addWidget(self.log_text, 3, 0)

		# MAIN GUI OPTIONS
		self.setWindowTitle(script)
		self.setWindowIcon(QIcon(resource_path('icon.ico')))
		self.resize(600, 660)
		self.setMinimumSize(500, 600)
		self.setAnimated(False)

		central_layout.setRowStretch(0, 0)
		central_layout.setRowStretch(1, 0)
		central_layout.setRowStretch(2, 0)
		central_layout.setRowStretch(3, 10)
		self.setCentralWidget(central_widget)

		# SET INITIAL STATE
		self.initializing = True  # prevent event emitters from going crazy during GUI initialization
		self.set_gui_values()
		self.initializing = False
		self.update_gui_oopts()
		self.update_gui_mopts()
		self.update_gui_dopts()

		# REDIRECT STDOUT
		sys.stdout = QtGUI.StdoutRedirector(writeSignal=self.log_append)
		sys.stderr = QtGUI.StdoutRedirector(writeSignal=self.log_append)

	def set_gui_values(self):
		for opt, widget in self.widgets.items():
			if isinstance(widget, QLineEdit):
				self.widgets[opt].setText(opts[opt])
			elif isinstance(widget, QCheckBox):
				self.widgets[opt].setChecked(opts[opt])

	def get_gui_values(self):
		global opts

		for opt, widget in self.widgets.items():
			if isinstance(widget, QLineEdit):
				if widget.isEnabled():
					opts[opt] = widget.text()
				else:
					opts[opt] = ''
			elif isinstance(widget, QCheckBox):
				if widget.isEnabled():
					opts[opt] = widget.isChecked()
				else:
					opts[opt] = False

	@pyqtSlot()
	def update_gui_oopts(self):
		if self.initializing:
			return

		if self.widgets['recursive'].isChecked():
			self.widgets['output_individual'].setDisabled(False)
			self.widgets['output_separators'].setDisabled(False)
		else:
			self.widgets['output_individual'].setDisabled(True)
			self.widgets['output_separators'].setDisabled(True)

		if self.widgets['output_individual'].isChecked() or not self.widgets['recursive'].isChecked():
			self.widgets['output_separators'].setDisabled(True)
		else:
			self.widgets['output_separators'].setDisabled(False)

		if self.widgets['output_as_table'].isChecked():
			self.widgets['output_table_titles'].setDisabled(False)
		else:
			self.widgets['output_table_titles'].setDisabled(True)

		if self.widgets['embed_images'].isChecked():
			self.widgets['output_bbcode_thumb'].setDisabled(False)
		else:
			self.widgets['output_bbcode_thumb'].setDisabled(True)

	@pyqtSlot()
	def update_gui_mopts(self):
		if self.initializing:
			return

		media_dir = self.widgets['media_dir'].text()
		output_dir = self.widgets['output_dir'].text()

		if self.widgets['recursive'].isChecked() \
			and self.widgets['recursive'].isEnabled() \
			and self.widgets['output_individual'].isChecked():
			self.tab_mopts.setDisabled(True)
			self.label_mopts.setVisible(False)
			self.label_mopts_disabled.setVisible(True)
		else:
			self.tab_mopts.setDisabled(False)
			self.label_mopts.setVisible(True)
			self.label_mopts_disabled.setVisible(False)

		if self.widgets['use_imagelist_fsz'].isChecked():
			self.widgets['use_primary_as_fsz'].setDisabled(False)
		else:
			self.widgets['use_primary_as_fsz'].setDisabled(True)

		if self.widgets['use_imagelist_fsz'].isChecked() and not self.widgets['use_primary_as_fsz'].isChecked():
			self.widgets['imagelist_fsz'].setDisabled(False)
			self.imagelist_buttons['imagelist_fsz'].setDisabled(False)
		else:
			self.widgets['imagelist_fsz'].setDisabled(True)
			self.imagelist_buttons['imagelist_fsz'].setDisabled(True)

		if not output_dir and not media_dir:
			base = ''
		elif not output_dir:
			base = os.path.normpath(os.path.join(media_dir, os.path.basename(media_dir)))
		else:
			base = os.path.normpath(os.path.join(output_dir, os.path.basename(media_dir)))

		self.widgets['imagelist_pri'].setPlaceholderText(base + '.txt')
		self.widgets['imagelist_alt'].setPlaceholderText(base + '_alt.txt')
		self.widgets['imagelist_fsz'].setPlaceholderText(base + '_fullsize.txt')

	@pyqtSlot()
	@pyqtSlot(str)
	def update_gui_dopts(self, dopt=None):
		if self.initializing:
			return

		if dopt:
			buttons = {dopt: self.color_buttons[dopt]}
		else:
			buttons = self.color_buttons

		for opt, button in buttons.items():
			value = self.get_color(self.widgets[opt].text())
			if value:
				self.color_buttons[opt].setStyleSheet('background-color: {}'.format(value['color']))
			else:
				self.color_buttons[opt].setStyleSheet('')

	@pyqtSlot(str)
	def pick_color(self, dopt):
		old_value = self.widgets[dopt].text()
		old_color = QColor()
		the_rest = ''

		if old_value:
			old_value = self.get_color(old_value)
			if old_value:
				old_color.setNamedColor(old_value['color'])
				the_rest = old_value['the_rest'].strip()

		new_color = QColorDialog.getColor(old_color)

		if new_color.isValid():
			self.widgets[dopt].setText((new_color.name().upper() + ' ' + the_rest).strip())
			self.update_gui_dopts(dopt)

	@staticmethod
	def get_color(string):
		match = re.search(r'#(?:[0-9a-fA-F]{1,2}){3}', string)
		if match:
			the_rest = string.replace(match.group(0), '')
			return {'color': match.group(0), 'the_rest': the_rest}
		else:
			return False

	@pyqtSlot(str)
	def visit_website(self, url):
		webbrowser.open(url, new=2)

	@pyqtSlot(str)
	def select_dir(self, opt):
		directory = QFileDialog.getExistingDirectory()

		if directory:
			self.widgets[opt].setText(directory)
			if 'media_dir' in opt or 'output_dir' in opt:
				self.update_gui_mopts()

	@pyqtSlot(str)
	def select_file(self, opt):
		file = QFileDialog.getOpenFileName()[0]

		if file:
			self.widgets[opt].setText(file)

	@pyqtSlot()
	def save_config(self):
		caption = 'Save config file'
		initial_dir = os.path.join(self.widgets['output_dir'].text(), 'mediatobbcode-config.yml')
		filters = 'YAML Files (*.yml *.yaml);;All Files (*.*)'
		selected_filter = 'YAML Files (*.yml *.yaml)'
		file = QFileDialog.getSaveFileName(self, caption, initial_dir, filters, selected_filter)[0]

		if file:
			self.get_gui_values()
			save_config_file(file)

	@pyqtSlot()
	def load_config(self):
		caption = 'Load config file'
		initial_dir = os.path.join(self.widgets['output_dir'].text(), 'mediatobbcode-config.yml')
		filters = 'YAML Files (*.yml *.yaml);;All Files (*.*)'
		selected_filter = 'YAML Files (*.yml *.yaml)'
		file = QFileDialog.getOpenFileName(self, caption, initial_dir, filters, selected_filter)[0]

		if file:
			success = load_config_file(file)
			if success:
				self.initializing = True
				self.set_gui_values()
				self.initializing = False
				self.update_gui_oopts()
				self.update_gui_mopts()
				self.update_gui_dopts()

	@pyqtSlot()
	def reset_config(self):
		self.initializing = True
		populate_opts()
		self.set_gui_values()
		self.initializing = False
		self.update_gui_oopts()
		self.update_gui_mopts()
		self.update_gui_dopts()

	@pyqtSlot()
	def run_start(self):
		self.get_gui_values()
		self.log_text.clear()

		self.parse_thread = QtGUI.ParseThread()
		self.parse_thread.finished.connect(self.run_finish)
		self.parse_thread.start()

		self.button_run.setText('Stop')
		self.button_run.clicked.disconnect()
		self.button_run.clicked.connect(self.run_terminate)

	@pyqtSlot()
	def run_finish(self):
		self.button_run.setText('Run')
		self.button_run.clicked.disconnect()
		self.button_run.clicked.connect(self.run_start)

	@pyqtSlot()
	def run_terminate(self):
		if self.parse_thread.isRunning():
			self.parse_thread.terminate()
			print('Thread terminated!')

	@pyqtSlot(str)
	def log_append(self, text):
		self.log_text.moveCursor(QTextCursor.End)
		self.log_text.insertPlainText(text)

	class ParseThread(QThread):
		def __init__(self):
			super().__init__()

		def run(self):
			try:
				set_paths_and_run()
			except:
				(errortype, value, traceback) = sys.exc_info()
				sys.excepthook(errortype, value, traceback)
				self.exit()

	# redirect stdout (print) to a widget
	# adapted from http://stackoverflow.com/questions/22581496/error-in-pyqt-qthread-not-printed
	class StdoutRedirector(QObject):
		writeSignal = pyqtSignal(str)

		def write(self, text):
			self.writeSignal.emit(str(text))

		def flush(self):
			pass


def resource_path(relative_path):
	"""
	Get absolute path to resources, works for dev and for PyInstaller 3.2
	"""
	try:
		# PyInstaller creates a temp folder and stores path in _MEIPASS
		base_path = sys._MEIPASS
	except AttributeError:
		base_path = os.path.abspath('.')

	return os.path.join(base_path, relative_path)


def main(argv):
	"""
	Process command-line inputs or load GUI
	"""
	global opts, debug_imghost_slugs

	# set the default opts as initial values
	populate_opts()

	h = 'mediatobbcode.py\n' \
		'- use GUI to set options\n\n' \
		'mediatobbcode.py -m <media dir>\n' \
		'- parse all media files in dir -m and output to -m\n\n' \
		'mediatobbcode.py -m <media dir> -o <output dir>\n' \
		'- parse all media files in dir -m and output to -o\n\n' \
		'mediatobbcode.py -m <media dir> -r -o <output dir>\n' \
		'- parse all media files in -m recursively and output to -o\n\n' \
		'mediatobbcode.py -c <config file>\n' \
		'- use previously saved config file to set script options\n\n' \
		'For a full list of command-line options, see the online documentation.'

	try:
		options, args = getopt.getopt(argv, 'hm:o:rzlbifuntsawzc:x',
			['help', 'mediadir=', 'outputdir=', 'recursive', 'zip', 'list', 'bare', 'individual', 'flat',
			'url', 'nothumb', 'tinylink', 'suppress', 'all', 'webhtml', 'fullsize', 'config=', 'xdebug'])
		if not options:
			# create GUI
			app = QApplication(sys.argv)
			gui = QtGUI()
			gui.show()
			sys.exit(app.exec_())
			# Create thread that will listen on the other end of the queue, and send the text to the textedit in our application

	except getopt.GetoptError:
		print(h)
		sys.exit(2)

	for opt, arg in options:
		if opt in ('-h', '--help'):
			print(h)
			sys.exit()

		elif opt in ('-m', '--mediadir'):
			opts['media_dir'] = arg
		elif opt in ('-o', '--outputdir'):
			opts['output_dir'] = arg
		elif opt in ('-r', '--recursive'):
			opts['recursive'] = True
		elif opt in ('-z', '--zip'):
			opts['parse_zip'] = True

		elif opt in ('-l', '--list'):
			opts['output_as_table'] = False
		elif opt in ('-b', '--bare'):
			opts['output_table_titles'] = False
		elif opt in ('-i', '--individual'):
			opts['output_individual'] = True
		elif opt in ('-f', '--flat'):
			opts['output_separators'] = False

		elif opt in ('-u', '--url'):
			opts['embed_images'] = False
		elif opt in ('-n', '--nothumb'):
			opts['output_bbcode_thumb'] = False
		elif opt in ('-t', '--tinylink'):
			opts['whole_filename_is_link'] = False
		elif opt in ('-s', '--suppress'):
			opts['suppress_img_warnings'] = True

		elif opt in ('-z', '--fullsize'):
			opts['use_imagelist_fsz'] = True
		elif opt in ('-a', '--all'):
			opts['all_layouts'] = True
		elif opt in ('-w', '--webhtml'):
			opts['output_html'] = True

		elif opt in ('-c', '--config'):
			success = load_config_file(arg)
			if not success:
				sys.exit()
		elif opt in ('-x', '--xdebug'):
			# if we just want to debug image-host matching for development
			debug_imghost_matching()
			sys.exit()

	# initialize the script using the command-line arguments
	set_paths_and_run()


# hi there :)
if __name__ == '__main__':
	main(sys.argv[1:])
