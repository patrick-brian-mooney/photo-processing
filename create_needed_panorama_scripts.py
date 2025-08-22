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

import os
import time

from pathlib import Path

import tqdm

import create_panorama_script as cps        # https://github.com/patrick-brian-mooney/photo-processing/


def main() -> None:
    # If we ever require Python 3.12+, we can use pathlib.Path.walk instead of os.walk
    for i, _, __ in tqdm.tqdm(os.walk('.')):
        olddir = os.getcwd()
        try:
            os.chdir(i)
            print(f"Currently checking directory: {Path(i).resolve()}")
            jpegs = [f for f in Path().glob('*') if f.suffix.casefold() == '.jpg']
            if jpegs:
                print(f"  {len(jpegs)} JPEG files found!", end=" ")
                if [f for f in Path().glob('*') if f.suffix.casefold() == '.pto']:
                    print("But there's an existing project file! Skipping...")
                    continue

                print("Creating new project script ...")
                cps.produce_script(jpegs)
        finally:
            os.chdir(olddir)
            time.sleep(0.1)


if __name__ == "__main__":
    main()
