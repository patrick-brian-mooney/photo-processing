#!/home/patrick/Documents/programming/python_projects/photo-processing/bin/python3
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


import csv
import datetime
import os
import shlex
import subprocess
import sys
import warnings

from pathlib import Path
from typing import Iterable, Mapping, Optional, Sequence, Tuple, Type, Union


import exifread                     # [sudo] pip[3] install exifread; or, https://pypi.python.org/pypi/ExifRead

import photo_config                 # https://github.com/patrick-brian-mooney/photo-processing


raw_photo_extensions = { '.cr2', 'dng', '.raf', '.dcr', '.nef' }
jpeg_extensions = { '.jpg', '.jpeg', '.jpe' }
other_image_extensions = { '.png', '.webp' }
json_extensions = { '.json', }
all_alternates = raw_photo_extensions | jpeg_extensions | json_extensions | other_image_extensions

movie_extensions = { '.mov', '.mp4', '.avi', '.mkv', '.3gp' }
audio_extensions = { '.wav', '.m4a', '.flac', '.mp3' }

darkframe_location = '/home/patrick/Photos/t7i_darkframe_for_dcraw.pgm'
measured_darkness_level = "2047.901764"     # pamsumm -mean on the previously specified image.


def get_value_from_any_tag(filename: Path,
                           taglist: Iterable[str]) -> Union[str, None]:
    """Read the EXIF tags from the file in FILENAME, then return the value of the
    first tag in the file that is found from the desired tags specified in TAGLIST.
    """
    assert isinstance(filename, Path)
    assert isinstance(taglist, Iterable), "ERROR! taglist must be an iterable container!"
    assert all([isinstance(str, f) for f in taglist]), "ERROR! taglist must contain tags represented as strings!"

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


def find_unique_name(suggested_name: Path) -> Path:
    """Given a SUGGESTED_NAME, return a version of that name that is unique in the
    directory in which it occurs, either by (a) just returning SUGGESTED_NAME if it
    is already unique, or (b) appending successively higher integers to the name
    until it becomes unique.
    """
    assert isinstance(suggested_name, Path)

    f_name, f_ext = suggested_name.stem, suggested_name.suffix

    found, index, the_name = False, 1, Path(str(suggested_name).strip())
    while not found:
        if index > 0:
            the_name = Path(f'{f_name}_{index}{f_ext}'.strip())
        if the_name.exists():
            index += 1          # Bump the counter and try again
        else:
            found = True        # Signal we're done

    return the_name


def movie_recorded_date(which_file: Path) -> str:
    """Tries to parse FFmpeg output to get the date the movie was recorded.
    #FIXME: probably quite fragile.
    """
    assert isinstance(which_file, Path), "ERROR! files passed to movie_recorded_date must be Paths!"
    result = subprocess.run([photo_config.executable_location("ffmpeg"), "-i", str(which_file)],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)     # And we therefore require Python 3.5.
    output = result.stderr.decode().split('\n')     # FFmpeg returns result code 1 if no action specified. That's OK.

    try:
        time_line = [i for i in output if 'creation_time' in i][0]
        return ''.join([c for c in time_line.strip() if c.isdigit()])

    except IndexError:
        return ''.join([c for c in which_file.name if c.isdigit()])


Apple_month_names = ('jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec')


def parse_apple_day(day_string: str) -> Union[None, Tuple[int, int]]:
    """Takes an "Apple day", a string of the form 'Jun 26', and parses it into a
    tuple: (numeric month, numeric day). This is the filename format for photos
    coming from my iPhone. If this function cannot parse the DAY_STRING string in
    the proper format, it returns None.

    This is probably rather fragile, but happens to work for me right now.
    """
    for month_num, month_name in enumerate(Apple_month_names):
        if month_name in day_string:
            try:
                return 1 + month_num, int(day_string[len(month_name) + day_string.index(month_name):].strip())
            except (ValueError, IndexError):
                pass

    return None


