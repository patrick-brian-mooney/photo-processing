#!/home/patrick/Documents/programming/python_projects/photo-processing/bin/python3
# -*- coding: utf-8 -*-
"""
The postprocess_photos.py script performs the kind of postprocessing work that
needs to happen when I move photos to my hard drive from one or more of my
cameras. It processes an entire directory at a time; just invoke it either
while the directory that needs to be processed is the current working
directory, or specifying the directory to process at the end of the command.

This script requires Python 3.6+ and that a series of external programs be
installed; read on for details. It does not currently, and probably never will,
run under any version of Windows, but it should run under most or all Unix-like
operating systems, including Linux and macOS, with minimal adjustment needed.
Comments, suggestions, bug reports, code contributions, and other feedback are
welcome, and should be submitted through the project's GitHub page.

I usually invoke the script after offloading photos from my camera(s)' memory
cards. Currently, it performs these tasks on a directory full of photos:
    1. Empties out the folder's .thumbnails directory if it has files, creates
       it if it doesn't exist, and locks it down by making it non-writable.
    2. Auto-renames all photos in the current directory, then writes a file,
       file_names.csv, indicating what the original name of each renamed file
       was. Files are renamed so that their new names encode the date and time
       when they were taken, based on the EXIF info or existing filename.
    3. Keeps track of the original and new names in doing so, and creates a
       record of the mapping between old and new names in a file it calls
       file_names.csv.
    4. Auto-rotates all photos in the current directory by calling exiftran.
    5. If any raw files are found in the directory, it automagically creates
       autotonemapped HDR files from those raw files.
    6. If any .SH files are found in the directory being processed, it assumes
       they are Bash scripts that call enfuse, possibly preceded by a call to
       align_image_stack (and are the product of automatic exposure bracketing
       by Magic Lantern, which is the only way that .SH files ever wind up on
       my memory cards). It then re-writes them, makes them executable, and
       calls them to create those enfused pictures. If this script encounters
       any non-enfuse scripts, it will happily attempt to rewrite them anyway,
       almost certainly producing garbage as a result.

       Tasks accomplished by this script-rewriting operation are:

           * Replacing the original names of the files in the script with their
             new names, as determined in the second step, above.
           * Extending the script by adding lines causing the script to take
             the TIFF output of the enfuse operation and re-encode it to HQ
             JPEG, then copying the EXIF metadata from the base (non-shifted)
             photo that begins the series into that resulting JPEG. (I take it
             that it's better to have SOME EXIF DATA than none; even if not
             quite all the metadata from the base photo applies, it's the
             closest available and is mostly a fair representation of the
             actual situation at the time.)
           * Moving the shots that were components of HDR tonemaps into a
             separate HDR_components folder.

That's it. That's all it does. Current limitations include:
    * It has limited support for anything that's not a JPEG image:
        * PNG images that have "Apple-style" date-type names are renamed to fit
          in with the other images. (In my case, these are Instagram-derived.)
        * known raw images are auto-processed to HDR.
        * known audio and video files are also renamed based on date.
      Aside from the above, this script does nothing with PNG, TIFF, BMP, etc.
    * It doesn't process any Magic Lantern scripts other than the enfuse/
      enfuse+align scripts. (ARE there others?)
    * It doesn't add the -d or -i (or -x, -y, or -z; or -C) options to the
      align line in rewritten Magic Lantern scripts, but maybe it should.

If the script is run from the command line without any parameters, it runs
through all of the above steps on all relevant files in the current directory.
If it is run with no action flags but specifying the name of a directory, it
runs through all of the above steps on all relevant files in THAT directory.
If any action flags are specified, it runs through only those actions that are
specified on the command line; this might be helpful if a previous run was
interrupted, for instance.

This program is part of Patrick Mooney's photo postprocessing scripts; the
complete set can be found at https://github.com/patrick-brian-mooney/photo-processing.
All programs in that collection are copyright 2015-2025 by Patrick Mooney; they
are free software released under the GNU GPL, either version 3 or (at your
option) any later version. See the file LICENSE.md for details.

The latest version of these scripts can always be found at
    https://github.com/patrick-brian-mooney/photo-processing
"""


