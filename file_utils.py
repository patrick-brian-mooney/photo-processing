#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A series of file-related utilities for my photo postprocessing scripts"""


import csv, datetime, glob, os, sys

import exifread                     # [sudo] pip[3] install exifread; or, https://pypi.python.org/pypi/ExifRead


raw_photo_extensions = ('CR2', 'cr2', 'DNG', 'dng', 'RAF', 'raf', 'DCR', 'dcr', 'NEF', 'nef')           # Extensions for raw photos.
jpeg_extensions = ('jpg', 'JPG', 'jpeg', 'JPEG', 'jpe', 'JPE')
json_extensions = ('json', 'JSON')
all_alternates = tuple(sorted(list(raw_photo_extensions + jpeg_extensions + json_extensions)))


def get_value_from_any_tag(filename, taglist):
    """Read the EXIF tags from the file in FILENAME, then return the value of the
    first tag in the file that is found from the desired tags specified in TAGLIST.
    """
    try:
        with open(filename, 'rb') as f:
            tags = exifread.process_file(f, details=False)
        for tag in taglist:
            try:
                return tags[tag]
            except KeyError:
                continue
    except BaseException:
        return None
    return None

def find_unique_name(suggested_name):
    """Given a SUGGESTED_NAME, return a version of that name that is unique in the
    directory in which it occurs, either by (a) just returning SUGGESTED_NAME if it
    is already unique, or (b) appending successively higher integers to the name
    until it becomes unique.
    """
    fname, f_ext = os.path.splitext(suggested_name)
    found, index = False, 1
    while not found:
        the_name = '%s_%d%s' % (fname, index, f_ext) if (index > 0) else suggested_name
        if os.path.exists(the_name):
            index += 1          # Bump the counter and try again
        else:
            found = True        # Signal we're done
    return the_name

def name_from_date(which_file):
    """Get a filename for a photo based on the date the photo was taken. Try several
    possible ways to get the date; if none works, just guess based on filename.
    """
    with open(which_file, 'rb') as f:
        tags = exifread.process_file(f, details=False)    # details=False means don't parse thumbs or other slow data we don't need.
        try:
            dt = tags['EXIF DateTimeOriginal'].values
        except KeyError:
            try:
                dt = tags['Image DateTime'].values
            except KeyError:            # Sigh. Not all of my image-generating devices generate EXIF info in all circumstances.
                dt = which_file         # At this point, just guess based on filename.
        dt = ''.join([char for char in dt if char.isdigit()])
        if len(dt) < 8:     # then we got filename gibberish, not a meaningful date.
            dt = ''.join([char for char in datetime.datetime.fromtimestamp(os.path.getmtime(which_file)).isoformat() if char.isdigit()])
        dt = dt.ljust(14)   # Even if it's just gibberish, make sure it's long enough gibberish
    return '%s-%s-%s_%s_%s_%s%s' % (dt[0:4], dt[4:6], dt[6:8], dt[8:10], dt[10:12], dt[12:14], os.path.splitext(which_file)[1].lower())

def find_alt_version(orig_name, alternate_extensions):
    """Check to see if there is an alternate version of this file (e.g., a raw file
    corresponding to a JPEG). This logic depends entirely on equivalent filenames
    with differing extensions. If so, return its name; otherwise, return None.

    ALTERNATE_EXTENSIONS is a list (or tuple) of other extensions to check for.
    This list (or tuple, or set, or ...) is checked in order, and the first file
    found with a matching extension is considered to be the match we're looking for,
    even if there are alternate versions. That is to say: there is no effort made to
    choose the "best" version, except insofar as the earliest extension listed is
    assumed to belong to the "best" file.
    """
    for whichext in alternate_extensions:
        altfile = os.path.splitext(orig_name)[0] + '.' + whichext
        if os.path.exists(altfile):
            return altfile
    return None                 # If we didn't find one ...

def list_of_raws():
    """Get a list of all raw files in the current directory."""
    all_raws = [][:]
    for which_ext in raw_photo_extensions:
        all_raws += glob.glob("*%s" % which_ext)
    return [f for f in sorted(list(set(all_raws)))]


"""The following class maintains a list of mappings:
    "original file name" -> "current file name".

Note that there is no claim made to maintain intermediate names the file may
have had. The intent is to make it possible to restore the original name of a
set of files after a series of filename changes. Doing this requires that all
filename changes are manually mapped through the routines in this class. I
find this helpful in my photo-postprocessing scripts, because I want to be able
to restore the files' original names if necessary.
"""

class FilenameMapper(object):
    """Maintains a mapping of old-to-new filenames."""
    def __init__(self, mapping=None, filename=None):
        """Set up the mapping names. MAPPING is a dict, in which
        mapping[oldname]=newname. FILENAME should be the path to a closed file
        in .csv format.
        """
        if mapping:
            self.mapping = mapping
        else:
            self.mapping = {}.copy()
        self.filename = filename

    def __repr__(self):
        """Return a printable representation."""
        ret = "< FilenameMapper object (mapping %d files) " % len(self.mapping)
        ret += "(stored in '%s') " % self.filename if self.filename else "(not tied to a file) "
        ret += ">"
        return ret

    def read_mappings(self, filename):
        """Read mapping dictionary back into memory. Do this before restoring
        original file names, or before doing other things that require a set of
        filename mappings to be in memory.

        The new mappings being read are ADDED TO the mappings; they UPDATE but
        do not REPLACE any existing set of mappings already in the object. The
        updating process acts as if the mappings in the file were the latest in a
        series of filename changes and attempts to deal with this by matching it
        back to the original name of the current name is currently registered as a
        new name.

        This procedure also registers FILENAME as the filename associated with the
        .csv file used to maintain the object's data.
        """
        try:
            with open(filename, newline='') as infile:
                reader = csv.reader(infile)
                reader.__next__()                                                   # Skip the header row.
                for key, value in {rows[0]:rows[1] for rows in reader}.items():
                    self.add_mapping(key, value)
        except FileNotFoundError:
            pass                    # Oh well, no mappings file found to read from.
        self.filename = filename

    def add_mapping(self, orig_name, new_name):
        """Maps ORIG_NAME to NEW_NAME, i.e. creates a note that NEW_NAME was once
        called ORIG_NAME. This procedure does not do the renaming itself, and does
        not write the changes to disk.
        """
        if orig_name in self.mapping.values():
            for i in self.mapping:                  # If that appears anywhere in the dict as a name resulting from a rename  ...
                if self.mapping[i] == orig_name:    # ... go through the dict, looking for things that point to it ...
                    self.mapping[i] = new_name      # ... and update the references to the new name.
        else:
            self.mapping[orig_name] = new_name

    def rename_and_map(self, orig_name, new_name):
        """Rename a file and keep track of the mapping from old to new names."""
        os.rename(orig_name, new_name)
        self.add_mapping(orig_name, new_name)

    def write_mappings(self):
        """Write the mapping to the .csv file that stores it."""
        with open(self.filename, 'w', newline='') as file_names:
            writer = csv.writer(file_names, dialect='unix')
            writer.writerow(['original name', 'new name'])
            writer.writerows(self.mapping.items())


if __name__ == "__main__":
    print("file_utils.py is not a program; it's a library of code to be used by other\nprograms. You can't usefully use it directly from the terminal.")
    sys.exit(1)
