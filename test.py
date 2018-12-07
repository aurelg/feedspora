#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Run pytest in the proper directory
"""

import os
import pathlib

import pytest

os.chdir(pathlib.Path.cwd() / "tests")

pytest.main()