import argparse
import datetime
import functools
import os
import shlex
import shutil
import subprocess
import sys
import time
import warnings

from pathlib import Path
from typing import Sequence, Union

from PIL import Image                   # [sudo] pip[3] install Pillow; https://python-pillow.org/
import tqdm                             # [sudo] pip[3] install tqdm; https://tqdm.github.io/

import create_HDR_script as hdr         # https://github.com/patrick-brian-mooney/photo-processing/
import HDR_from_raw as hfr
import photo_file_utils as fu
import photo_config


photo_config.startup()                  # Check that the system meets minimum requirements; find necessary executables

debugging = True
raw_must_be_paired_with_JPEG = False    # If True, delete raw photos that don't have a pre-existing JPEG counterpart
delete_small_raws = True                # Delete raw photos that are paired with small JPEGs.
maximum_short_side_length = 5000        # If an image's longest side is at least this long, it's not a "small image."

file_name_mappings = fu.FilenameMapper(map_file=Path('file_names.csv'))    # Maps original names to new names.


def python_help() -> None:
    print("""

    If you want to use postprocess_photos.py as a Python module, you might plausibly
    do something like this in a Python 3 shell:

        import postprocess_photos as pp
        help(pp)                                # to see the documentation for the script
        pp.file_name_mappings.read_mappings()   # to read in the existing file_names.csv
        pp.process_shell_scripts()

    This would read the existing filename mappings back into memory and rewrite the
    shell scripts in the directory; this might be useful, for instance, if the
    previous run of the script had been interrupted before this could be done. Note
    that, for many things the module can do, it needs to have a set of filename
    mappings in memory; this can be done by calling read_filename_mappings() to
    read an existing file_names.csv into memory, if that was created by a previous
    call to rename_photos(); if this hasn't been done yet, call rename_photos() to
    rename the photos, build the mappings, and write the file.

    There are some utility functions available that are never called by the script
    when it is merely invoked from the shell; they are available to be called by you
    from the Python shell once the module has been imported, though. These are
    currently:

        spring_forward():           if you forgot about DST before taking photos
        fall_back():                if you forgot about DST before photographing
        read_filename_mappings():   if you need to reload these to resume
        restore_file_names():       if you need to undo the auto-renaming

    Try running

        help(PROCEDURE_NAME)

    from the Python interpreter for more info on these; e.g., if you imported
    the module with

        import postprocess_photos as pp

    (as in the example above), you might try

        help(pp.fall_back)

    for the documentation on that function. You can also try help(pp) or
    help(postprocess_photos) for complete docs, or dir(pp) or
    dir(postprocess_photos) to inspect the module.

    """)


def print_usage():
    "Display a message explaining the usage of the script."
    print(__doc__)


