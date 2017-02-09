# encoding: utf-8

import csv
import getopt
import hashlib
import operator
import os
import re
import unicodedata
import sys
from urllib.parse import urlparse


##########################################################################
# DON'T TOUCH ANYTHING ABOVE THIS LINE UNLESS YOU KNOW WHAT YOU'RE DOING #
##########################################################################


# The following settings determine the input for the script, choose wisely.

# The working directory, where CSV files and image-lists should be located, and _output.txt files are written.
# All CSV files located here will be parsed, so make sure they are properly formatted by MediaInfo.
working_dir = './files'

# Switches from using CSV as input, to actually generating file information using MediaInfo as the script runs.
# Requires MediaInfo.dll (32/64bit DLL must match Python environment!)
parse_media = False

# Determines the directory to use when looking for media files to process.
# Only applies if "parse_media = True".
clips_path = './videos'

# Will enable recursive searching for files. Meaning it will include all sub-directories of "clips_path".
# Only applies if "parse_media = True".
clips_path_recursive = False


# These settings determine the output formatting. Be careful when using "embed_images" with "output_as_table".
# I strongly advise using small/medium thumbnail images if you want to embed them, or they will break the table layout.

# Generate table output. If not, a simpler (ugly) flat list will be generated.
# Requires support for [table] tags by the BBCode engine used by your website.
output_as_table = True

# Generate a separate output file for each directory successfully traversed recursively.
# Only applies if "parse_media = True" and "clips_path_recursive = True".
output_individual = False

# Generate separators (with the directory name) when switching directories in recursive mode.
# Only applies if "parse_media = True" and "clips_path_recursive = True" and "output_individual = False"
output_separators = True

# Generate a nice heading above the table/list.
# Requires support for [table] tags by the BBCode engine used by your website.
output_section_head = True

# Embed the image/thumbnails in the output. Otherwise a link to the image will be embedded.
# Requires support for [spoiler] tags by the BBCode engine used by your website.
embed_images = True

# Instead of having a small link next to the file-name, to the full-sized image, the whole title will be a link.
# When combined with "embed_images", this will make the whole file-name a spoiler tag.
whole_filename_is_link = True

# Prevents those red warning messages from appearing in the output if no suitable image/link was found.
suppress_img_warnings = False

# This will output all 7 different layout options below each other, easy for testing and picking your favorite.
# Note that this will include layouts with [table] and [spoiler] tags, so be careful if these aren't supported.
all_layouts = False

# Experimental feature that will convert the output BBCode directly to HTML. This can be used for rapid testing.
# But for final rendering it's mostly useless. Would require way too much work to add all the needed tags.
# Requires bbcode module.
output_html = False


##########################################################################
# DON'T TOUCH ANYTHING BELOW THIS LINE UNLESS YOU KNOW WHAT YOU'RE DOING #
##########################################################################


def parse_media_files():
	"""
	Uses the pymediainfo module to parse each file in a directory (recursively), and extract media information from
	each video-clip. It creates Clip objects and stores it in a clips list for later use.
	"""
	try:
		from pymediainfo import MediaInfo
	except ImportError:
		print('\nERROR: Couldn\'t import MediaInfo module from pymediainfo!\n')
		sys.exit()

	clips = []
	ran_at_all = False  # canary - general
	parsed_at_all = False  # canary - for when output_individual has cleared clips[] after sending to output

	for root, dirs, files in os.walk(clips_path):
		print('\nSWITCH dir: {}'.format(root))
		new_dir = True
		ran_at_all = True

		for file in files:
			# ignore some common file-extensions found alongside videos  # TODO unix is case-sensitive :(
			if file.endswith(('.jpg', '.JPG', '.jpeg', 'JPEG', '.png', '.PNG', '.gif', '.GIF', '.psd', '.ai',
							'.txt', '.nfo', '.NFO', '.doc', '.xml', '.csv', '.pdf', '.zip', '.gz', '.tar', '.rar',
							'.flac', '.mp3', '.acc', '.wav', '.pls', '.m3u', '.torrent')):
				print('skipped file: {}'.format(os.path.join(root, file)))
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
				print(' attempt file: {}'.format(os.path.join(root, file)))

				# create a separator with the relative directory, but only if it's the first valid file in the dir
				if new_dir and clips_path_recursive and output_separators and not output_individual:
					current_dir = os.path.relpath(root, clips_path)
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
				clip = Clip('RAW', filepath, filename, filesize, length, vcodec, vcodec_alt,
							vbitrate, vbitrate_alt, vwidth, vheight, vscantype, vframerate, vframerate_alt,
							acodec, abitrate, asample, aprofile)
				clips.append(metadata_cleanup(clip))
				print(' parsed file : {}'.format(os.path.join(root, file)))
			else:
				print('ERROR parsing: {}  -  not a video file?'.format(file))

		# break after top level if we don't want recursive parsing
		if not clips_path_recursive:
			break
		elif output_individual and clips:
			# output each dir as a separate file, so we need to reset the clips after each successfully parsed dir
			parsed_at_all = True
			format_final_output(clips, root)
			clips = []

	if not ran_at_all:
		print('ERROR: invalid directory for: {}'.format(clips_path))
	elif not clips and not parsed_at_all:
		print('ERROR: no valid media files found in: '.format(clips_path))
	elif not output_individual:
		format_final_output(clips, clips_path)


