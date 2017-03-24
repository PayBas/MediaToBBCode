#!/usr/bin/env python3
# coding=utf-8
# Copyright 2017 PayBas
# All Rights Reserved.

# PyInstaller has problems parsing modules with "get_distribution('name').version", so we'll use a hook.

from PyInstaller.utils.hooks import copy_metadata

datas = copy_metadata('pymediainfo')
