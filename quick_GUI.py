#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A GUI providing access to functions in the postprocess_photos script, plus
access to several external utilities. I primarily use it to make quick changes
to photos from a GUI viewer with a limited number of "external programs" easily
accessible from a menu.

This program is part of Patrick Mooney's photo postprocessing scripts; the
complete set can be found at https://github.com/patrick-brian-mooney/photo-processing.
All programs in that collection are copyright 2015-2019 by Patrick Mooney; they
are free software released under the GNU GPL, either version 3 or (at your
option) any later version. See the file LICENSE.md for details.

The latest version of these scripts can always be found at
    https://github.com/patrick-brian-mooney/photo-processing
"""


import os, subprocess, sys
from tkinter import *

import patrick_logger               # https://github.com/patrick-brian-mooney/python-personal-library/blob/master/patrick_logger.py
from patrick_logger import log_it

import postprocess_photos as pp
import file_utils as fu
import create_HDR_script as cHs
import HDR_from_raw as Hfr
import create_panorama_script as cps

import config

config.startup()                        # Check that the system meets minimum requirements; find necessary executables


patrick_logger.verbosity_level = 5

root = Tk()                         # Top-level TKinter object
root.title('Image Processing Options')


class NonIdioticStringVar(StringVar):
    """Let's make these easily displayable for debugging, shall we?"""
    def __repr__(self):
        return "'%s'" % self.get()

    def __str__(self):
        return self.get()


date_fields = ('YYYY', 'MO', 'DD', 'HH', 'MM', 'SS')


class DateTimeAdjustDialog(Frame):
    """Get a date/time combo from the user. Used in EXIF data-related situations."""

    def ret_func(self):
        """Called when OK is pushed."""
        d = { f: self.new_date[f].get() for f in date_fields }
        self.callback(int(d['YYYY']), int(d['MO']), int(d["DD"]), int(d['HH']), int(d['MM']), int(d['SS']))
        self.master.destroy()

    def cancel_func(self):
        """Destroy the window without doing anything else."""
        self.master.destroy()

    def __init__(self, master=None, callback=None):
        """We pack bottom-up here so that subclasses can easily add to the top of the
        frame, should they so desire.
        """
        assert callback is not None
        self.new_date = {}
        self.callback = callback
        Frame.__init__(self, master)
        self.pack()
        row = Frame(master)
        Button(row, text="OK", command=self.ret_func).pack(side=RIGHT, expand=YES, fill=X)
        Button(row, text="Cancel", command=self.cancel_func).pack(side=LEFT, expand=YES, fill=X)
        row.pack(side=BOTTOM)
        Label(master, text="WARNING: all values must be numeric. No validation is performed!").pack(side=BOTTOM, expand=YES, fill=X)
        for field in date_fields:
            row = Frame(master)
            lab = Label(row, width=5, text=field)
            ent = Entry(row)
            ent.insert(0, "0")
            self.new_date[field] = ent
            row.pack(side=TOP, fill=X)
            lab.pack(side=LEFT)
            ent.pack(side=RIGHT, expand=YES, fill=X)


class DateTimeSetDialog(DateTimeAdjustDialog):
    pass


def adjust_timestamp(file_list, rename=True):
    """Pop up a dialog that asks the user by how much to adjust an EXIF timestamp. If
    RENAME is True (the default), the files are renamed based on their new
    timestamps after the timestamps are adjusted.
    """
    #FIXME: we need a text label at the top telling the user what to do.
    dialog = Toplevel()
    DateTimeAdjustDialog(master=dialog, callback=lambda yr, mo, days, hr, m, s: pp.adjust_timestamps(file_list, yr, mo, days, hr, m, s, rename=rename)).pack()
    dialog.grab_set()
    dialog.focus_set()
    dialog.wait_window()
    sys.exit()


def set_timestamp(file_list):
    """Pop up a dialog that asks the user what the EXIF timestamp should be."""
    #FIXME: we need a text label at the top telling the user what to do.
    dialog = Toplevel()
    DateTimeSetDialog(master=dialog, callback=lambda yr, mo, days, hr, m, s: pp.set_timestamps(file_list, yr, mo, days, hr, m, s)).pack()
    dialog.grab_set()
    dialog.focus_set()
    dialog.wait_window()
    sys.exit()


