#!/usr/bin/env python3
# coding=utf-8
# Copyright 2017 PayBas
# All Rights Reserved.

import os
import unittest

from mediatobbcode import core, config

test_dir = os.path.dirname(os.path.abspath(__file__))


class MediaToBBCodeTest(unittest.TestCase):
	def setUp(self):
		config.populate_opts()
		media_dir = os.path.join(test_dir, 'videos')
		output_dir = media_dir
		config.opts['media_dir'] = media_dir
		config.opts['output_dir'] = output_dir
		self.output_file = os.path.join(output_dir, os.path.basename(media_dir) + '_output.txt')
		self.compare_file = os.path.join(output_dir, os.path.basename(media_dir) + '_output_test.txt')
		core.set_paths_and_run()

		with open(self.output_file) as file:
			output = file.read()
		self.output = output

		with open(self.compare_file) as file:
			compare = file.read()
		self.compare = compare

	def test_output(self):
		self.assertEqual(self.output, self.compare)

	def tearDown(self):
		os.remove(self.output_file)