def adjust_timestamps(file_list: Sequence[Path],
                      yr: int = 0,
                      mo: int = 0,
                      days: int = 0,
                      hr: int = 0,
                      m: int = 0,
                      sec: Union[int, float] = 0,
                      rename: bool = True) -> None:
    """Calls exiftool to adjust the timestamps of all files in FILE_LIST by the
    indicated amount. If any component of the date is negative, then the amount of
    time represented is subtracted from the current time for each file; otherwise,
    the amount of time is added to the current timestamp in each file.

    If RENAME is True (the default), the files are renamed based on the new
    timestamps after the timestamps are adjusted.

    Assumes all files in FILE_LIST are in the same directory.
    """
    # FIXME! We should also be doing this for sidecars/alternate versions!

    assert isinstance(file_list, Sequence)
    assert file_list, "ERROR! No files passed to adjust_timestamps!"
    assert all([isinstance(f, Path) for f in file_list]), "ERROR! All files passed to adjust_timestamps must be Paths"

    if not all([file_list[0].parent.samefile(f.parent) for f in file_list]):
        raise ValueError("ERROR! Every file passed to adjust_timestamps must be in the same directory!")

    if not (yr or mo or days or hr or m or sec):
        print("No timeshift specified! Quitting ...")
        return

    old_dir = Path.cwd()
    try:
        os.chdir(file_list[0].parent)
        sign = "-" if [i for i in [yr, mo, days, hr, m, sec] if i < 0] else "+"
        f_date = f"{abs(yr)}:{abs(mo)}:{abs(days)} {abs(hr)}:{abs(m)}:{abs(sec)}"
        subprocess.call([photo_config.executable_location('exiftool'), '-m', f'-AllDates{sign}={f_date}',
                         f'-FileModifyDate{sign}={f_date}', '-overwrite_original'] + [str(f) for f in file_list])

        if rename:
            mappings = fu.FilenameMapper()
            mappings.read_mappings(Path('file_names.csv'))
            for f in file_list:
                new_name = fu.find_unique_name(fu.name_from_date(f))
                mappings.rename_and_map(f, new_name)
            mappings.write_mappings()
    finally:
        os.chdir(old_dir)


def set_timestamps(file_list: Sequence[Path],
                   yr: int,
                   mo: int,
                   days: int,
                   hr: int,
                   m: int,
                   sec: Union[int, float] = 0):
    """Calls exiftran to set the EXIF timestamps of all files in FILE_LIST to the
    indicated date and time.

    This function, unlike its similarly-named counterpart above, does not rename
    files after giving them an EXIF timestamp, because my own postprocessing
    workflow tends to use this only on files entirely without EXIF data in the first
    place: scanned negatives, primarily. In any case, these files that come without
    ANY date already embedded tend to be named according to criteria other than
    embedded datetimes: primarily, these numbers are based on film roll ID# and the
    sequential number of the negative on the roll.

    Assumes all files in FILE_LIST are in the same directory.
    """
    assert isinstance(file_list, Sequence), "ERROR: set_timestamps() was not passed a LIST OF FILES as FILE_LIST!"
    assert file_list, "ERROR! Must pass at least one file to set_timestamps!"
    assert all([isinstance(f, Path) for f in file_list]), "ERROR! Every file passed to set_timestamps must be a Path!"
    assert all([file_list[0].parent.samefile(f.parent) for f in file_list]), \
        "ERROR: all files passed to set_timestamps() must be in the same directory!"

    old_dir = os.getcwd()
    try:
        os.chdir(file_list[0].parent)
        f_date = f"{yr}:{mo}:{days} {hr}:{m}:{sec}"
        subprocess.call([photo_config.executable_location('exiftool'), '-m', f'-AllDates={f_date}',
                         f'-FileModifyDate={f_date}', '-overwrite_original'] + [str(f) for f in file_list])
    finally:
        os.chdir(old_dir)


def increment_timestamp(file_list: Sequence[Path]) -> None:
    """Add one hour to the timestamp for each file in FILE_LIST.
    """
    adjust_timestamps(file_list, hr=1)


def decrement_timestamp(file_list: Sequence[Path]) -> None:
    """Subtract one hour from the timestamp for each file in FILE_LIST.
    """
    adjust_timestamps(file_list, hr=-1)


def spring_forward() -> None:
    """Adjust the EXIF timestamps on the batch of photos in the current directory by
    adding one hour to them, as if I had forgotten to do this after the DST
    change. This function is NEVER called directly by the code itself and is not
    available from the command line; it's a utility function available from the
    Python interpreter after the script is imported.

    This routine DOES NOT require that you have previously read a set of file name
    mappings into memory; it just operates on all JPEG files in the current
    directory.
    """
    # FIXME! We should also be doing this for any sidecars
    increment_timestamp(sorted([f for f in Path().glob('*') if f.suffix.casefold() == '.jpg']))