def parse_csv_files():
	"""
	Searches the working_dir for CSV files generated by MediaInfo. It extracts the valuable bits, creates a
	Clip object for each row, and puts them in a clips dictionary which is used for generating output.
	"""
	files_tried = files_parsed = 0

	for file in os.listdir('.'):  # path has already been set by os.chdir(working_dir)
		if file.endswith('.csv') or file.endswith('.CSV'):
			print('\nSWITCH CSV: {}'.format(file))
			files_tried += 1
			clips = []

			with open(file) as csvfile:
				reader = csv.DictReader(csvfile, delimiter=';')
				try:
					reader = sorted(reader, key=operator.itemgetter('General CompleteName'))

					# pray that these column names are correct for your CSV files
					for row in reader:
						# this hack makes it possible to parse Windows generated CSV files on Unix
						filename_xos = os.path.normpath(row['General CompleteName'].replace('\\', '/'))

						print(' attempt row: {}'.format(os.path.basename(filename_xos)))
						filepath = os.path.dirname(filename_xos)
						filename = os.path.basename(filename_xos)
						filesize = row['General FileSize/String']
						length = row['General Duration/String']

						vcodec = row['Video 0 CodecID']
						vcodec_alt = row['Video 0 Format']
						vbitrate = row['Video 0 BitRate/String']
						vbitrate_alt = row['General OverallBitRate/String']
						vwidth = row['Video 0 Width/String']
						vheight = row['Video 0 Height/String']
						vscantype = row['Video 0 ScanType/String']
						vframerate = row['Video 0 FrameRate/String']
						vframerate_alt = row['Video 0 FrameRate_Nominal/String']

						acodec = row['Audio 0 Format']
						abitrate = row['Audio 0 BitRate/String']
						asample = row['Audio 0 SamplingRate/String']
						aprofile = row['Audio 0 Format_Profile']

						# exclude every line that doesn't appear to be a video (only applies to CSV input)
						if not length or (not vcodec and not vcodec_alt):
							continue

						# create Clip object for easier manipulation and passing around
						clip = Clip('CSV', filepath, filename, filesize, length, vcodec, vcodec_alt,
									vbitrate, vbitrate_alt, vwidth, vheight, vscantype, vframerate, vframerate_alt,
									acodec, abitrate, asample, aprofile)
						clips.append(metadata_cleanup(clip))
						print(' parsed row : {}'.format(os.path.basename(row['General CompleteName'])))

					files_parsed += 1

				except KeyError:
					csvfile.close()
					print('ERROR parsing: {}  -  file most likely not generated using MediaInfo!'.format(file))
					continue

			format_final_output(clips, file)

			csvfile.close()

	if files_tried == 0:
		print('ERROR: No CSV files found in: {}'.format(working_dir))
	elif files_parsed == 0:
		print('ERROR: Only incompatible CSV files found in: {}'.format(working_dir))
	else:
		print('CSV files tried: {}. CSV files parsed: {}'.format(files_tried, files_parsed))