def parse_apple_filename(which_file: Path) -> Union[str, None]:
    """Parses "Apple filenames," as defined above, attempting to pick dates and times
    out of strings with the format 'Photo Jun 26, 6 06 59 PM.jpg'. Returns a
    numeric date string, like other date-detecting routines in here.
    """
    assert isinstance(which_file, Path), "ERROR! files passed to parse_apple_filename must be Paths!"
    if 'photo' not in str(which_file).casefold():           # Then it's not an Apple date
        return None

    # First massage, then split into date and time.
    photo_loc = str(which_file).casefold().find('photo') + len('photo')
    ret = str(which_file).casefold()[photo_loc:].strip()
    ret = Path(ret).stem

    try:
        day_string, time_string = ret.split(',')
        day_string, time_string = day_string.strip(), time_string.strip()
    except ValueError:      # Can't split into day string and time string? Probably not an Apple date after all.
        return None

    try:
        month_num, day_num = parse_apple_day(day_string)
    except TypeError:       # Can't expand the tuple? parse_apple_day didn't work. This is probably not an Apple date.
        return None

    # OK, figure out what time the photo was taken, if possible.
    stripped_time = ''.join([c for c in time_string if (c.isspace() or c.isdigit())])
    hours, minutes, *seconds = stripped_time.split(' ')

    if isinstance(seconds, (list, tuple)):  # If seconds winds up being a tuple instead of a string, fix it.
        seconds = seconds[0]
    if 'am' in seconds:                                 # Drop any parenthetical sequence we may have picked up.
        seconds = seconds[:seconds.index('am')]
    elif 'pm' in seconds:
        seconds = seconds[:seconds.index('pm')]

    hours, minutes, seconds = int(hours), int(minutes), int(seconds)
    if ('pm' in time_string.casefold()) and (hours < 13):
        hours += 12

    # Annoyingly, Apple dates don't have a year. Guess what it is, assuming the system date is correct,
    # the photo date is correct, and the photo is less than a year old.
    current_year = datetime.datetime.now().year
    projected_date = datetime.datetime(year=current_year, month=month_num, day=day_num,
                                       hour=hours, minute=minutes, second=seconds)
    if projected_date > datetime.datetime.now():
        projected_date = datetime.datetime(year=current_year-1, month=month_num, day=day_num,
                                           hour=hours, minute=minutes, second=seconds)

    return str(projected_date)


def name_from_date(which_file: Path) -> Path:
    """Get a new filename for a photo based on the date the photo was taken. Try
    several possible ways to get the date; if none works, just guess based on
    the photo's current filename.
    """
    assert isinstance(which_file, Path)      # FIXME! We should be taking and returning Paths!
    dt: Optional[str] = None

    try:
        try:
            with open(which_file, 'rb') as f:
                tags = exifread.process_file(f, details=False)  # don't parse thumbs or other slow data we don't need.
        except AttributeError as errrr:     # guard against some unprocessable HEIF files returning None
            raise KeyError from errrr           # just move along if process_file bombs on an intermediate None
        dt = tags['EXIF DateTimeOriginal'].values
    except KeyError:
        pass

    if not dt:
        try:
            dt = tags['Image DateTime'].values
        except (KeyError, UnboundLocalError):       # Sigh. Not all image-making devices always generate EXIF info.
            if which_file.suffix in (movie_extensions | audio_extensions):
                dt = movie_recorded_date(which_file)
            else:
                dt = parse_apple_filename(which_file)

                if not dt:
                    try:            # As a nearly-last-ditch resort, try getting the file-modified time.
                        dt = str(datetime.datetime.fromtimestamp(os.path.getmtime(which_file)))
                    except BaseException:
                        dt = str(which_file)        # At this point, give up and guess based on filename.

    dt = ''.join([char for char in dt if char.isdigit()])
    if len(dt) < 8:     # then we got filename gibberish, not a meaningful date.
        dt = datetime.datetime.fromtimestamp(os.path.getmtime(which_file)).isoformat()
        dt = ''.join([char for char in dt if char.isdigit()])

    dt = dt.ljust(14)   # Even if it's just gibberish, make sure it's long enough gibberish
    return Path(f'{dt[0:4]}-{dt[4:6]}-{dt[6:8]}_{dt[8:10]}_{dt[10:12]}_{dt[12:14]}{which_file.suffix.lower()}')


def find_alt_version(orig_name: Path,
                     alternate_extensions: Iterable[str]) -> Union[Path, None]:
    """Check to see if there is an alternate version of this file (e.g., a raw file
    corresponding to a JPEG). If so, return it. This function depends entirely on
    "alternate versions" having identical filenames except for differing extensions.

    If an "alternate version" exists, return its name; otherwise, return None. If
    multiple "alternate versions" occur based on the list of ALTERNATE_EXTENSIONS
    (say, if there are multiple versions with extensions identicaly except for
    case, on case-insensitive systems), return the one that occurs earliest in a
    lexicographic sort of otherwise-identical options.

    ALTERNATE_EXTENSIONS is a sequence of other extensions to check for. This list
    is checked in order, and the first file found with a matching extension is
    considered to be the match we're looking for, even if there are more alternate
    versions. That is to say: there is no effort made to choose the "best" version,
    except insofar as the earliest extension listed is assumed to belong to the
    "best" file.
    """
    assert isinstance(orig_name, Path), "ERROR! Files passed to find_alt_version must be Paths!"

    for ext in alternate_extensions:
        alt_files = [f for f in Path().glob(orig_name.stem + '.*') if f.suffix.casefold() in alternate_extensions]
        if alt_files:
            return sorted(alt_files)[0]

    return None                 # If we didn't find one ...