def fall_back() -> None:
    """Adjust the EXIF timestamps on the batch of photos in this directory by
    subtracting one hour from them, as if I had forgotten to do this after the DST
    change. This function is NEVER called directly by the code itself and is not
    available from the command line; it's a utility function available from the
    Python interpreter after the script is imported.

    This routine DOES NOT require that you have previously read a set of file name
    mappings into memory; it just operates on all JPEG files in the current
    directory.
    """
    # FIXME! We should also be doing this for any sidecars
    decrement_timestamp(sorted([f for f in Path().glob('*') if f.suffix.casefold() == '.jpg']))


def empty_thumbnails() -> None:
    """Create an empty .thumbnails directory and make it writable for no one.
    This routine DOES NOT REQUIRE having previously read in a set of filename
    mappings; it just operates on the current directory.
    """
    print("Keeping directory's .thumbnails subdirectory empty ... ", end='')
    try:
        if Path('.thumbnails').exists():
            if Path('.thumbnails').is_dir():
                shutil.rmtree(Path('.thumbnails'))
            else:
                Path('.thumbnails').unlink()

        # OK, now create the directory and make it writable for no one
        Path('.thumbnails').mkdir(mode=0o555)

    except BaseException as errrr:
        print('\n')     # End the status line that's waiting to be ended
        raise errrr     # before allowing the error to propagate.
    print(' ... done.\n\n')


def delete_spurious_raw_files() -> None:
    """This function performs a few related cleanup tasks.

    First, it ensures that every raw file has a corresponding JPEG file. I only
    shoot raw photos in RAW+JPG mode, never raw-only, so any raw photos without
    corresponding JPEGs indicate that the JPEG was deleted in an attempt to erase
    "the photo." Since some quick viewers don't support raw files at all, and "the
    photo" here means "both related files," this procedure ensures that JPEGs
    deleted in one of these quick viewers don't leave orphaned raw files behind.

    This first action can be turned off by setting the global variable
    raw_must_be_paired_with_JPEG to False.

    Second, it removes raw files whose JPEG files have been resized to lower-res
    versions. I occasionally, through oversight or lack of time to make settings
    adjustments or after-the-fact reconsideration, wind up with raw photos whose
    corresponding JPEG shots are destined to be resized to a lower resolution
    because they only capture information and lack essentially all aesthetic merit.
    Provided that the small JPEG adequately captures a legible version of that
    information, I'd rather recover the drive space used to store the superfluous
    raw file.

    This second action can be turned off by setting the global variable
    delete_small_raws to False. It is possible to configure how short the longer
    side of the corresponding JPEG needs to be for the raw file to be deleted: set
    the global variable maximum_short_side_length to the largest value that should
    be considered "the longest side of a short file."

    This routine DOES NOT REQUIRE that a set of filename mappings be read into
    memory; it just operates on all eligible files in the current directory without
    modifying or otherwise interacting with the global filename mappings at all.
    """
    # First, delete any raw files that do not have a corresponding JPEG.
    @functools.lru_cache
    def jpeg_finder(raw: Path) -> Path:
        """Helper function used below.
        """
        return fu.find_alt_version(raw, fu.jpeg_extensions)

    @functools.lru_cache
    def max_img_length(img: Path) -> Union[None, int]:
        """Helper function used below.
        """
        try:
            im = Image.open(img)
            return max(im.size)
        except BaseException as errrr:
            warnings.warn(f"Cannot retrieve dimensions for file {img}! The system said: {errrr}")
            return None

    if raw_must_be_paired_with_JPEG:
        orphan_raws = [f for f in fu.list_of_raws() if not fu.find_alt_version(f, fu.jpeg_extensions)]
        if orphan_raws:
            print("\nEliminating raws without corresponding JPEGs ...")
            for which_raw in tqdm.tqdm(orphan_raws):
                print(f"Raw file '{which_raw}' has no corresponding JPEG; deleting ...")
                which_raw.unlink()

    # Now, delete any raw files whose corresponding JPEG is "small."
    if delete_small_raws:
        print("\nScanning raw files to find small corresponding JPEGs ...")
        raws_with_jpg = [(raw, jpeg_finder(raw)) for raw in tqdm.tqdm(fu.list_of_raws()) if jpeg_finder(raw)]
        if raws_with_jpg:
            raws_with_small_jpgs = [(raw, jpg) for raw, jpg in tqdm.tqdm(raws_with_jpg) if
                                    (max_img_length(jpg) and (max_img_length(jpg) < maximum_short_side_length))]
            if raws_with_small_jpgs:
                print("Deleting raw files whose JPEGs were reduced in size ...")
                for which_raw, corr_jpg in tqdm.tqdm(raws_with_small_jpgs):
                    if corr_jpg:
                        print(f"Raw file '{which_raw}' has low-resolution JPEG with max. dimension "
                              f"{max_img_length(corr_jpg)}; deleting ...")
                        which_raw.unlink()
                    else:                       # We SHOULD have already covered this ...
                        which_raw.unlink()          # ... but just for the sake of being perfectly sure ...


