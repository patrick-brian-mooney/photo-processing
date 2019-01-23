#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A series of declarations about external programs, used by other scripts in the
photo processing collection.

This program comes with ABSOLUTELY NO WARRANTY. Use at your own risk.

This program is part of Patrick Mooney's photo postprocessing scripts; the
complete set can be found at https://github.com/patrick-brian-mooney/photo-processing.
All programs in that collection are copyright 2015-2018 by Patrick Mooney; they
are free software released under the GNU GPL, either version 3 or (at your
option) any later version. See the file LICENSE.md for details.
"""


import platform, shlex, subprocess, sys


# The list of executable programs and their locations. Anything whose value is set to None will be searched for in
# the user's $PATH. If the executable is not in the $PATH, set it here.
executables = {
    'exiftool': None,
    'exiftran': None,
    'luminance-hdr': None,
    'mogrify': None,
    'ffmpeg': None,
}


def executable_location(executable_name):
    """Return the known location for EXECUTABLE_NAME."""
    assert executable_name, "ERROR: no known location for %s!\n\nIs the externals.py module properly set up?" % executable_name
    return executables(executable_name)

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
    populate the list of external programs.
    """
    if "windows" in platform.system().lower():
        print("ERROR: Patrick Mooney's photo-processing scripts do not currently run under Windows.")
        sys.exit(1)
    populate_executables()


if __name__ == "__main__":
    startup()

    # If we haven't quit yet ...
    print("Successfully initialized program locations!")