def increment_and_rename(file_list):
    """Bump up the timestamp for each file in FILE_LIST by one hour, then rename
    each file based on the new timestamp.
    """
    # root.withdraw()
    assert isinstance(file_list, (list, tuple))
    assert len(file_list) >= 1, "ERROR: you must specify at least one file to increment_and_rename()"
    log_it("INFO: increment_and_rename() called for %d files" % len(file_list), 2)
    mappings = fu.FilenameMapper()
    mappings.read_mappings('file_names.csv')
    for f in file_list:
        log_it("INFO: incrementing timestamp on '%s' and renaming" % f, 3)
        pp._increment_timestamp([f])
        new_name = fu.find_unique_name(fu.name_from_date(f))
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
        mappings = fu.FilenameMapper()
        mappings.read_mappings('file_names.csv')
        log_it("INFO: file name mappings read: %s" % mappings, 2)
        for f in file_list:
            log_it("INFO: decrementing timestamp on '%s' and renaming" % f, 3)
            pp._decrement_timestamp([f])
            new_name = fu.find_unique_name(fu.name_from_date(f))
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
        for ext in sorted(list(fu.all_alternates)):
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
        raw_file = fu.find_alt_version(f, fu.raw_photo_extensions)
        if raw_file:
            log_it("INFO: identified raw photo: %s" % raw_file, 3)
            Hfr.HDR_tonemap_from_raw(raw_file)
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
        raw_file = fu.find_alt_version(f, fu.raw_photo_extensions)
        if raw_file:
            log_it("INFO: identified raw photo: %s" % raw_file, 3)
            _ = Hfr.create_HDR_script(raw_file)
    sys.exit()


def script_from_files(file_list):
    """Create an HDR script from selected files. This function is just a
    convenience wrapper for an external function.
    """
    # root.withdraw()
    assert isinstance(file_list, (list, tuple))
    assert len(file_list) > 1, "ERROR: you must specify at least two files to script_from_files()"
    cHs.create_script_from_file_list(file_list)
    sys.exit()


def open_in_luminance(file_list):
    """Create an HDR script from selected files. This function is just a
    convenience wrapper for an external function.
    """
    # root.withdraw()
    assert isinstance(file_list, (list, tuple))
    assert len(file_list) >= 1, "ERROR: you must specify at least one file to open in Luminance"
    raws = [fu.find_alt_version(x, fu.raw_photo_extensions) for x in file_list]
    subprocess.call([config.executable_location('luminance-hdr')] + raws)
    sys.exit()


def create_panorama_script(file_list):
    """Creates a default panorama-creation script from the selected files."""
    assert isinstance(file_list, (list, tuple))
    assert len(file_list) >= 2, "ERROR: you must specify at least two files from which to create a panorama"
    cps.produce_script(file_list)
    sys.exit()


def exif_rotate(file_list, orientation):
    """Rotate each JPEG file in FILE_LIST to the specified ORIENTATION. ORIENTATION
    is a string constant that constitutes a command-line flag to the exiftran
    program.
    """
    assert isinstance(file_list, (list, tuple))
    assert len(file_list) >= 1, "ERROR: you must specify at least one file to exif_rotate()"
    subprocess.call([config.executable_location('exiftran'), '-%sig' % orientation] + file_list)
    sys.exit()


def regen_thumb(file_list):
    """Regenerate the thumbnail image for a JPEG file."""
    assert isinstance(file_list, (list, tuple))
    assert len(file_list) >= 1, "ERROR: you must specify at least one file to regen_thumb()"
    subprocess.call([config.executable_location('exiftran'), '-ig' ] + file_list)
    sys.exit()


def resize_files(file_list, longest_side):
    """Proportionally resize each file in FILE_LIST so that its longest side is the
    length specified by LONGEST_SIDE.    """
    assert isinstance(file_list, (list, tuple))
    assert len(file_list) >= 1, "ERROR: you must specify at least one file to resize_files()"
    for f in file_list:
        subprocess.call([config.executable_location('mogrify'), '-resize', '%dx%d' % (longest_side, longest_side)] + [f])
    sys.exit()