def format_final_output(clips, source):
	"""
	Takes the Clips generated from either a single CSV file, or an live dir parsing session, and write the output.
	"""
	# no clips? something is wrong
	if not clips:
		print('ERROR: No media clips found! The script shouldn\'t even have gotten this far. o_O')
		return

	# setup some file locations for input/output
	if parse_media:
		if output_individual:
			# When creating an output file for each parsed directory, we don't want to have to create directories to
			# the same depth as the source files (in order to keep the file structure). So for directories deeper than
			# clips_path + 1, we concatenate the dir-names into a long string.
			relpath = os.path.relpath(source, clips_path)

			if relpath == '.':
				working_file = os.path.join(working_dir, os.path.basename(source))
			else:
				working_file = os.path.join(working_dir, relpath.replace('\\', '__').replace('/', '__'))
		else:
			working_file = os.path.join(working_dir, os.path.basename(source))

		file_output = working_file + '_output.txt'
		file_output_html = working_file + '_output.html'
		file_img_list = working_file + '.txt'
		file_img_list_alt = working_file + '_alt.txt'
	else:
		# source is the CSV file-name
		file_output = os.path.join(source[:-4] + '_output.txt')
		file_output_html = os.path.join(source[:-4] + '_output.html')
		file_img_list = os.path.join(source[:-4] + '.txt')
		file_img_list_alt = os.path.join(source[:-4] + '_alt.txt')

	# create an output loop for generating all different layouts
	if all_layouts and not layouts_busy:
		try:
			open(file_output, 'w+').close()  # clear the current output file before starting the loop
		except (IOError, OSError):
			print('ERROR: Couldn\'t create output file: {}  (invalid directory?)'.format(file_output))
			sys.exit()
		generate_all_layouts(clips, source)
		return

	# append the output of every cycle rather than truncating the entire output file
	write_mode = 'a+' if all_layouts else 'w+'
	try:
		output = open(file_output, write_mode, encoding='utf-8')
	except (IOError, OSError):
		print('ERROR: Couldn\'t create output file: {}  (invalid directory?)'.format(file_output))
		return

	# stop if this combination is active, it will produce a mess
	if whole_filename_is_link and embed_images and not output_as_table:
		invalid_combo = 'Using the parameters "whole_filename_is_link" and "embed_images" ' \
						'and not "output_as_table" is the only invalid combination\n\n'
		output.write(invalid_combo)
		output.close()
		print(invalid_combo)
		sys.exit()  # the only situation where nothing good can come out of it

	# everything seems okay, now we can finally output something useful
	tags = []
	clips_parsed = 0

	# get the image data for later use; img_data is a string with error details if no compatible image data was found
	img_data = get_img_list(file_img_list)
	if isinstance(img_data, str):
		output.write(img_data + '\n\n')
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
	if all_layouts and layouts_busy:
		options = ''
		if not output_as_table:
			options += '-l '
		if not embed_images:
			options += '-u '
		if not whole_filename_is_link:
			options += '-t '

		output.write('\n\nCommand-line options: [size=3][b]{}[/b][/size]\n\n'.format(options))

	# if we choose to output the data as a table, we need to set up the table header before the data first row
	if output_section_head:
		output.write('[table=100][tr][td=#0054B0][bg=#003875][align=center][font=Verdana][size=5][color=#FFFFFF]'
					'[b]FILE DETAILS[/b][/color][/size][/font][/align][/bg][/td][/tr][/table]')
	if output_as_table:
		output.write('[size=0][align=center][table=100,#f4f4f4]\n[tr][th][align=left]Filename + IMG[/align][/th]'
					'[th]Size[/th][th]Length[/th][th]Codec[/th][th]Resolution[/th][th]Audio[/th]{alt}[/tr]\n'
					.format(alt="[th]Alt.[/th]" if has_alts else ''))

	# iterate over each clip, and do some magic
	for clip in clips:

		# if the clip is a string, it represents the parsing dir of the following clips, i.e. a separator
		if isinstance(clip, str):
			output.write(format_row_output(clip, None, None, has_alts, True))
			continue

		# get thumbnail data from image-list and alternative/backup image-list
		img_match = img_match_alt = None

		for idata in (img_data, img_data_alt):
			if idata:
				if 'imagebam' in idata['host']:
					file_slug = get_screenshot_hash(clip.filename, clip.filepath, 'md5', 6)
				else:
					file_slug = slugify(clip.filename, idata['host'])

				match = match_slug(idata['img_list'], file_slug, idata['file'])  # list, can be multiple!

				# not ideal, but we can't use enumerate() on None object-types
				if img_match:
					img_match_alt = match
				else:
					img_match = match

		# generate and output the row
		output.write(format_row_output(clip, img_match, img_match_alt, has_alts))

		# don't count separators towards the final output
		if not isinstance(clip, str):
			clips_parsed += 1

		# try to generate performer tags for presentation, see  generate_tags()
		tags = generate_tags(tags, clip.filename)

	# if we choose to output the data as a table, we need to set up the table footer after the last data row
	if output_as_table:
		output.write('[/table][/align][/size]')

	output.write('[size=0][align=right]File information for {} items generated by MediaInfo.'.format(clips_parsed))
	output.write(' Output script by [url=https://github.com/paybas]PayBas[/url].[/align][/size]')  # TODO

	# append the generated performer tags (if successful) to the output
	if tags:
		output.write('\n\nPERFORMER TAGS:  ' + ' '.join(tags) + '\n\n')
		print('PERFORMER TAGS:  ' + ' '.join(tags))

	# finished succesfully
	output.close()
	print('Output written to: {}'.format(file_output))

	# 99% broken
	if output_html:
		try:
			import bbcode
		except ImportError:
			print('ERROR: Couldn\'t import bbcode module! No HTML output will be generated.')
			return

		try:
			bbcinput = open(file_output)
		except (IOError, OSError):
			print('ERROR: Couldn\'t reopen file for conversion to HTML: {}'.format(file_output))
			return

		# append the output of every cycle rather than truncating the entire output file
		write_mode = 'a+' if all_layouts else 'w+'
		try:
			html_file = open(file_output_html, write_mode, encoding='utf-8')
		except (IOError, OSError):
			print('ERROR: Couldn\'t create HTML output file: {}  (invalid directory?)'.format(file_output_html))
			return

		content = bbcinput.read()
		html_content = bbcode.render_html(content)
		html_file.write(html_content)

		bbcinput.close()
		html_file.close()


