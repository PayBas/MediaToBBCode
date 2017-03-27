#!/usr/bin/env python3
# coding=utf-8
# Copyright 2017 PayBas
# All Rights Reserved.

import os
import unittest

from mediatobbcode import core, config

test_dir = os.path.dirname(os.path.abspath(__file__))


class FullRunTest(unittest.TestCase):
	def setUp(self):
		self.media_dir = os.path.join(test_dir, 'videos')
		self.output_dir = self.media_dir
		self.output_file = os.path.join(self.output_dir, os.path.basename(self.media_dir) + '_output.txt')
		self.reference_dir = os.path.join(test_dir, 'reference-outputs')
		self.maxDiff = None

	def testDefault(self):
		config.populate_opts()
		config.opts['media_dir'] = self.media_dir
		config.opts['output_dir'] = self.output_dir

		core.set_paths_and_run()

		with open(os.path.join(self.reference_dir, 'default.txt')) as file:
			correct = file.read()

		with open(self.output_file) as file:
			output = file.read()
		os.remove(self.output_file)

		self.assertEqual(correct, output)

	def testFullSize(self):
		config.populate_opts()
		config.opts['media_dir'] = self.media_dir
		config.opts['output_dir'] = self.output_dir

		config.opts['use_imagelist_fullsize'] = True
		config.opts['use_primary_as_fullsize'] = True

		core.set_paths_and_run()

		with open(os.path.join(self.reference_dir, 'fullsize.txt')) as file:
			correct = file.read()

		with open(self.output_file) as file:
			output = file.read()

		os.remove(self.output_file)
		self.assertEqual(correct, output)

	def testImageSets(self):
		config.populate_opts()
		config.opts['media_dir'] = self.media_dir
		config.opts['output_dir'] = self.output_dir

		config.opts['parse_zip'] = True

		core.set_paths_and_run()

		with open(os.path.join(self.reference_dir, 'imagesets.txt')) as file:
			correct = file.read()

		with open(self.output_file) as file:
			output = file.read()

		os.remove(self.output_file)
		self.assertEqual(correct, output)