def rename_photos() -> None:
    """Auto-rename files based on the time when they were taken. This routine
    DOES NOT REQUIRE that a set of filename mappings be read into memory;
    instead, it creates that set of mappings and writes it to the current
    directory as file_names.csv.

    Starts by reading the date and time from each image, ideally from the EXIF
    info, but trying to extract it from the filename if this fails.

    Keeps a list as file_list: [dateTime, file_name], then converts it into another
    list in the file_name_mappings object: originalName -> newName
    """
    print('Renaming photos (based on EXIF data, where possible) ... ')
    try:
        # First, get a list of all relevant files and (as best we can determine) when they were shot.
        renameable_extensions = fu.raw_photo_extensions | fu.jpeg_extensions | fu.other_image_extensions
        renameable_extensions = renameable_extensions | (fu.movie_extensions | fu.audio_extensions)

        which_files = {f for f in Path().glob('*') if f.suffix.casefold() in renameable_extensions}
        file_list = [[fu.name_from_date(img), img] for img in which_files]

        # OK, now sort that list (twice). First, sort by original filename (globbing filenames does not preserve
        # order). Then, sort again by datetime string. Since Python sorts are stable, the second sort will preserve
        # the order of the first when values for the sort-by key for the second sort are identical.
        file_list.sort(key=lambda item: str(item[1]))
        file_list.sort(key=lambda item: str(item[0]))

        # Finally, actually rename the files, keeping a dictionary that maps the original to the new names.
        try:
            for _, cur_name in tqdm.tqdm(file_list):
                # recalc suggested name. Don't reuse the previously generated one -- dir contents might have changed.
                new_name = fu.find_unique_name(fu.name_from_date(cur_name))
                if not new_name.exists() or not new_name.samefile(cur_name):
                    file_name_mappings.rename_and_map(cur_name, new_name)
                    raw_version = fu.find_alt_version(cur_name, fu.raw_photo_extensions)
                    if raw_version:
                        new_raw = new_name.with_suffix(raw_version.suffix)
                        file_name_mappings.rename_and_map(raw_version, new_raw)
                    json_version = fu.find_alt_version(cur_name, fu.json_extensions)
                    if json_version:
                        file_name_mappings.rename_and_map(json_version, new_name.with_suffix('.json'))

        finally:
            file_name_mappings.write_mappings()     # Write what we've got, no matter what.

    except BaseException as errrr:
        print('\n')     # If an error occurs, end the status line in progress before letting the error propagate.
        raise errrr

    print('     ... done.\n\n')


def restore_file_names() -> None:
    """Restore original file names, based on the dictionary in memory, which is
    assumed to be comprehensive and intact. This routine REQUIRES that a set of
    filename mappings is already in memory; this can be accomplished by calling
    read_filename_mappings() to read an existing file_names.csv file into
    memory.

    # FIXME! Ultimately, the FilenameMapper object should be holding and mapping
    Paths, not strings, and when that happens, we should use Path-based file
    manipulations instead of os.path.
    """
    for original_name, new_name in tqdm.tqdm(file_name_mappings.mapping.items()):
        if os.path.exists(new_name):
            print('Renaming "%s" to "%s".' % (new_name, original_name))
            os.rename(new_name, original_name)


