#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Maintains a list of mappings: "original file name" -> "current file name". Note
that there is no claim made to maintain intermediate names the file may have
had.

The intent is to make it possible to restore the original name of a file after
a series of filename changes. Doing this requires that all filename changes are
manually mapped through the routines in this module. I find this helpful in my
photo-postprocessing scripts, because I want to be able to restore the files'
original names if necessary.
"""


import csv, os


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
        ret += "(stored in %s) " % self.filename if self.filename else "(not tied to a file) "
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
        with open(filename, newline='') as infile:
            reader = csv.reader(infile)
            reader.__next__()                                                   # Skip the header row.
            for key, value in {rows[0]:rows[1] for rows in reader}.items():
                self.add_mapping(key, value)
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
    pass
