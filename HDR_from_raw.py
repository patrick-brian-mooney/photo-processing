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
import statistics                   # And therefore we require Python 3.4.

from PIL import Image               # [sudo] pip[3] install Pillow; https://python-pillow.org/

import create_HDR_script as chs
import file_utils as fu

import patrick_logger               # https://github.com/patrick-brian-mooney/python-personal-library/blob/master/patrick_logger.py
from patrick_logger import log_it


patrick_logger.verbosity_level = 3

shifts = range(-5, 6)       # Range of Ev adjustments. This is probably the maximum plausible range from a single 12- or 14-bit raw file.

force_debug = True


def massage_file_list(selected_files):
    """Massages the values in SELECTED_FILES, which is a dictionary mapping EVs to
    True/False values indicating whether they will or will not be used in the
    final image. This procedure is the last chance to tweak those use/do not use
    settings.

    Currently, it does nothing other than assert that there is at least one True in
    the list, but it used to also include the following lines:

    earliest_True = min([x for x in selected_files if selected_files[x]])
    if earliest_True > min(selected_files):
        selected_files[earliest_True-1] = True  # Use one earlier photo
    latest_True = max([x for x in selected_files if selected_files[x]])
    if latest_True < max(selected_files):
        selected_files[latest_True+1] = True
    """
    assert len(selected_files) > 0, "ERROR: Unable to create any viable files from raw photo"
    return selected_files

def produce_shifted_tonemap(rawfile, base_ISO, base_Ev, Ev_shift):
    """Produce a TIFF-format tonemap of RAWFILE at a given EV_SHIFT relative to
    BASE_ISO. Return the name of the TIFF file so produced.
    """
    log_it("INFO: creating, tagging, and testing a file for Ev_shift %d" % Ev_shift, 2)
    outfile = os.path.splitext(rawfile)[0] + ("+" if Ev_shift >= 0 else "") + str(Ev_shift) + ".jpg"
    command = 'dcraw  -c -v -w -W -b %s %s | cjpeg -quality 100 -dct float > %s' % (2 ** Ev_shift, rawfile, outfile)
    subprocess.call(command, shell=True)

    # OK, we've produced a file. Let's give it EXIF data, then adjust that data
    try:
        ISO = int(base_ISO) * (2 ** Ev_shift)
    except BaseException as e:
        ISO = 100 * (2 ** Ev_shift)                 # Pick a plausible value for the base
        log_it("WARNING: unable to calculate real ISO because %s; using dummy ISO value %d" % (e, ISO), 3)
    try:
        Ev = int(base_Ev) + Ev_shift
    except BaseException as e:
        Ev = 8 + Ev_shift                           # Pick a plausible value for the base
        log_it("WARNING: unable to calculate real Ev because %s; using dummy Ev value %d" % (e, Ev), 3)
    command = 'exiftool -overwrite_original -tagsfromfile %s %s' % (rawfile, outfile)
    subprocess.call(command, shell=True)
    command = 'exiftool -overwrite_original -ISO=%d -AutoISO=%d -BaseISO=%d -MeasuredEV=%d, -MeasuredEV2=%d "%s"'
    command = command % (ISO, ISO, ISO, Ev, Ev, outfile)
    subprocess.call(command, shell=True)
    return outfile

def get_smoothed_image_histogram(image_filename):
    """Get an image brightness histogram for IMAGE_FILENAME, and then do some smoothing
    on the data so that the calling function can avoid being distracted by noise in
    the data. "Smoothing" here means "low values are dropped to zero."

    Returns a 256-item list, which is the pixel count for each brightness level,
    from 0 (pure black) to 255 (pure white). Note that, because smoothing works by
    swapping zeroes in for small values, the sum of the smoothed histogram values
    will often be noticeably smaller than the number of pixels in the source image.
    """
    h = Image.open(image_filename).convert('L').histogram()
    minimum_threshold = (sum(h) / len(h)) - 2 * statistics.stdev(h) # threshold is 2 standard deviations below the average
    h = [ v if v > minimum_threshold else 0 for v in h ]            # Anything below threshold is dropped to zero
    return h

clipping_threshold = 16     # If >= half the image's data is within this dist. of the relevant edge, we'll consider it clipped.

def is_right_edge_clipping(histo):
    """Returns True if the histogram HISTO is clipped at the right edge, or False
    otherwise. We treat a False from this function as a criterion for detecting
    we've found the darkest image to include in the tonemap.

    Assumes that HISTO is a 256-item brightness histogram.
    """
    return (sum(histo[(256-clipping_threshold):]) >= sum(histo[:(256-clipping_threshold)]))

