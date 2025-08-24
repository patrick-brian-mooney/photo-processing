#!/home/patrick/Documents/programming/python_projects/photo-processing/bin/python3
# -*- coding: utf-8 -*-
"""Takes a raw image file and creates a tonemapped HDR from it. Requires dcraw
and the panotools suite.

It can also be imported as a module by Python 3.X programs.

This program is part of Patrick Mooney's photo postprocessing scripts; the
complete set can be found at https://github.com/patrick-brian-mooney/photo-processing.
All programs in that collection are copyright 2015-2019 by Patrick Mooney; they
are free software released under the GNU GPL, either version 3 or (at your
option) any later version. See the file LICENSE.md for details.

The latest version of these scripts can always be found at
    https://github.com/patrick-brian-mooney/photo-processing
"""


import os
import shlex
import statistics                   # And therefore we require Python 3.4+.
import subprocess
import sys
import time

from pathlib import Path
from typing import List, Sequence, Union


from PIL import Image               # [sudo] pip[3] install Pillow; https://python-pillow.org/

import patrick_logger               # https://github.com/patrick-brian-mooney/python-personal-library/
from patrick_logger import log_it

import create_HDR_script as chs     # https://github.com/patrick-brian-mooney/photo-processing
import photo_file_utils as fu
import photo_config


photo_config.startup()              # Check that the system meets minimum requirements; find necessary executables


patrick_logger.verbosity_level = 3

shifts = range(-5, 6)       # Range of Ev adjustments: probably the maximum plausible range from a single raw file.
clipping_threshold = 32     # If >= half image data this close to the relevant edge, we consider it clipped.


def massage_file_list(selected_files: Sequence[Path]) -> Sequence[Path]:
    """Massages the values in SELECTED_FILES, which is a dictionary mapping EVs to
    True/False values indicating whether they will or will not be used in the
    final image. This procedure is the last chance to tweak those use/do not use
    settings.

    This routine has done more in the past and may do more in the future.
    """
    assert isinstance(selected_files, Sequence)
    assert selected_files, "ERROR: No files created to use in tonemapping raw photo!"
    assert all([isinstance(f, Path) for f in selected_files]), "ERROR! All files passed must be Paths!"

    return selected_files


def produce_shifted_tonemap(raw_file: Path,
                            ev_shift: int) -> Path:
    """Produce a TIFF-format tonemap of RAW_FILE at a given EV_SHIFT. Return the name
    of the TIFF file produced.
    """
    log_it("INFO: creating, tagging, and testing a file for Ev shift %d" % ev_shift, 2)
    outfile = Path(f'HDR_AIS_{raw_file.stem}{"+" if ev_shift >= 0 else ""}{ev_shift}').with_suffix(".tif")

    command = [photo_config.executable_location('dcraw'), '-T', '-c', '-v', '-w', '-W', '-b']
    command += [str(2 ** ev_shift), str(raw_file)]

    with open(outfile, mode="w") as the_output:
        subprocess.call(command, stdout=the_output)

    return outfile


def get_smoothed_image_histogram(image_filename: Path) -> List[int]:
    """Get an image brightness histogram for IMAGE_FILENAME, and then do some smoothing
    on the data so that the calling function can avoid being distracted by noise in
    the data. "Smoothing" here means "low values are dropped to zero."

    Returns a 256-item list, which is the pixel count for each brightness level,
    from 0 (pure black) to 255 (pure white). Note that, because smoothing works by
    swapping zeroes in for small values, the sum of the smoothed histogram values
    will often be noticeably smaller than the number of pixels in the source image.
    """
    assert isinstance(image_filename, Path), "ERROR! IMAGE_FILENAME must be a Path!"

    h = Image.open(image_filename).convert('L').histogram()
    minimum_threshold = (sum(h) / len(h)) - 2 * statistics.stdev(h)     # threshold: 2 std devs below the average
    h = [ v if v > minimum_threshold else 0 for v in h ]                # Anything below threshold is dropped to zero

    return h


def is_right_edge_clipping(histo: List[int]) -> bool:
    """Returns True if the histogram HISTO is clipped at the right edge, or False
    otherwise. We treat a False from this function as a criterion for detecting
    whether we've found the darkest image to include in the tonemap.

    Assumes that HISTO is a 256-item brightness histogram.
    """
    return sum(histo[(256-clipping_threshold):]) >= sum(histo[:(256-clipping_threshold)])


def is_left_edge_clipping(histo: List[int]) -> bool:
    """Returns True if the histogram HISTO is clipped at the left edge, or False
    otherwise. We treat a False from this function as a criterion for detecting
    when we've found the darkest image to include in the tonemap.

    Assumes that HISTO is a 256-item brightness histogram.

    #FIXME: I think we need different numerical thresholds for "right-edge clipping"
    and "left-edge clipping." I think this will solve the "HDRs often come out too
    bright" problem. Let's test this when we get some time.
    """
    return sum(histo[:clipping_threshold]) >= sum(histo[clipping_threshold:])