def rotate_photos() -> None:
    """Auto-rotate all photos using exiftran. DOES NOT REQUIRE that a set of
    filename mappings be in memory; it just operates on the JPEG files in the
    current folder.
       It operates on no more than 128 files per invocation of exiftran to make sure
    that we don't run up against the system's limit on maximum number of files
    passed to an external program.
    """
    print('Auto-rotating images ...\n\n')
    all_photos = sorted([f for f in Path().glob('*') if f.suffix.casefold() == ".jpg"])
    for photo in tqdm.tqdm(all_photos):
        subprocess.call([photo_config.executable_location('exiftran'), '-aigp'] + [str(photo)])


def process_shell_scripts() -> None:
    """Rewrite any shell scripts created by Magic Lantern.

    Currently, we only process HDR_????.SH scripts, which call enfuse. They MAY
    (well ... should) call align_image_stack first, but that depends on whether I
    remembered to choose 'align + enfuse" in Magic Lantern. Currently, up to two
    changes are made: old file names are replaced with their new file name
    equivalents, and (optionally) output is made TIFF instead of JPEG. This part of
    the script is currently heavily dependent on the structure of these Magic
    Lantern scripts (currently, they're produced by Magic Lantern firmware version
    1.0.2-ml-v2.3). In any case, this procedure creates identical output scripts
    whether or not the input script includes the align step.

    This routine REQUIRES that a set of filename mappings have already been read
    into memory; you can accomplish this by calling read_filename_mappings() to read
    an existing file_names.csv file into memory.

    #FIXME: this docstring needs a rewrite.
    """
    @functools.lru_cache
    def cmp(f: Path) -> str:
        """Convenience function to produce a case-insensitive stringified version of
         a Path's name.
        """
        return str(f).casefold()

    print('\nRewriting enfuse HDR scripts ... ')
    try:
        all_scripts = [s for s in Path().glob('*') if cmp(s).startswith('hdr') and cmp(s).endswith('.sh')]
        for which_script in tqdm.tqdm(all_scripts):
            print(f'    Rewriting {which_script}')
            with open(which_script, 'rt') as the_script:
                script_lines = the_script.readlines()
                if script_lines[4].startswith('align_image_stack'):
                    # It's an align-first script, with 8 lines, 5 non-blank.
                    # Getting the script filenames takes some processing time here. It assumes a familiarity with
                    # the format of this line in ML firmware version 1.0.2-ml-v2.3, which currently looks like this:
                    #    align_image_stack -m -a OUTPUT_PREFIX INFILE1.JPG INFILE2.JPG [...]

                    # The number of infiles depends, of course, on settings that were in effect when the sequence
                    # was taken. So, the align_line, when tokenized, is, by array index:
                    #   [0] executable name
                    #   [1] -m, a switch meaning "optimize field of view for all images except for the first."
                    #   [2 and 3] -a OUTPUT_PREFIX specifies the prefix for all output files.
                    #   [4 to end] the names of the input files.
                    hdr_input_files = [file_name_mappings.mapping[f] if f in file_name_mappings.mapping
                                       else f
                                       for f in script_lines[4].split()[4:] ]

                else:                                   # It's a just-call-enfuse script, with 6 lines, 3 non-blank.
                    last_line_tokens = script_lines[-1].split()     # Get the names of the input files.
                    hdr_input_files = [file_name_mappings.mapping[f] if f in file_name_mappings.mapping
                                       else f
                                       for f in last_line_tokens[3:]]

            hdr.create_script_from_file_list(hdr_input_files, to_move=which_script)

    except BaseException as errrr:
        print()     # If an error occurs, end the line that's waiting to be ended before letting the error propagate.
        raise errrr

    print('\n ... done rewriting enfuse scripts.\n')


