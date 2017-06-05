#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Takes a raw image file and creates a tonemapped HDR from it. Requires dcraw
and the panotools suite.

Usage:

    ./HDR_from_raw FILE [FILE2] [FILE3] [...]

It can also be imported as a module by Python 3.X programs.

This script is copyright 2017 by Patrick Mooney. It is licensed under the GPL,
either version 3 or (at your option) any later version. See the file LICENSE.md
for details.
"""


import os, subprocess, sys

import exifread

import create_HDR_script as chs     # from  https://github.com/patrick-brian-mooney/python-personal-library


force_debug = False


def get_value_from_any_tag(filename, taglist):
    """Read the EXIF tags from the file in FILENAME, then return the value of the
    first tag in the file that is found from the desired tags specified in TAGLIST.
    """
    with open(filename, 'rb') as f:
        tags = exifread.process_file(f, details=False)
    for tag in taglist:
        try:
            return tags[tag]
        except KeyError:
            continue
    return None                 # E > I, so be explicit here.

def create_HDR_script(rawfile):
    """Create a series of EV-shifted versions of the raw file, then produce a script
    that will tonemap them. Return the filename of the script.
    """
    files_to_merge = [][:]
    shifts = range(-4, 5)
    original_ISO = get_value_from_any_tag(rawfile, ['ISO', 'AutoISO', 'BaseISO'])
    original_Ev = get_value_from_any_tag(rawfile, ['MeasuredEV', 'MeasuredEV2'])
    for shift_factor in shifts:                 # Create ISO-shifted files
        outfile = os.path.splitext(rawfile)[0] + ("+" if shift_factor >= 0 else "-") + str(shift_factor) + ".jpg"
        command = 'dcraw  -c -v -w -W -b %s %s | cjpeg -quality 100 -dct float > %s' % (2 ** shift_factor, rawfile, outfile)
        subprocess.call(command, shell=True)

        # OK, we've produced a file, Let's give it EXIF data, then adjust that data
        try:
            ISO = int(original_ISO) * (2 ** shift_factor)
        except BaseException:
            ISO = 100 * (2 ** shift_factor)                 # Pick a plausible value for the base
        try:
            Ev = int(original_Ev) + shift_factor
        except BaseException:
            Ev = 8 + shift_factor                           # Pick a plausible value for the base
        subprocess.call('exiftool -overwrite_original -tagsfromfile %s %s' % (rawfile, outfile), shell=True)
        subprocess.call('exiftool -overwrite_original -ISO=%d -AutoISO=%d -BaseISO=%d -MeasuredEV=%d, -MeasuredEV2=%d "%s"' % (ISO, ISO, ISO, Ev, Ev, outfile), shell=True)

        files_to_merge += [outfile]

    # Now move the non-EV-shifted file to the front of the list, because create_script_from_file_list assumes precisely that.
    files_to_merge.insert(0, files_to_merge.pop(files_to_merge.index(os.path.splitext(rawfile)[0] + "+0.jpg")))
    chs.create_script_from_file_list(files_to_merge, delete_originals=True)
    return os.path.splitext(files_to_merge[0])[0] + '_HDR.SH'

def HDR_tonemap_from_raw(rawfile):
    """Write the script, then run it."""
    the_script = create_HDR_script(rawfile)
    subprocess.call(os.path.abspath(the_script), shell=True)

if __name__ == "__main__":
    if force_debug:
        sys.argv += ['/home/patrick/Desktop/working/temp/IMG_7642.CR2']
    if len(sys.argv) == 1 or sys.argv[1] in ['--help', '-h']:
        print(__doc__)
        sys.exit(0)
    for whichfile in sys.argv[1:] :
        HDR_tonemap_from_raw(whichfile)
