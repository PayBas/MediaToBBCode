#!/usr/bin/env python3
# coding=utf-8
# Copyright 2017 PayBas
# All Rights Reserved.

import os
import re
import sys
import webbrowser
from PyQt5.QtCore import Qt, QObject, QThread, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QColor, QFont, QIcon, QTextCursor
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QGridLayout, QHBoxLayout, QGroupBox, QTabWidget,
	QLabel, QLineEdit, QPlainTextEdit, QCheckBox, QPushButton, QFrame, QFileDialog, QColorDialog, QMessageBox)
from dottorrentGUI import gui as dott_gui
import config
import core


# noinspection PyArgumentList, PyUnresolvedReferences, PyTypeChecker, PyCallByClass
class QtGUI(QMainWindow):
	def __init__(self):
		super().__init__()

		self.widgets = {}  # dictionary of some mutable widgets, for easier manipulation
		self.parse_thread = None  # defined here just to appease PEP
		self.parse_worker = None  # defined here just to appease PEP

		central_widget = QWidget(self)
		central_layout = QGridLayout(central_widget)

		# INPUT OPTIONS
		frame_iops = QGroupBox('Input options', central_widget)
		layout_iops = QGridLayout(frame_iops)

		label_mdir = QLabel(config.config['iopts']['media_dir'][1], frame_iops)
		label_mdir.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
		layout_iops.addWidget(label_mdir, 0, 0)

		label_odir = QLabel(config.config['iopts']['output_dir'][1], frame_iops)
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

		self.widgets['recursive'] = QCheckBox(config.config['iopts']['recursive'][1], frame_iops)
		self.widgets['recursive'].stateChanged.connect(self.update_gui_oopts)
		self.widgets['recursive'].stateChanged.connect(self.update_gui_mopts)
		layout_iops.addWidget(self.widgets['recursive'], 0, 3)

		self.widgets['parse_zip'] = QCheckBox(config.config['iopts']['parse_zip'][1], frame_iops)
		self.widgets['parse_zip'].stateChanged.connect(self.update_gui_oopts)
		layout_iops.addWidget(self.widgets['parse_zip'], 1, 3)

		central_layout.addWidget(frame_iops, 0, 0)

		# TABS
		tabs = QTabWidget(central_widget)

		# OUTPUT OPTIONS
		tab_oopts = QWidget(tabs)
		layout_oopts = QGridLayout(tab_oopts)

		row = 0
		for oopt, values in config.config['oopts'].items():
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
		for mopt, values in config.config['mopts'].items():
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
			if 'imagelist_alternative' in mopt:
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
		for dopt, values in config.config['dopts'].items():
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

		script_display = QLabel(config.script, tab_about)
		script_font = QFont()
		script_font.setPointSize(20)
		script_display.setFont(script_font)
		script_display.setAlignment(Qt.AlignCenter | Qt.AlignVCenter)
		script_display.mousePressEvent = lambda event: self.visit_website(config.script_url)
		layout_about.addWidget(script_display, 1, 1, 1, 2)

		author_label = QLabel('author:', tab_about)
		author_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
		layout_about.addWidget(author_label, 2, 1)

		author_content = QLabel(config.author, tab_about)
		author_content.mousePressEvent = lambda event: self.visit_website(config.author_url)
		layout_about.addWidget(author_content, 2, 2)

		version_label = QLabel('version:', tab_about)
		version_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
		layout_about.addWidget(version_label, 3, 1)

		version_content = QLabel(config.version, tab_about)
		layout_about.addWidget(version_content, 3, 2)

		compile_label = QLabel('compile date:', tab_about)
		compile_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
		layout_about.addWidget(compile_label, 4, 1)

		compile_content = QLabel(config.compile_date, tab_about)
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

		self.button_torrent = QPushButton('Create Torrent', frame_run)
		self.button_torrent.clicked.connect(self.create_torrent)

		self.button_run = QPushButton('Run', frame_run)
		self.button_run.clicked.connect(self.run_start)

		layout_run.addStretch()
		layout_run.addWidget(self.button_torrent)
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
		self.setWindowTitle(config.script)
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
				self.widgets[opt].setText(config.opts[opt])
			elif isinstance(widget, QCheckBox):
				self.widgets[opt].setChecked(config.opts[opt])

	def get_gui_values(self, allow_disabled=False):
		for opt, widget in self.widgets.items():
			if isinstance(widget, QLineEdit):
				if widget.isEnabled() or allow_disabled:
					config.opts[opt] = widget.text()
				else:
					config.opts[opt] = ''
			elif isinstance(widget, QCheckBox):
				if widget.isEnabled() or allow_disabled:
					config.opts[opt] = widget.isChecked()
				else:
					config.opts[opt] = False

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

		if (self.widgets['recursive'].isChecked() and
			self.widgets['recursive'].isEnabled() and
			self.widgets['output_individual'].isChecked()):

			self.tab_mopts.setDisabled(True)
			self.label_mopts.setVisible(False)
			self.label_mopts_disabled.setVisible(True)
		else:
			self.tab_mopts.setDisabled(False)
			self.label_mopts.setVisible(True)
			self.label_mopts_disabled.setVisible(False)

		if self.widgets['use_imagelist_fullsize'].isChecked():
			self.widgets['use_primary_as_fullsize'].setDisabled(False)
		else:
			self.widgets['use_primary_as_fullsize'].setDisabled(True)

		if (self.widgets['use_imagelist_fullsize'].isChecked() and not
			self.widgets['use_primary_as_fullsize'].isChecked()):

			self.widgets['imagelist_fullsize'].setDisabled(False)
			self.imagelist_buttons['imagelist_fullsize'].setDisabled(False)
		else:
			self.widgets['imagelist_fullsize'].setDisabled(True)
			self.imagelist_buttons['imagelist_fullsize'].setDisabled(True)

		if not output_dir and not media_dir:
			base = ''
		elif not output_dir:
			base = os.path.normpath(os.path.join(media_dir, os.path.basename(media_dir)))
		else:
			base = os.path.normpath(os.path.join(output_dir, os.path.basename(media_dir)))

		self.widgets['imagelist_primary'].setPlaceholderText(base + '.txt')
		self.widgets['imagelist_alternative'].setPlaceholderText(base + '_alt.txt')
		self.widgets['imagelist_fullsize'].setPlaceholderText(base + '_fullsize.txt')

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
		initial_dir = ''
		filters = 'INI Files (*.ini *.conf);;All Files (*.*)'
		selected_filter = 'INI Files (*.ini *.conf)'
		file = QFileDialog.getSaveFileName(self, caption, initial_dir, filters, selected_filter)[0]

		if file:
			self.get_gui_values()
			config.save_config_file(file)

	@pyqtSlot()
	def load_config(self):
		caption = 'Load config file'
		initial_dir = ''
		filters = 'INI Files (*.ini *.conf);;All Files (*.*)'
		selected_filter = 'INI Files (*.ini *.conf)'
		file = QFileDialog.getOpenFileName(self, caption, initial_dir, filters, selected_filter)[0]

		if file:
			success = config.load_config_file(file)
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
		config.populate_opts()
		self.set_gui_values()
		self.initializing = False
		self.update_gui_oopts()
		self.update_gui_mopts()
		self.update_gui_dopts()

	@pyqtSlot()
	def run_start(self):
		self.get_gui_values()
		self.log_text.clear()
		config.kill_thread = False

		self.parse_thread = QThread()
		self.parse_worker = self.ParseWorker()
		self.parse_worker.moveToThread(self.parse_thread)
		self.parse_worker.finished.connect(self.run_finish)
		self.parse_thread.started.connect(self.parse_worker.run)
		self.parse_thread.finished.connect(self.run_finish)
		self.parse_thread.start()

		self.button_run.setText('Stop')
		self.button_run.clicked.disconnect()
		self.button_run.clicked.connect(self.run_terminate)

	@pyqtSlot()
	def run_finish(self):
		self.parse_thread.quit()

		self.button_run.setText('Run')
		self.button_run.clicked.disconnect()
		self.button_run.clicked.connect(self.run_start)

	@pyqtSlot()
	def run_terminate(self):
		if self.parse_thread.isRunning():
			config.kill_thread = True
			self.parse_thread.terminate()
			print('Thread terminated!')

	@pyqtSlot()
	def create_torrent(self):
		self.get_gui_values()

		# noinspection PyBroadException
		try:
			dott_window = QMainWindow(self)
			ui = dott_gui.DottorrentGUI()
			ui.setupUi(dott_window)
			ui.loadSettings()
			ui.clipboard = QApplication.instance().clipboard
			dott_window.resize(500, 800)

			# manipulate the dottorrent settings to reflect config options
			ui.directoryRadioButton.setChecked(True)
			ui.inputEdit.setText(config.opts['media_dir'])
			if config.opts['recursive'] and config.opts['output_individual']:
				ui.batchModeCheckBox.setChecked(True)
			else:
				ui.batchModeCheckBox.setChecked(False)
			if not ui.excludeEdit.toPlainText():
				ui.excludeEdit.setPlainText('*.txt\n*.ini\n*.torrent')
			ui.initializeTorrent()

			def dott_close_event(event):
				ui.saveSettings()
				event.accept()
			dott_window.closeEvent = dott_close_event
			dott_window.show()
		except:
			(errortype, value, traceback) = sys.exc_info()
			sys.excepthook(errortype, value, traceback)

	@pyqtSlot(str)
	def log_append(self, text):
		self.log_text.moveCursor(QTextCursor.End)
		self.log_text.insertPlainText(text)

	def closeEvent(self, event):
		self.get_gui_values(True)

		if config.opts == config.opts_saved:
			event.accept()
		else:
			title = 'Settings changed'
			question = 'There appear to be unsaved setting changes.\nAre you sure you want to quit?'
			reply = QMessageBox.question(self, title, question, QMessageBox.Yes, QMessageBox.No)

			if reply == QMessageBox.Yes:
				event.accept()
			else:
				event.ignore()

	class ParseWorker(QObject):
		"""
		Note to self: disable "PyQt compatible" in Python debugger settings, or this will break.
		http://stackoverflow.com/a/6789205
		"""
		finished = pyqtSignal()

		@pyqtSlot()
		def run(self):
			# noinspection PyBroadException
			try:
				core.set_paths_and_run()
				self.finished.emit()
			except:
				(errortype, value, traceback) = sys.exc_info()
				sys.excepthook(errortype, value, traceback)
				self.exit()

	# redirect stdout (print) to a widget
	# adapted from http://stackoverflow.com/a/22582213
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


def main():
	# set the default opts as initial values
	config.populate_opts()

	app = QApplication(sys.argv)
	gui = QtGUI()
	gui.show()
	sys.exit(app.exec_())


# hi there :)
if __name__ == '__main__':
	main()