def run_shell_scripts() -> None:
    """Run the executable shell scripts in the current directory, then make them
    non-executable after they have been run.

    This routine DOES NOT REQUIRE that filename mappings have been read into
    memory; it just runs all the executable shell scripts in the current
    directory.
    """
    try:
        Path('HDR_components').mkdir()
        print("\nHDR_components/ directory created.")
    except FileExistsError:
        pass                                            # target directory already exists? Cool!

    scripts = sorted([f for f in Path().glob("*") if (str(f).casefold().endswith('.sh') and os.access(f, os.X_OK))])
    if not scripts:
        print(f'No scripts to run in directory {Path().resolve()} ...')
        return

    print(f"Running {len(scripts)} executable script{'s' if (len(scripts) > 1) else ''} in {os.getcwd()} ...")
    for which_script in tqdm.tqdm(scripts):
        print(f'\n\n    Running script: {which_script}')
        subprocess.call([str(which_script.resolve())])
        os.system(f'chmod a-x -R {shlex.quote(str(which_script))}')

    print("\n\n ... done running scripts.")


def create_hdrs_from_raws():
    """Create a tonemap from every raw file in the current directory by creating and
    running an intermediate Bash script. Created scripts remain after this file .

    This routine DOES NOT REQUIRE that filename mappings have been read into
    memory; it just operates on all the identifiable raw photos in the current
    directory.
    """
    the_raws = sorted(fu.list_of_raws())
    if not the_raws:
        print("\nNo raw photos detected, moving on ...")
        return

    print(f"\nCreating HDR JPEGs (and intermediate scripts) from {len(the_raws)} raw files ...\n\n")
    for which_raw in tqdm.tqdm(the_raws):
        hfr.hdr_tonemap_from_raw(which_raw)


def hang_around() -> None:
    """Offers to hang around, watching for executable shell scripts in the
    directory and running them if they appear. This might be handy if, for
    instance, all the shell scripts had been accidentally deleted: this
    script can be left running while the files in the directory are manually
    examined and new shell scripts are created (perhaps by running
    create_HDR_script.py). Note that this will have to be interrupted with Ctrl+C;
    it will otherwise just run forever, waiting.

    This routine DOES NOT REQUIRE that filename mappings have been read into
    memory; it just runs all the executable shell scripts in the current
    directory.
    """
    while True:
        print(f"  (Current directory is {os.getcwd()})")
        print(f'Looking for executable shell scripts at {datetime.datetime.now().isoformat()} ...')
        file_list = [f for f in Path().glob("*SH") if (str(f).casefold().endswith('.sh') and os.access(f, os.X_OK))]
        if file_list:
            print(f"Found {len(file_list)} script{'s' if (len(file_list) > 1) else ''}; executing ...")
            run_shell_scripts()
        else:
            time.sleep(30)


