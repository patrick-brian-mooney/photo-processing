#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A series of declarations about external programs, used by other scripts in the
photo processing collection.

This program comes with ABSOLUTELY NO WARRANTY. Use at your own risk.

This program is part of Patrick Mooney's photo postprocessing scripts; the
complete set can be found at https://github.com/patrick-brian-mooney/photo-processing.
All programs in that collection are copyright 2015-2019 by Patrick Mooney; they
are free software released under the GNU GPL, either version 3 or (at your
option) any later version. See the file LICENSE.md for details.
"""


import os, platform, shlex, subprocess, sys

import PIL  # I'd rather have this fail here, during setup checking, then


# The list of executable programs and their locations. Anything whose value is set to None will be searched for in
# the user's $PATH. If the executable is not in the $PATH, it can be set manually here. Note that some paths set here
# are not actually called by any of the photo-processing scripts directly: instead, they are called by bash scripts
# written by the photo-postprocessing scripts. They go here both for completeness's sake and because this forces a
# check for their existence, which means that the relevant "program not installed" error is thrown early and
# intelligibly by this script, instead of cryptically when the user tries to (implicitly or explicitly) run the bash
# script. Note that other paths that need to be accessible can be set here manually or procedurally, too.
executables = {
    'exiftool': None,
    'exiftran': None,
    'luminance-hdr': None,
    'mogrify': None,
    'ffmpeg': None,
    'dcraw': None,
    'align_image_stack': None,
    'enfuse': None,
    'convert': None,
    'photo-processing': os.path.split(os.path.abspath(sys.argv[0]))[0],   # Well ... path to the folder containing the current script, actually. #FIXME: this will break if we move scripts around.
}


def executable_location(executable_name):
    """Return the known location for EXECUTABLE_NAME."""
    assert executable_name in executables, "ERROR: no known location for %s!\n\nIs the externals.py module properly set up?" % executable_name
    return executables[executable_name]


def populate_executables():
    """Populate the list of external executable programs."""
    for which_exec in executables:
        try:
            if executables[which_exec] is None:             # use POSIX `which` to locate the binary.
                executables[which_exec] = subprocess.check_output(['which', shlex.quote(which_exec)]).decode().strip()
        except BaseException as err:
            print("ERROR: unable to locate the program: %s." % which_exec)
            print("Please be sure it is installed and located in your system $PATH.")
            print("The system complained: %s" % err)
            sys.exit(1)


def startup():
    """Handle basic startup tasks: after making sure we're not running under Windows,
    populate the list of external programs. Doesn't do anything if the list is
    already initialized.
    * Assumes a terminal at least 80 chars wide.
    """
    if None in executables.values():
        if "windows" in platform.system().lower():
            print("ERROR: Patrick Mooney's photo-processing scripts do not run under Windows. With\nthe proper external programs and a little attention, though, they should run\nunder most Unix-like OSes.")
            sys.exit(1)
        populate_executables()


if __name__ == "__main__":
    startup()

    # If we haven't quit yet ...
    print("Successfully initialized program locations!")
