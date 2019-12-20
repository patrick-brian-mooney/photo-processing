#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""This quick hack makes an HDR script from all JPG photos in the current
directory. Then it runs it. It assumes that all of the photos are JPGs in the
current directory, that all of the JPGs in the current directory are photos for
the project, and that there are no other .SH files in the current directory.

This program comes with ABSOLUTELY NO WARRANTY. Use at your own risk.

This program is part of Patrick Mooney's photo postprocessing scripts; the
complete set can be found at https://github.com/patrick-brian-mooney/photo-processing.
All programs in that collection are copyright 2015-2019 by Patrick Mooney; they
are free software released under the GNU GPL, either version 3 or (at your
option) any later version. See the file LICENSE.md for details.

The latest version of these scripts can always be found at
    https://github.com/patrick-brian-mooney/photo-processing
"""

import os, glob

import postprocess_photos as pp     # https://github.com/patrick-brian-mooney/photo-processing/blob/master/postprocess_photos.py
import create_HDR_script as cHs     # https://github.com/patrick-brian-mooney/photo-processing/blob/master/create_HDR_script.py


the_files = sorted(glob.glob('*JPG') + glob.glob('*jpg'))
if len(the_files) > 0:
    cHs.create_script_from_file_list(the_files)
    pp.run_shell_scripts()
else:
    raise IndexError('You must call HDR_from_all.py in a folder with at least one *jpg or *JPG file;\n   current working directory is: %s' % os.getcwd())