# OK, let's go
def main() -> None:
    force_debug = False         # Used if program setup in IDE is needed.
    if force_debug:
        # Whatever statements need are needed to set up an IDE run go here.
        os.chdir('/home/patrick/Photos/2025-05-25')

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
                                     epilog="""Currently, this suite of scripts depends (directly itself, or indirectly by
way of the scripts it writes) on these external programs:

    program             Debian package name     My version
    -------             -------------------     ----------
    align_image_stack   enfuse                  4.1.3+dfsg-2
    enfuse                  "                       "
    convert             imagemagick             8:6.8.9.9-5
    mogrify                 "                       "
    dcraw               dcraw                   9.21-0.2
    exiftool            libimage-exiftool-perl  9.74-1
    exiftran            exiftran                2.09-1+b1
    ffmpeg              ffmpeg                  7:2.8.15
    luminance-hdr       luminance-hdr           2.4.0-8

Other versions will often, though not necessarily always, work just fine.
YMMV. Remember that Ubuntu is not Debian and package names may be different.
Synaptic is your friend if you're having trouble finding things. If you're
a Debian (or Ubuntu, or Linux Mint ...) user who's lost and not sure where to
start, try

    sudo apt install enfuse imagemagick dcraw libimage-exiftool-perl exiftran \
        ffmpeg luminance-hdr

in a terminal and see if that helps.

This script can also be imported as a Python module (it requires Python 3.5+);
try typing

    ./postprocess_photos.py --pythonhelp

in a terminal for more.

This program comes with ABSOLUTELY NO WARRANTY. Use at your own risk.

This program is part of Patrick Mooney's photo postprocessing scripts; the
complete set can be found at https://github.com/patrick-brian-mooney/photo-processing.
All programs in that collection are copyright 2015-2023 by Patrick Mooney; they
are free software released under the GNU GPL, either version 3 or (at your
option) any later version. See the file LICENSE.md for details.
""",)
    parser.add_argument('-e', '--empty', '--empty-thumbnails', '--empty_thumbnails', action='store_true',
                        help="force the directory's .thumbnails cache to be empty and non-writeable")
    parser.add_argument('-d', '--delete', '--delete-spurious-raw-files', '--delete_spurious_raw_files',
                        action='store_true', help="delete raw files not associated with a JPEG")
    parser.add_argument('-r', '--rename', '--rename-photos', '--rename_photos', action='store_true',
                        help="rename all photos based on their EXIF date and time")
    parser.add_argument('-c', '--create', '--create-HDRs-from-raws', '--create_HDRs_from_raws',
                        action='store_true', help="create HDR scripts for all raw files, then run those scripts")
    parser.add_argument('-t', '--rotate', '--rotate-photos', '--rotate_photos', action='store_true',
                        help="rotate all photos in the directory to their default EXIF orientation")
    parser.add_argument('-p', '--process', '--process-shell-scripts', '--process_shell_scripts',
                        action='store_true', help="rewrite Magic Lantern scripts in the directory")
    parser.add_argument('-u', '--run', '--run-shell-scripts', '--run_shell_scripts', action='store_true',
                        help="run all executable shell scripts in the directory")
    parser.add_argument('-y', '--python-help', '--python_help', action='store_true',
                        help="run all executable shell scripts in the directory")
    parser.add_argument(dest="directory", nargs='?', default=Path('.'), type=Path,
                        help = "directory containing images to process")
    args = vars(parser.parse_args())            # Now we have a dictionary of command-line arguments

    if args['python_help']:
        python_help()
        sys.exit(0)

    # Massage the list of actions to perform: If NO actions are specified, do EVERYTHING.
    actions = ['create', 'delete', 'empty', 'process', 'rename', 'rotate', 'run']
    if all([not args[a] for a in actions]):
        for a in actions:
            args[a] = True

    if not args['directory'].is_dir():
        print(f"ERROR! {args['directory']} is not a directory.")
    elif not args['directory'].samefile(Path('.')):
        os.chdir(args['directory'])

    try:        # Read existing filename mappings if there are any, and if they're readable.
        file_name_mappings.read_mappings(Path('file_names.csv'))
    except FileNotFoundError:
        pass
    except OSError as errrr:
        print(f"Unable to read file_names.csv! The system said: {errrr}")

    # OK, let's do the things that we actually need to do.
    if args['empty']: empty_thumbnails()
    if args['delete']: delete_spurious_raw_files()
    if args['rename']: rename_photos()
    if args['create']: create_hdrs_from_raws()
    if args['rotate']: rotate_photos()
    if args['process']: process_shell_scripts()
    if args['run']: run_shell_scripts()

    prompt = "Want me to hang around and run scripts that show up? (Say NO if unsure.) --|  "
    if input(prompt).strip().casefold()[0].startswith("y"):
        print('\n\nOK, hit ctrl-C when finished.\n')
        hang_around()                                      # We're done!


if __name__ == "__main__":
    start_time = datetime.datetime.now()
    try:
        py_vers = sys.version.split('\n')[0]
        print(f"We're starting, running under Python {py_vers} ...")
        main()
    finally:
        print(f"\n\nRun finished in {((datetime.datetime.now() - start_time).seconds)/60:.3f} minutes!")
