#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""This script starts in the current directory and recursively examines each of its
subdirectories. It looks for directories that have JPEG files but no hugin
project files. When it finds such a directory, it callscreate_panorama_script.py to create a script that will automatically create a
hugin project file.
This is a utility script that is intended to work on my own hard drive, where I
have a single directory containing multiple other directories, each of whichsubdirectories contains a group of photos that need to be stitched into a
single panorama. It's kind of a hack, but may be useful to others.

This program is part of Patrick Mooney's photo postprocessing scripts; the
complete set can be found at https://github.com/patrick-brian-mooney/photo-processing.
All programs in that collection are copyright 2015-2017 by Patrick Mooney; they
are free software released under the GNU GPL, either version 3 or (at your
option) any later version. See the file LICENSE.md for details.
"""

import glob, os, subprocess, time

if __name__ == "__main__":
    for i in sorted([x[0] for x in os.walk('.')]):
        try:
            olddir = os.getcwd()
            os.chdir(i)
            print("Currently checking directory:  " + i)
            if len(glob.glob('*jpg') + glob.glob("*JPG")) > 0:
                print("  JPEG files found!", end=" ")
                if len(glob.glob("*pto")) > 0:
                    print("But there's an existing project file! Skipping...")
                else:
                    print("Creating new project script ...")
                    subprocess.call('create_panorama_script.py', shell=True)
        finally:
            os.chdir(olddir)
            time.sleep(0.1)