def is_left_edge_clipping(histo):
    """Returns True if the histogram HISTO is clipped at the left edge, or False
    otherwise. We treat a False from this function as a criterion for detecting
    we've found the darkest image to include in the tonemap.

    Assumes that HISTO is a 256-item brightness histogram.
    """
    return (sum(histo[:clipping_threshold]) >= sum(histo[clipping_threshold:]))

def no_lower_quarter_data(histo):
    """Detect whether all of the data in a (smoothed, presumably) brightness
    histogram is in the upper three-quarters of the brightness graph. We treat
    this as a factor in determining we've found the brightest necessary image
    for the tonemap.
    """
    return sum(histo[:63]) == 0

def create_HDR_script(rawfile):
    """Create a series of EV-shifted versions of RAWFILE, then produce a script that
    will tonemap them. Returns the filename of the script.
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
        original_ISO = fu.get_value_from_any_tag(fu.find_alt_version(rawfile, fu.jpeg_extensions), ['ISO', 'AutoISO', 'BaseISO'])
        original_Ev = fu.get_value_from_any_tag(fu.find_alt_version(rawfile, fu.jpeg_extensions), ['MeasuredEV', 'MeasuredEV2'])
        for shift_factor in shifts:                 # Create individual ISO-shifted files
            outfile = produce_shifted_tonemap(rawfile, original_ISO, original_Ev, shift_factor)
            shift_mappings[shift_factor] = outfile

        # OK, let's trim the list to actually useful images
        # First, start at the top and move downwards, seeking the darkest useful image.
        current_shift, found_beginning, found_end = max(shifts), False, False
        while current_shift >= min(shifts):
            h = get_smoothed_image_histogram(shift_mappings[current_shift])
            if found_end:                               # If we've already found the bottom image ...
                os.unlink(shift_mappings[current_shift])# ... delete this image, which is past it ...
                del(shift_mappings[current_shift])      # ... and track that we don't have it.
            elif found_beginning:                       # Otherwise, check if this is the last image, i.e. 1st one w/o right-edge clipping.
                if is_left_edge_clipping(h):
                    found_end = True
                    os.unlink(shift_mappings[current_shift])
                    del(shift_mappings[current_shift])
            else:
                found_beginning = not is_right_edge_clipping(h)
            current_shift -= 1
        # Now, start at the bottom, and find the lightest useful image
        current_shift, found_beginning, found_end = min(shift_mappings.keys()), False, False
        while current_shift <= max(shifts):
            h = get_smoothed_image_histogram(shift_mappings[current_shift])
            if found_end:
                os.unlink(shift_mappings[current_shift])
                del(shift_mappings[current_shift])
            elif found_beginning:
                if is_right_edge_clipping(h):
                    found_end = True
                    os.unlink(shift_mappings[current_shift])
                    del(shift_mappings[current_shift])
            else:
                found_beginning = not is_left_edge_clipping(h)
            current_shift += 1

        selected_files = list(shift_mappings.values())
        selected_files = massage_file_list(selected_files)
        files_to_merge = sorted(selected_files)

        # Now move the non-EV-shifted file to the front of the list, because create_script_from_file_list assumes precisely that.
        try:    # If the unshifted image appears in the file list, use that for the base exposure
            files_to_merge.insert(0, files_to_merge.pop(files_to_merge.index(os.path.splitext(rawfile)[0] + "+0.jpg")))
        except ValueError:  # Otherwise, just sort the list, which does a fairly good job of picking a low value for the front.
            files_to_merge.sort()
        chs.create_script_from_file_list(files_to_merge, delete_originals=True, suppress_align=True)
        return os.path.abspath(os.path.splitext(files_to_merge[0])[0] + '_HDR.SH')
    finally:
        os.chdir(olddir)

def HDR_tonemap_from_raw(rawfile):
    """Write an HDR-creation script for RAWFILE, then run it."""
    raw_script = create_HDR_script(rawfile)
    subprocess.call(os.path.abspath(raw_script), shell=True)

if __name__ == "__main__":
    if force_debug:
        sys.argv[1:] = ['/home/patrick/Photos/2017-12-22/trip to Portland/2017-12-17_15_52_19_1.CR2']
    if len(sys.argv) == 1 or sys.argv[1] in ['--help', '-h']:
        print(__doc__)
        sys.exit(0)
    for whichfile in sys.argv[1:] :
        HDR_tonemap_from_raw(whichfile)
