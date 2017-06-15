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

import exifread                     # [sudo] pip[3] install exifread; https://pypi.python.org/pypi/ExifRead
from PIL import Image               # [sudo] pip[3] install Pillow; https://python-pillow.org/

import create_HDR_script as chs     # from https://github.com/patrick-brian-mooney/python-personal-library

import patrick_logger               # https://github.com/patrick-brian-mooney/python-personal-library/blob/master/patrick_logger.py
from patrick_logger import log_it


patrick_logger.verbosity_level = 3

force_debug = False

min_brightness_value_spread = 80    # Minimum difference between mix and max for image to feed into HDR sequence
min_top_brightness = 100            # Brightest pixel in dark image must have at least this value for image inclusion.
max_low_brightness = 20             # Darkest pixel in bright image must have at least this value for image inclusion.


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
    return None

def approve_brightness_spread(n, x):
    """Given a brightness spread N, X (which is: miN, maX brightness levels in a
    photo), either returns True (meaning "yes, use the photo as part of the HDR
    tonemapping sequence") or False (meaning "no, do not use the photo as part
    of a tonemapping sequence.")
    """
    log_it("INFO: approve_brightness_spread() called to approve spread (%d, %d)" % (n, x), 3)
    if abs(x-n) < min_brightness_value_spread:  # Is brightness spread large enough?
        log_it("    INFO: brightness spread is too small (%d); rejecting ..." % abs(x-n), 3)
        return False                                # If not, don't use the image.
    elif n == 0:                                # Minimum value is pure black?
        log_it('    minimum brightness value is pure black; maximum value is %d' % x, 3)
        return (x >= min_top_brightness)            # Include the image if its brightest point is bright enough.
    elif x == 255:                              # Maximum value is pure white?
        log_it('    maximum brightness value is pure white; minimum value is %d' % n, 3)
        return (n <= max_low_brightness)            # Include the image if its darkest point is bright enough.
    else:                                       # Image brightness data never reaches pure black or pure white?
        log_it('    no reason to reject; including file ...', 3)
        return True                                 # Include the image.

def create_HDR_script(rawfile):
    """Create a series of EV-shifted versions of the raw file, then produce a script
    that will tonemap them. Return the filename of the script.
    """
    log_it("INFO: creating an HDR tonemapping script for raw file '%s'" % rawfile)
    olddir = os.getcwd()
    try:
        head, tail = os.path.split(rawfile)
        if head:                                    # If we're passed in a full path to a file ...
            os.chdir(os.path.dirname(rawfile))
            rawfile = tail
        files_to_merge = [][:]
        selected_files, shift_mappings = {}.copy(), {}.copy()
        shifts = range(-5, 6)
        original_ISO = get_value_from_any_tag(rawfile, ['ISO', 'AutoISO', 'BaseISO'])
        original_Ev = get_value_from_any_tag(rawfile, ['MeasuredEV', 'MeasuredEV2'])
        for shift_factor in shifts:                 # Create individual ISO-shifted files
            log_it("INFO: creating, tagging, and testing a file for shift_factor %d" % shift_factor, 2)
            outfile = os.path.splitext(rawfile)[0] + ("+" if shift_factor >= 0 else "") + str(shift_factor) + ".jpg"
            command = 'dcraw  -c -v -w -W -b %s %s | cjpeg -quality 100 -dct float > %s' % (2 ** shift_factor, rawfile, outfile)
            subprocess.call(command, shell=True)

            # OK, we've produced a file, Let's give it EXIF data, then adjust that data
            try:
                ISO = int(original_ISO) * (2 ** shift_factor)
            except BaseException as e:
                ISO = 100 * (2 ** shift_factor)                 # Pick a plausible value for the base
                log_it("WARNING: unable to calculate real ISO because %s; using dummy ISO value %d" % (e, ISO), 3)
            try:
                Ev = int(original_Ev) + shift_factor
            except BaseException as e:
                Ev = 8 + shift_factor                           # Pick a plausible value for the base
                log_it("WARNING: unable to calculate real Ev because %s; using dummy Ev value %d" % (e, Ev), 3)
            command = 'exiftool -overwrite_original -tagsfromfile %s %s' % (rawfile, outfile)
            subprocess.call(command, shell=True)
            command = 'exiftool -overwrite_original -ISO=%d -AutoISO=%d -BaseISO=%d -MeasuredEV=%d, -MeasuredEV2=%d "%s"' % (ISO, ISO, ISO, Ev, Ev, outfile)
            subprocess.call(command, shell=True)

            # OK, we've got a plausible file at that shift_factor. Let's see if it's a useful one.
            shift_mappings[shift_factor] = outfile
            image = Image.open(outfile).convert(mode="L")
            selected_files[shift_factor] = approve_brightness_spread(*image.getextrema())

        # OK, let's massage the list of files to use.
        assert len([x for x in shifts if selected_files[x]]) > 0, "ERROR: Unable to create any viable files from raw photo"
        earliest_True = min([x for x in shifts if selected_files[x]])
        if earliest_True > min(shifts):
            selected_files[earliest_True-1] = True  # Use one earlier photo
        latest_True = max([x for x in shifts if selected_files[x]])
        if latest_True < max(shifts):
            selected_files[latest_True+1] = True

        for i in sorted(shifts):
            if selected_files[i]:
                files_to_merge += [shift_mappings[i]]               # Use it to construct the HDR.
            else:                                               # Otherwise ...
                os.unlink(shift_mappings[i])        # Delete the file

        # Now move the non-EV-shifted file to the front of the list, because create_script_from_file_list assumes precisely that.
        files_to_merge.insert(0, files_to_merge.pop(files_to_merge.index(os.path.splitext(rawfile)[0] + "+0.jpg")))
        chs.create_script_from_file_list(files_to_merge, delete_originals=True, suppress_align=True)
        return os.path.abspath(os.path.splitext(files_to_merge[0])[0] + '_HDR.SH')
    finally:
        os.chdir(olddir)

def HDR_tonemap_from_raw(rawfile):
    """Write the script, then run it."""
    the_script = create_HDR_script(rawfile)
    subprocess.call(os.path.abspath(the_script), shell=True)

if __name__ == "__main__":
    if force_debug:
        import glob
        sys.argv[1:] = glob.glob('/home/patrick/Desktop/working/temp/*CR2')
    if len(sys.argv) == 1 or sys.argv[1] in ['--help', '-h']:
        print(__doc__)
        sys.exit(0)
    for whichfile in sys.argv[1:] :
        HDR_tonemap_from_raw(whichfile)