def format_row_output(clip, img_match, img_match_alt, has_alts=False, separator=False):
	"""
	Generate the row output, change this to suit your needs. Just don't break anything ;)
	"""
	if img_match and len(img_match) == 1:
		# format the image link (and thumbnail) into correct BBCode for display
		img_match = img_match[0]
		if embed_images:
			if img_match['bburl']:
				img_code = '[url={1}][img]{0}[/img][/url]'.format(img_match['bbimg'], img_match['bburl'])
			else:
				img_code = '[img]{0}[/img]'.format(img_match['bbimg'])
		# since we don't want to embed the image (or thumbnail), just grab the url to the big version
		else:
			img_code = img_match['bburl'] if img_match['bburl'] else img_match['bbimg']
		img_error = None
	elif img_match:
		img_error = '[color=#FF8800]Image conflict![/color]'  # multiple matches
		img_code = False
	else:
		img_error = '[color=#FF0000]Image missing![/color]'
		img_code = False

	# get the url to the full-sized alternative/backup image
	if has_alts:
		if img_match_alt and len(img_match_alt) == 1:
			img_match_alt = img_match_alt[0]
			img_code_alt = img_match_alt['bburl'] if img_match_alt['bburl'] else img_match_alt['bbimg']
			img_alt_str = '\n[url={}][b]> Backup Image <[/b][/url]'.format(img_code_alt)
		elif img_match_alt:
			img_code_alt = False
			img_alt_str = '[color=#FF8800][b]Image conflict![/b][/color]'  # multiple matches
		else:
			img_code_alt = False
			img_alt_str = '[color=#FF0000][b]Image missing![/b][/color]'
	else:
		img_code_alt = False
		img_alt_str = ''

	# output format differs considerably when outputting as a table
	if output_as_table:
		if separator:
			# most BBCode engines don't support col-span
			output = '[tr=#AAA][td][align=left][size=2][b]{0}[/b][/size][/align][/td]{1}{1}{1}{1}{1}{alt}[/tr]\n'\
					.format(clip, '[td][/td]', alt="[td][/td]" if has_alts else '')
			return output

		if img_code:
			# make the entire file-name a spoiler link
			if embed_images and whole_filename_is_link:
				bbsafe_filename = clip.filename.replace('[', '{').replace(']', '}')
				col1 = '[spoiler={0}]{1}{2}[/spoiler]'.format(bbsafe_filename, img_code, img_alt_str)
			# inline spoiler BBCode pushes trailing text to the bottom, so if we embed images, they have to be at the end
			elif embed_images:
				col1 = '{0}     [spoiler=IMG]{1}{2}[/spoiler]'.format(clip.filename, img_code, img_alt_str)
			elif whole_filename_is_link:
				col1 = '[b][url={1}]{0}[/url][/b]'.format(clip.filename, img_code)
			else:
				col1 = '[b][b][url={1}]IMG[/url][/b]  {0}[/b]'.format(clip.filename, img_code)
		elif suppress_img_warnings:
			col1 = clip.filename
		else:
			col1 = '{0}     {1}'.format(clip.filename, img_error)

		col1 = '[td][align=left][size=2]{}[/size][/align][/td]'.format(col1)
		col2 = '[td]{}[/td]'.format(clip.filesize)
		col3 = '[td]{}[/td]'.format(clip.length)
		col4 = '[td]{0} @ {1}[/td]'.format(clip.vcodec, clip.vbitrate)
		col5 = '[td]{0}×{1} @ {2} {3}[/td]'.format(clip.vwidth, clip.vheight, clip.vframerate, clip.vscantype)
		col6 = '[td]{0} {1} @ {2}[/td]'.format(clip.acodec, clip.abitrate, clip.asample)

		if has_alts:
			if img_code_alt:
				col7 = '[td][url={0}]IMG[/url][/td]'.format(img_code_alt)
			elif img_match_alt and len(img_match_alt) > 1:
				col7 = '[td][b][b][color=#FF8800]![/color][/b][/b][/td]'
			else:
				col7 = '[td][b][b][color=#FF0000]?[/color][/b][/b][/td]'
		else:
			col7 = ''

		output = '[tr]{0}{1}{2}{3}{4}{5}{6}[/tr]\n'.format(col1, col2, col3, col4, col5, col6, col7)

	# output BBCode as a normal list, this is messier to look at, but more flexible with images (and BBCode support)
	else:
		if separator:
			# just a boring row with the directory name
			output = '- [b][i]{}[/i][/b]\n'.format(clip)
			return output

		filename = clip.filename
		fmeta = '{0} ~ {1}'.format(clip.filesize, clip.length)
		vinfo = '{0} {1} ~ {2}×{3} @ {4}'.format(clip.vcodec, clip.vbitrate, clip.vwidth, clip.vheight, clip.vframerate)
		ainfo = '{0} {1} @ {2}'.format(clip.acodec, clip.abitrate, clip.asample)

		if img_code:
			if embed_images:
				img_code = ' [spoiler=:]{0}{1}[/spoiler]'.format(img_code, img_alt_str)
			elif whole_filename_is_link:
				filename = '[url={1}]{0}[/url]'.format(filename, img_code)
				if img_code_alt:
					filename += '  ([url={}]alt.[/url])'.format(img_code_alt)
				img_code = ''
			else:
				if img_code_alt:
					filename = '[b][url={1}]IMG[/url][/b] | [url={2}]aIMG[/url]  {0}'\
							.format(filename, img_code, img_code_alt)
				else:
					filename = '[b][url={1}]IMG[/url][/b]  {0}'.format(filename, img_code)
				img_code = ''
		elif suppress_img_warnings:
			img_code = ''
		else:
			img_code = '     {0}'.format(img_error)

		sep = ' || '

		output = '[b]{1}[/b][size=0] {0} {3} {0} {4} {0} {5} [/size]{2}\n'\
			.format(sep, filename, img_code, fmeta, vinfo, ainfo)

	return output


