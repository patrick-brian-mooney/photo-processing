#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A series of file-related utilities for my photo postprocessing scripts.

This program is part of Patrick Mooney's photo postprocessing scripts; the
complete set can be found at https://github.com/patrick-brian-mooney/photo-processing.
All programs in that collection are copyright 2015-2019 by Patrick Mooney; they
are free software released under the GNU GPL, either version 3 or (at your
option) any later version. See the file LICENSE.md for details.

The latest version of these scripts can always be found at
    https://github.com/patrick-brian-mooney/photo-processing
"""


import csv, datetime, glob, os, shlex, subprocess, sys

import exifread                     # [sudo] pip[3] install exifread; or, https://pypi.python.org/pypi/ExifRead

import photo_config


raw_photo_extensions = ('CR2', 'cr2', 'DNG', 'dng', 'RAF', 'raf', 'DCR', 'dcr', 'NEF', 'nef')
jpeg_extensions = ('jpg', 'JPG', 'jpeg', 'JPEG', 'jpe', 'JPE')
other_image_extensions = ('png', 'PNG')
json_extensions = ('json', 'JSON')
all_alternates = tuple(sorted(list(raw_photo_extensions + jpeg_extensions + json_extensions + other_image_extensions)))

movie_extensions = ('MOV', 'mov', 'MP4', 'mp4', 'AVI', 'avi',  'm4a', 'M4A', 'mkv', "MKV",)
audio_extensions = ('wav', 'WAV', 'FLAC', 'flac', 'mp3', 'MP3', )

darkframe_location = '/home/patrick/Photos/t7i_darkframe_for_dcraw.pgm'
measured_darkness_level = "2047.901764"     # pamsumm -mean on the previously specified image.


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


def movie_recorded_date(which_file):
    """Tries to parse FFmpeg output to get the date the movie was recorded.
    #FIXME: probably quite fragile.
    """
    result = subprocess.run([photo_config.executable_location("ffmpeg"), "-i", which_file], stdout=subprocess.PIPE, stderr=subprocess.PIPE)       # And we therefore require Python 3.5.
    output = result.stderr.decode().split('\n')     # FFmpeg returns result code 1 if no action specified. That's OK.
    try:
        time_line = [i for i in output if 'creation_time' in i][0]
        return ''.join([c for c in time_line.strip() if c.isdigit()])
    except IndexError:
        return ''.join([c for c in which_file if c.isdigit()])


Apple_day_names = ('jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec')
def parse_Apple_day(day_string):
    """Takes an "Apple day", a string of the form 'Jun 26', and parses it into a
    tuple: (numeric month, numeric day). Probably quite fragile. This is the
    filename format for photos coming off of my iPhone. If this function cannot
    parse the DAY_STRING string in the proper format, it returns None.

    This is probably rather fragile, but happens to work for me right now.
    """
    for month_num, month_name in enumerate(Apple_day_names):
        if month_name in day_string:
            try:
                return (1 + month_num, int(day_string[len(month_name) + day_string.index(month_name):].strip()))
            except (ValueError, IndexError):
                pass
    return None


def parse_Apple_filename(which_file):
    """Parses "Apple filenames," as defined above, attempting to pick dates and times
    out of strings with the format 'Photo Jun 26, 6 06 59 PM.jpg'. Returns a
    numeric date string, like other date-detecting routines in here.
    """
    if 'photo' not in which_file.lower():           # Then it's not an Apple date
        return None

    # First massage, then split into date and time.
    ret = which_file.lower().strip().lstrip('photo').strip()
    ret = os.path.splitext(ret)[0]
    day_string, time_string = ret.split(',')
    day_string, time_string = day_string.strip(), time_string.strip()
    try:
        month_num, day_num = parse_Apple_day(day_string)
    except TypeError:       # Can't expand the tuple? parse_Apple_day didn't work. This is probably not an Apple date.
        return None

    # OK, figure out what time the photo was taken, if possible.
    stripped_time = ''.join([c for c in time_string if (c.isspace() or c.isdigit())])
    hours, minutes, *seconds = stripped_time.split(' ')
    if isinstance(seconds, (list, tuple)):  # If we wound up with a tuple instead of a string, rectify that.
        seconds = seconds[0]
    if 'am' in seconds:                                 # Drop any parenthetical sequence we may have picked up.
        seconds = seconds[:seconds.index('am')]
    elif 'pm' in seconds:
        seconds = seconds[:seconds.index('pm')]
    hours, minutes, seconds = int(hours), int(minutes), int(seconds)
    if (('pm' in time_string.lower()) and (hours < 13)):
        hours += 12

    # Annoyingly, Apple dates don't have a year. Guess what it is, assuming the system date is correct,
    # the photo date is correct, and the photo is less than a year old.
    current_year = datetime.datetime.now().year
    projected_date = datetime.datetime(year=current_year, month=month_num, day=day_num, hour=hours, minute=minutes, second=seconds)
    if projected_date > datetime.datetime.now():
        projected_date = datetime.datetime(year=current_year-1, month=month_num, day=day_num, hour=hours, minute=minutes, second=seconds)

    return str(projected_date)


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
            if os.path.splitext(which_file)[1].strip().strip('.').strip() in (movie_extensions + audio_extensions):
                dt = movie_recorded_date(which_file)
            else:
                dt = parse_Apple_filename(which_file)
                if not dt:
                    try:            # As a nearly-last-ditch resort, try getting the file-modified time.
                        dt = str(datetime.fromtimestamp(os.path.getmtime(which_file)))
                    except BaseException:
                        dt = which_file         # At this point, give up and guess based on filename.
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


"""
The following class maintains a list of mappings:
    "original file name" -> "current file name".

Note that there is no claim made to maintain intermediate names the file may
have had. The intent is to make it possible to restore the original name of a
set of files after a series of filename changes. Doing this requires that all
filename changes are manually mapped through the routines in this class. I
find this helpful in my photo-postprocessing scripts because I want to be able
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
        ret += "(stored in %s) " % shlex.quote(self.filename) if self.filename else "(not tied to a file) "
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