def no_lower_quarter_data(histo: List[int]) -> bool:
    """Detect whether all the data in a (smoothed, presumably) brightness
    histogram is in the upper three-quarters of the brightness graph. We treat
    this as a factor in determining when we've found the brightest necessary
    image for the tonemap.
    """
    return sum(histo[:63]) == 0


def create_hdr_script(raw_file: Path) -> Union[Path, None]:
    """Create a series of EV-shifted versions of RAW_FILE, then produce a script that
    will tonemap them. RAW_FILE is the pathname to the raw file. Returns the filename
    of the script that it created.
    """
    assert isinstance(raw_file, Path), "ERROR! Files passed to create_hdr_script must be Paths!"
    assert raw_file.exists(), "ERROR! Cannot produce an HDR script for a file that does not exist!"
    assert raw_file.suffix.casefold() in fu.raw_photo_extensions, \
        f"ERROR! {raw_file.suffix} is not a recognized raw file!"

    log_it(f"INFO: creating an HDR tonemapping script for raw file '{raw_file}'")
    old_dir = os.getcwd()

    try:
        head, tail = raw_file.parent, Path(raw_file.name)
        if head:                                    # If we're passed in a full path to a file ...
            os.chdir(head)
            raw_file = tail

        # Create individual ISO-shifted files
        shift_mappings = {shift_factor: produce_shifted_tonemap(raw_file, shift_factor) for shift_factor in shifts}

        # OK, let's trim the list to actually useful images
        # First, start at the top and move downwards, seeking the darkest useful image.
        current_shift, found_beginning, found_end = max(shifts), False, False
        while current_shift >= min(shifts):
            h = get_smoothed_image_histogram(shift_mappings[current_shift])
            if found_end:                                   # If we've already found the bottom image ...
                shift_mappings[current_shift].unlink()      # ... delete this image, which is past it ...
                del(shift_mappings[current_shift])          # ... and track that we don't have it.
            elif found_beginning:
                if is_left_edge_clipping(h):                # Otherwise, check if this is the last image:
                    found_end = True                        # that is, the first one w/ left-edge clipping.
                    shift_mappings[current_shift].unlink()
                    del(shift_mappings[current_shift])
            else:
                found_beginning = not is_right_edge_clipping(h)
            current_shift -= 1

        # Now, start at the bottom, and find the lightest useful image
        current_shift, found_beginning, found_end = min(shift_mappings.keys()), False, False
        while current_shift <= max(shifts):
            h = get_smoothed_image_histogram(shift_mappings[current_shift])
            if found_end:
                shift_mappings[current_shift].unlink()
                del(shift_mappings[current_shift])
            elif found_beginning:
                if is_right_edge_clipping(h):
                    found_end = True
                    shift_mappings[current_shift].unlink()
                    del(shift_mappings[current_shift])
            else:
                found_beginning = not is_left_edge_clipping(h)
            current_shift += 1

        files_to_merge = sorted(massage_file_list(list(shift_mappings.values())))
        base_tiff = Path(raw_file.stem + "+0.tif")

        # Now move the non-Ev-shifted file to the front of the list; create_script_from_file_list assumes that.
        try:    # If the unshifted image appears in the file list, use that for the base exposure
            files_to_merge.insert(0, files_to_merge.pop(files_to_merge.index(base_tiff)))
        except ValueError:
            # Otherwise, just sort the list, which does a fairly good job of picking a low value for the front.
            # FIXME: use the middle file instead
            files_to_merge.sort()
            base_tiff = files_to_merge[0]
        new_script = chs.create_script_from_file_list(files_to_merge, delete_originals=True, suppress_align=True,
                                                      metadata_source=fu.find_alt_version(raw_file,
                                                                                          fu.jpeg_extensions))
        return Path(new_script).resolve()

    except BaseException as e:
        log_it(f"ERROR: create_hdr_script() got error {e} while trying to create a script for {raw_file}.")
        return None

    finally:
        os.chdir(old_dir)


def hdr_tonemap_from_raw(raw_file: Path) -> None:
    """Write an HDR-creation script for RAW_FILE, then run it.
    """
    try:
        raw_script = create_hdr_script(raw_file)
        subprocess.call([str(raw_script.resolve())])
        os.system(f'chmod a-x -R {shlex.quote(str(raw_script))}')
    except (Exception,) as errrr:
        print(f"Unable to create HDR tonemap from {raw_file}! The system said: {errrr}.")


force_debug = False


if __name__ == "__main__":
    if force_debug:
        # Any debugging-harness commands go here.
        # hdr_tonemap_from_raw("/home/patrick/Photos/film/by roll number/1485/1485-01.dng")
        pass
    if len(sys.argv) == 1 or sys.argv[1] in ['--help', '-h']:
        print(__doc__)
        sys.exit(0)
    for whichfile in sys.argv[1:]:
        if whichfile:
            print(f"Processing {whichfile} ...")
            time.sleep(0.5)
            hdr_tonemap_from_raw(Path(whichfile))
        else:
            print("Skipping parameter %s that was passed in: it's not truthy!" % whichfile)