def metadata_cleanup(clip):
	"""
	Performs various steps in order to check the integrity of the data, as well as cleaning up ugly inputs.
	All this is very specific to MediaInfo, and might even break with versions other than MediaInfo 0.7.92. YMMV
	"""
	# shared adjustments for both RAW and CSV
	if clip.generator in {'RAW', 'CSV'}:

		# some general cleanups
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

	if clip.generator == 'RAW':

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

	elif clip.generator == 'CSV':

		# format video length, not ideal due to default MediaInfo CSV output
		time_segments = re.findall('(\d{1,2}\s?\w{1,5})', clip.length)

		if time_segments:
			time_units = {'h': 0, 'm': 0, 's': 0, 'ms': 0}

			for segment in time_segments:
				if 'ms' in segment:
					time_units['ms'] = segment
				elif 'h' in segment:
					time_units['h'] = segment
				elif 'm' in segment:
					time_units['m'] = segment
				elif 's' in segment:
					time_units['s'] = segment

			for unit, value in time_units.items():
				time_units[unit] = re.sub('\D', '', str(value)).zfill(2)

			setattr(clip, 'length', '{}:{}:{}'.format(time_units['h'], time_units['m'], time_units['s']))

		# some other cleanups
		setattr(clip, 'vwidth', re.sub('\D', '', clip.vwidth))
		setattr(clip, 'vheight', re.sub('\D', '', clip.vheight))

		# remove annoying spaces between numbers: 1 500 kb/s > 1500 kb/s
		setattr(clip, 'vbitrate', re.sub(r'(\d)\s+(\d)', r'\1\2', clip.vbitrate))

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
			error = ('WARNING: No corresponding image-list found! Looked for: {}\n'.format(file_img_list))
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
		error = ('WARNING: No valid image data in image-list! Check the contents of: {}\n'.format(file_img_list))
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
	common_ss_subdirs = ['ss', 'screens', 'screenshots', 'th', 'thumbs', 'thumbnails',
						'SS', 'Screens', 'Screenshots', 'TH', 'Thumbs', 'Thumbnails']
	search_dirs = [filepath]  # same path as the actual video file, so the image would be in the same dir

	for ss_subdir in common_ss_subdirs:
		# commonly named sub-dirs of the same path as the actual video file
		search_dirs.append(os.path.join(filepath, ss_subdir))

	if parse_media and clips_path_recursive:
		# path of video relative to master path
		relpath = os.path.relpath(filepath, clips_path)
		if relpath is not '.':
			for ss_subdir in common_ss_subdirs:
				# for when screenshots are located at the top level dir, but have the same dir structure as the clips
				search_dirs.append(os.path.join(clips_path, ss_subdir, relpath))

		for ss_subdir in common_ss_subdirs:
			# commonly named sub-dirs of the top level clips_path (when recursive clip searching is used)
			search_dirs.append(os.path.join(clips_path, ss_subdir))

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
			print('ERROR: couldn\'t open the following image to calculate hash: {}'.format(ss_found))
			return None
		if 'md5' in algorithm:
			print('calculating MD5 hash for: {}'.format(ss_found))
			return hashlib.md5(img).hexdigest()[:strlen]
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
		sys.exit()

	test_names = test_names.read().splitlines()
	if not test_names:
		print('{1}ERROR: No file-names found for testing in:{2} {0}'.format(ifile, c['FAIL'], c['ENDC']))
		sys.exit()

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


