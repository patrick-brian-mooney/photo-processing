#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""This script starts in the current directory and recursively examines each of its
subdirectories. It looks for directories that have JPEG files but no hugin
project files. When it finds such a directory, it calls
create_panorama_script.py to create a script that will automatically create a
hugin project file.

This is a utility script that is intended to work on my own hard drive, where I
have a single directory containing multiple other directories, each of which
subdirectories contains a group of photos that need to be stitched into a
single panorama. It's kind of a hack, but it may be useful to others. (It may
need substantial adaptation IN ORDER to be useful to others, though.)

This program is part of Patrick Mooney's photo postprocessing scripts; the
complete set can be found at https://github.com/patrick-brian-mooney/photo-processing.
All programs in that collection are copyright 2015-2019 by Patrick Mooney; they
are free software released under the GNU GPL, either version 3 or (at your
option) any later version. See the file LICENSE.md for details.

The latest version of these scripts can always be found at
    https://github.com/patrick-brian-mooney/photo-processing
"""

import glob
import os
import subprocess
import time

import photo_config               # https://github.com/patrick-brian-mooney/photo-processing/


def main():
    for i in sorted([x[0] for x in os.walk('.')]):
        try:
            olddir = os.getcwd()
            os.chdir(i)
            print("Currently checking directory:  " + os.path.abspath(i))
            if len(glob.glob('*jpg') + glob.glob("*JPG")) > 0:
                print("  JPEG files found!", end=" ")
                if len(glob.glob("*pto")) > 0:
                    print("But there's an existing project file! Skipping...")
                else:
                    print("Creating new project script ...")
                    subprocess.call([os.path.join(photo_config.executable_location('photo-processing'),
                                                 'create_panorama_script.py')])
        finally:
            os.chdir(olddir)
            time.sleep(0.1)


if __name__ == "__main__":
    main()
