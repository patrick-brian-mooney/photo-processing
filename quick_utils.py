#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A GUI providing access to functions in the postprocess_photos script. I
primarily use it to make changes to photos from a GUI viewer with a limited
number of "external programs" easily accessible from a menu.

This program is part of photo-processing, a collection of scripts. It is
copyright 2017 by Patrick Mooney, and is licensed under the GPL, either version
3 or (at your option) any later version. See the file LICENSE.md for more
details.

The latest version of these scripts can always be found at
    https://github.com/patrick-brian-mooney/photo-processing
"""


import os, subprocess, sys
from tkinter import *

import postprocess_photos as pp
import file_mappings as f_m
import create_HDR_script as c_H_s
import HDR_from_raw as H_f_r

import patrick_logger               # https://github.com/patrick-brian-mooney/python-personal-library/blob/master/patrick_logger.py
from patrick_logger import log_it


patrick_logger.verbosity_level = 5

root = Tk()                         # Top-level TKinter object


def increment_and_rename(file_list):
    """Bump up the timestamp for each file in FILE_LIST, then rename it based on the
    new timestamp.
    """
    # root.withdraw()
    assert isinstance(file_list, (list, tuple))
    assert len(file_list) >= 1, "ERROR: you must specify at least one file to increment_and_rename()"
    log_it("INFO: increment_and_rename() called for %d files" % len(file_list), 2)
    mappings = f_m.FilenameMapper()
    mappings.read_mappings('file_list.csv')
    for f in file_list:
        log_it("INFO: incrementing timestamp on '%s' and renaming" % f, 3)
        pp._increment_timestamp([f])
        new_name = pp.find_unique_name(pp.name_from_date(f))
        mappings.rename_and_map(f, new_name)
    mappings.write_mappings()
    sys.exit()

def decrement_and_rename(file_list):
    """Bump the timestamp down for each file in FILE_LIST, then rename it based on
    the new timestamp. Assumes that all of the files in FILE_LIST are in the same
    directory, and assumes that they have a file_names.csv file containing the set
    of filename mappings.
    """
    # root.withdraw()
    assert isinstance(file_list, (list, tuple))
    assert len(file_list) >= 1, "ERROR: you must specify at least one file to decrement_and_rename()"
    log_it("INFO: decrement_and_rename() called for %d files" % len(file_list), 2)
    log_it("INFO: current directory is %s" % os.getcwd(), 3)
    log_it("INFO: those files are: %s" % file_list, (4 if len(file_list) > 4 else 2))
    try:
        olddir = os.getcwd()
        files_dir = os.path.dirname(file_list[0])
        if files_dir:
            os.chdir(files_dir)
        mappings = f_m.FilenameMapper()
        mappings.read_mappings('file_names.csv')
        log_it("INFO: file name mappings read: %s" % mappings, 2)
        for f in file_list:
            log_it("INFO: decrementing timestamp on '%s' and renaming" % f, 3)
            pp._decrement_timestamp([f])
            new_name = pp.find_unique_name(pp.name_from_date(f))
            mappings.rename_and_map(f, new_name)
        mappings.write_mappings()
    finally:
        os.chdir(olddir)
    sys.exit()

def delete_with_any_alternates(file_list):
    """Delete the file, with any alternate or paratextual associated files."""
    # root.withdraw()
    assert isinstance(file_list, (list, tuple))
    assert len(file_list) >= 1, "ERROR: you must specify at least one file to delete_with_any_alternates()"
    log_it("INFO: deleting files and their alternates for %d files" % len(file_list), 2)
    for f in file_list:
        log_it("INFO: deleting %s and all linked files" % f, 3)
        for ext in sorted(list(pp.all_alternates)):
            if os.path.exists('%s.%s' % (os.path.splitext(f)[0], ext)):
                os.unlink('%s.%s' % (os.path.splitext(f)[0], ext))
        os.unlink(f)
    sys.exit()

def tonemap_raws(file_list):
    """Create automated tonemaps from the specified raw files."""
    # root.withdraw()
    assert isinstance(file_list, (list, tuple))
    assert len(file_list) >= 1, "ERROR: you must specify at least one file to tonemap_raws()"
    log_it("INFO: creating %d tonemaps from raw files" % len(file_list), 2)
    for f in file_list:
        log_it("INFO: trying to tonemap %s" % f, 3)
        raw_file = pp.find_alt_version(f, pp.raw_photo_extensions)
        if raw_file:
            log_it("INFO: identified raw photo: %s" % raw_file, 3)
            H_f_r.HDR_tonemap_from_raw(raw_file)
    sys.exit()

def produce_raw_scripts(file_list):
    """Produce scripts that will tonemap the raw files, along with the necessary
    files that the script will depend on (e.g., the intermediate renderings at
    various Ev values).

    This function does not, itself, run the scripts.
    """
    # root.withdraw()
    assert isinstance(file_list, (list, tuple))
    assert len(file_list) >= 1, "ERROR: you must specify at least one file to produce_raw_scripts()"
    log_it("INFO: creating %d tonemaps from raw files" % len(file_list), 2)
    for f in file_list:
        log_it("INFO: trying to tonemap %s" % f, 3)
        raw_file = pp.find_alt_version(f, pp.raw_photo_extensions)
        if raw_file:
            log_it("INFO: identified raw photo: %s" % raw_file, 3)
            _ = H_f_r.create_HDR_script(raw_file)
    sys.exit()

def script_from_files(file_list):
    """Create an HDR script from selected files. This function is just a
    convenience wrapper for an external function.
    """
    # root.withdraw()
    assert isinstance(file_list, (list, tuple))
    assert len(file_list) > 1, "ERROR: you must specify at least two files to script_from_files()"
    c_H_s.create_script_from_file_list(file_list)
    sys.exit()

def open_in_luminance(file_list):
    """Create an HDR script from selected files. This function is just a
    convenience wrapper for an external function.
    """
    # root.withdraw()
    assert isinstance(file_list, (list, tuple))
    assert len(file_list) >= 1, "ERROR: you must specify at least one file to open in Luminance"
    raws = [pp.find_alt_version(x, pp.raw_photo_extensions) for x in file_list]
    subprocess.call('luminance-hdr %s' % ' '.join(raws), shell=True)
    sys.exit()

def exif_rotate(file_list, orientation):
    """Rotate eachJPEG file in FILE_LIST to the specified ORIENTATION. ORIENTATION
    is a string constant that constitutes a command-line flag to the exiftran
    program.
    """
    assert isinstance(file_list, (list, tuple))
    assert len(file_list) >= 1, "ERROR: you must specify at least one file to exif_rotate()"
    subprocess.call('exiftran -%sig %s' % (orientation, ' '.join(file_list)), shell=True)
    sys.exit()

def regen_thumb(file_list):
    """Regenerate the thumbnail image for a JPEG file."""
    assert isinstance(file_list, (list, tuple))
    assert len(file_list) >= 1, "ERROR: you must specify at least one file to regen_thumb()"
    subprocess.call('exiftran -ig %s' % ' '.join(file_list), shell=True)
    sys.exit()

if __name__ == "__main__":
    file_list = sys.argv[1:]
    log_it("OK, we're starting, and operating on %d files" % len(file_list), 2)
    assert len(file_list) > 0, "ERROR: You must specify at least one file on which to operate."

    base_path = os.path.split(file_list[0])[0]
    if base_path:
        os.chdir(base_path)
    for i in file_list:
        assert base_path == os.path.split(i)[0], "ERROR: file_list has files in different directories."
    file_list = [os.path.basename(x) for x in file_list]

    label = Label(root, text='\nWhat would you like to do with these %d files?\n\n' % len(file_list))
    label.pack(side=TOP, fill=X)
    button = Button(root, text="Add 1 hour to timestamp(s) and rename", command=lambda: increment_and_rename(file_list))
    button.pack(side=TOP, fill=X)
    button = Button(root, text="Subtract 1 hour from timestamp(s) and rename", command=lambda: decrement_and_rename(file_list))
    button.pack(side=TOP, fill=X)
    button = Button(root, text="Delete, and delete all alternate files", command=lambda: delete_with_any_alternates(file_list))
    button.pack(side=TOP, fill=X)

    label = Label(root, text='\n\nEXIF-aware JPEG transformations')
    label.pack(side=TOP, fill=X)
    button = Button(root, text="Rotate automatically", command=lambda: exif_rotate(file_list, "a"))
    button.pack(side=TOP, fill=X)
    button = Button(root, text="Rotate clockwise", command=lambda: exif_rotate(file_list, "9"))
    button.pack(side=TOP, fill=X)
    button = Button(root, text="Rotate counterclockwise", command=lambda: exif_rotate(file_list, "2"))
    button.pack(side=TOP, fill=X)
    button = Button(root, text="Rotate 180 degrees", command=lambda: exif_rotate(file_list, "1"))
    button.pack(side=TOP, fill=X)
    button = Button(root, text="Regenerate JPEG thumbnail", command=lambda: open_in_luminance(file_list))
    button.pack(side=TOP, fill=X)

    label = Label(root, text='\n\nHDR Scripting')
    label.pack(side=TOP, fill=X)
    button = Button(root, text="Create HDR script for all selected files", command=lambda: script_from_files(file_list))
    button.pack(side=TOP, fill=X)
    button = Button(root, text="HDR tonemapping script from corresponding raw", command=lambda: produce_raw_scripts(file_list))
    button.pack(side=TOP, fill=X)
    button = Button(root, text="HDR tonemap from corresponding raw", command=lambda: tonemap_raws(file_list))
    button.pack(side=TOP, fill=X)
    button = Button(root, text="Open corresponding raw in Luminance", command=lambda: open_in_luminance(file_list))
    button.pack(side=TOP, fill=X)

    root.mainloop()