class Clip(object):
	def __init__(self, generator, filepath, filename, filesize, length, vcodec, vcodec_alt, vbitrate, vbitrate_alt,
				vwidth, vheight, vscantype, vframerate, vframerate_alt,
				acodec, abitrate, asample, aprofile):

		self.generator = generator

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


def generate_all_layouts(clips, source):
	"""
	Hijacks the output function and runs it multiple times with differing settings to generate all possible layouts.
	"""
	global layouts_busy
	layouts_busy = True

	global output_as_table
	global embed_images
	global whole_filename_is_link

	output_as_table = True
	embed_images = True
	whole_filename_is_link = True
	format_final_output(clips, source)

	output_as_table = True
	embed_images = False
	whole_filename_is_link = True
	format_final_output(clips, source)

	output_as_table = True
	embed_images = True
	whole_filename_is_link = False
	format_final_output(clips, source)

	output_as_table = True
	embed_images = False
	whole_filename_is_link = False
	format_final_output(clips, source)

	output_as_table = False
	embed_images = False
	whole_filename_is_link = True
	format_final_output(clips, source)

	output_as_table = False
	embed_images = True
	whole_filename_is_link = False
	format_final_output(clips, source)

	output_as_table = False
	embed_images = False
	whole_filename_is_link = False
	format_final_output(clips, source)

	layouts_busy = False