def list_of_raws() -> Sequence[Path]:
    """Get a list of all raw files in the current directory.
    """
    return sorted({f for f in Path().glob('*') if f.suffix.casefold() in raw_photo_extensions})


class FilenameMapper(object):   # FIXME: We should make this indexable like a standard dictionary.
    """
    Maintains a list of old-filename-to-new-filename mappings:
        "original file name" -> "current file name".

    Note that there is no claim made to maintain intermediate names the file may
    have had. The intent is to make it possible to restore the original name of a
    set of files after a series of filename changes. Doing this requires that all
    filename changes are manually mapped through the routines in this class. I
    find this helpful in my photo-postprocessing scripts because I want to be able
    to restore the files' original names if necessary.
    """
    def __init__(self, mapping: Optional[Type[Mapping]] = None,
                 map_file: Optional[Path] = None):           # FIXME! use Path
        """Set up the mapping names. MAPPING maps oldname -> newname.

        FILENAME should be the path to a closed file in .csv format. It is not
        read, even if it already exists; it simply becomes the name of the file
        that WILL BE used to store the mapping data.
        """
        if map_file:
            assert isinstance(map_file, Path)   # FIXME! use Path

        if mapping:
            if not isinstance(mapping, Mapping):
                raise TypeError("ERROR! a mapping used to initialize a FilenameMapper must be a proper mapping!")
            self.mapping = mapping
        else:
            self.mapping = {}.copy()

        self.filename = map_file

    def __repr__(self) -> str:
        """Return a printable representation.
        """
        ret = f"< FilenameMapper object (mapping {len(self.mapping)} files) "
        ret += f"(stored in {shlex.quote(str(self.filename))}) " if self.filename else "(not tied to a file) "
        ret += ">"
        return ret

    def read_mappings(self, map_filename: Union[str, Path]) -> None:
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
        assert isinstance(map_filename, Path)

        try:
            with open(map_filename, newline='') as infile:
                reader = csv.reader(infile)
                reader.__next__()                                                   # Skip the header row.
                for key, value in {rows[0]:rows[1] for rows in reader}.items():
                    self.add_mapping(key, value)
        except FileNotFoundError:
            warnings.warn(f"Unable to read file mappings file {map_filename}! File does not exist.")

        self.filename = map_filename

    def add_mapping(self, orig_name: Union[str, Path],
                    new_name: Union[str, Path]) -> None:
        """Maps ORIG_NAME to NEW_NAME, i.e. creates a note that NEW_NAME was once
        called ORIG_NAME. This procedure does not do the renaming itself, and does
        not write the changes to disk.
        """
        if not isinstance(orig_name, str): orig_name = str(orig_name)       # FIXME! Use Path!
        if not isinstance(new_name, str): new_name = str(new_name)          # FIXME! Use Path!

        if orig_name in self.mapping.values():
            for i in self.mapping:                  # If file appears  as a name resulting from a rename  ...
                if self.mapping[i] == orig_name:    # ... go through the dict, looking for things that point to it ...
                    self.mapping[i] = new_name      # ... and update the references to the new name.
        else:
            self.mapping[orig_name] = new_name

    def rename_and_map(self, orig_name: Union[str, Path],
                       new_name: Union[str, Path]) -> None:
        """Rename a file and keep track of the mapping from old to new names.
        """
        if not isinstance(orig_name, str): orig_name = str(orig_name)       # FIXME! Use Path!
        if not isinstance(new_name, str): new_name = str(new_name)          # FIXME! Use Path!

        os.rename(orig_name, new_name)
        self.add_mapping(orig_name, new_name)

    def write_mappings(self) -> None:
        """Write the mapping to the .csv file that stores it."""
        with open(self.filename, 'w', newline='') as file_names:
            writer = csv.writer(file_names, dialect='unix')
            writer.writerow(['original name', 'new name'])
            writer.writerows(self.mapping.items())


if __name__ == "__main__":
    print("file_utils.py is not a program; it's a library of code to be used by other")
    print("programs. You can't usefully use it directly from the terminal.")
    sys.exit(1)
