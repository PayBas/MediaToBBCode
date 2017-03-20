# coding=utf-8

import webbrowser


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