layouts_busy = False  # don't touch!
debug_imghost_slugs = False  # for debugging


def main(argv):
	"""
	Process command-line inputs
	"""
	global working_dir
	global parse_media
	global clips_path
	global clips_path_recursive

	global output_as_table
	global output_individual
	global output_separators
	global output_section_head
	global embed_images
	global whole_filename_is_link
	global suppress_img_warnings
	global all_layouts
	global output_html

	global debug_imghost_slugs

	h = 'mediatobbcode.py\n' \
		'- parse all CSV files in default dir: ./files/\n\n' \
		'mediatobbcode.py -d <working dir>\n' \
		'- parse all CSV files in working dir -d\n\n' \
		'mediatobbcode.py -m <media dir>\n' \
		'- parse all media files in dir -m and output to: ./files/\n\n' \
		'mediatobbcode.py -d <working dir> -m <media dir>\n' \
		'- parse all media files in dir -m and output to -d\n\n' \
		'mediatobbcode.py -d <working dir> -m <media dir> -r\n' \
		'- parse all media files in -m recursively and output to -d\n\n' \
		'For a full list of command-line options, see the online documentation.'

	try:
		opts, args = getopt.getopt(argv, 'hd:m:rlifbutsawx', ['help', 'dir=', 'mediadir=', 'recursive',
															'list', 'individual', 'flat', 'bare', 'url', 'tinylink',
															'suppress', 'all', 'webhtml', 'xdebug'])
	except getopt.GetoptError:
		print(h)
		sys.exit(2)

	for opt, arg in opts:
		if opt in ('-h', '--help'):
			print(h)
			sys.exit()

		elif opt in ('-d', '--dir'):
			working_dir = arg
		elif opt in ('-m', '--mediadir'):
			parse_media = True
			clips_path = arg
		elif opt in ('-r', '--recursive'):
			clips_path_recursive = True

		elif opt in ('-l', '--list'):
			output_as_table = False
		elif opt in ('-i', '--individual'):
			output_individual = True
		elif opt in ('-f', '--flat'):
			output_separators = False
		elif opt in ('-b', '--bare'):
			output_section_head = False
		elif opt in ('-u', '--url'):
			embed_images = False
		elif opt in ('-t', '--tinylink'):
			whole_filename_is_link = False
		elif opt in ('-s', '--suppress'):
			suppress_img_warnings = True
		elif opt in ('-a', '--all'):
			all_layouts = True
		elif opt in ('-w', '--webhtml'):
			output_html = True
		elif opt in ('-x', '--xdebug'):
			debug_imghost_slugs = True

	# if we just want to debug image-host matching for development
	if debug_imghost_slugs:
		debug_imghost_matching()
		sys.exit()

	# some house cleaning before we start
	if not working_dir:
		print('ERROR: no working directory specified!')
		sys.exit()
	else:
		working_dir = os.path.normpath(os.path.expanduser(working_dir))

	if parse_media and not clips_path:
		print('ERROR: no media directory specified!')
		sys.exit()
	elif parse_media and clips_path:
		clips_path = os.path.normpath(os.path.expanduser(clips_path))

	if parse_media:
		parse_media_files()
	else:
		try:
			os.chdir(working_dir)
		except OSError:
			print('ERROR: directory "{}" doesn\'t appear to exist!'.format(working_dir))
			sys.exit()
		parse_csv_files()


# hi there :)
if __name__ == '__main__':
	main(sys.argv[1:])