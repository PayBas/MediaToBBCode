#!/usr/bin/env python3
# coding=utf-8
# Copyright 2017 PayBas
# All Rights Reserved.

from setuptools import setup, find_packages
from mediatobbcode import config

setup(
	name='MediaToBBCode',
	version=config.version,
	author=config.author,
	author_email='paybas@gmail.com',
	url=config.script_url,
	description='Parse media files and output to BBCode.',
	long_description=('A Python script that combines the metadata output of MediaInfo with the BBCode output of various '
					'image-hosts to automatically generate a BBCode-formatted presentation of a media-clips collection.'),
	packages=find_packages(),
	include_package_data=True,
	license='GNU General Public License v3 (GPLv3)',
	tests_require=['nose'],
	test_suite="nose.collector",
	install_requires=['pymediainfo', 'Pillow', 'bbcode'],
	classifiers=[
		'Development Status :: 5 - Production/Stable',
		'Programming Language :: Python',
		'Programming Language :: Python :: 3.4',
		'Programming Language :: Python :: 3.5',
		'Programming Language :: Python :: 3.6',
		'Environment :: Console',
		'Environment :: Qt',
		'Operating System :: POSIX :: Linux',
		'Operating System :: Microsoft :: Windows',
		'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
		'Intended Audience :: Developers',
		'Intended Audience :: End Users/Desktop',
		'Topic :: Multimedia'
	]
)