force_debug = True

if __name__ == "__main__":
    if force_debug:
        import glob
        sys.argv[1:] = glob.glob('/home/patrick/Photos/film/by roll number/1122/*.JPG') + glob.glob('/home/patrick/Photos/film/by roll number/1122/*.jpg')
    file_list = sys.argv[1:]
    log_it("OK, we're starting, and operating on %d files" % len(file_list), 2)
    assert len(file_list) > 0, "ERROR: You must specify at least one file on which to operate."

    base_path = os.path.split(file_list[0])[0]
    if base_path:
        os.chdir(base_path)
    for i in file_list:
        assert os.path.samefile(base_path, os.path.split(i)[0]), "ERROR: file_list has files in different directories."
    file_list = [os.path.basename(x) for x in file_list]

    Label(root, text='\nWhat would you like to do with these %d files?\n\n' % len(file_list)).pack(side=TOP, fill=X)

    Button(root, text="Adjust timestamp(s) and rename", command=lambda: adjust_timestamp(file_list)).pack(side=TOP, fill=X)
    Button(root, text="Adjust timestamp(s) without renaming", command=lambda: adjust_timestamp(file_list, rename=False)).pack(side=TOP, fill=X)
    Button(root, text="Assign timestamp(s) without renaming", command=lambda: set_timestamp(file_list)).pack(side=TOP, fill=X)
    Button(root, text="Add 1 hour to timestamp(s) and rename", command=lambda: increment_and_rename(file_list)).pack(side=TOP, fill=X)
    Button(root, text="Subtract 1 hour from timestamp(s) and rename", command=lambda: decrement_and_rename(file_list)).pack(side=TOP, fill=X)
    Button(root, text="Delete, and delete all sidecars", command=lambda: delete_with_any_alternates(file_list)).pack(side=TOP, fill=X)

    Label(root, text='\n\nResize').pack(side=TOP, fill=X)
    Button(root, text="Resize to 720p", command=lambda: resize_files(file_list, 720)).pack(side=TOP, fill=X)
    Button(root, text="Resize to 1920p", command=lambda: resize_files(file_list, 1920)).pack(side=TOP, fill=X)
    Label(root, text='\n\nEXIF-aware JPEG transformations').pack(side=TOP, fill=X)
    Button(root, text="Rotate automatically", command=lambda: exif_rotate(file_list, "a")).pack(side=TOP, fill=X)
    Button(root, text="Rotate clockwise", command=lambda: exif_rotate(file_list, "9")).pack(side=TOP, fill=X)
    Button(root, text="Rotate counterclockwise", command=lambda: exif_rotate(file_list, "2")).pack(side=TOP, fill=X)
    Button(root, text="Rotate 180 degrees", command=lambda: exif_rotate(file_list, "1")).pack(side=TOP, fill=X)
    Button(root, text="Regenerate JPEG thumbnail", command=lambda: regen_thumb(file_list)).pack(side=TOP, fill=X)

    Label(root, text='\n\nHDR and Panorama Processing').pack(side=TOP, fill=X)
    Button(root, text="Create HDR script for all selected files", command=lambda: script_from_files(file_list)).pack(side=TOP, fill=X)
    Button(root, text="Create HDR tonemap script(s) from corresponding raw(s)", command=lambda: produce_raw_scripts(file_list)).pack(side=TOP, fill=X)
    Button(root, text="HDR tonemap(s) from (corresponding) raw(s)", command=lambda: tonemap_raws(file_list)).pack(side=TOP, fill=X)
    Button(root, text="Open (corresponding) raw(s) in Luminance", command=lambda: open_in_luminance(file_list)).pack(side=TOP, fill=X)
    Button(root, text="Panorama script from all selected files", command=lambda: create_panorama_script(file_list)).pack(side=TOP, fill=X)

    root.mainloop()

else:
    root.withdraw()
