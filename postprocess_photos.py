#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""

The postprocess_photos.py script performs the kind of postprocessing work that
needs to happen when I move photos to my hard drive from one or more of my
cameras. It processes an entire directory at a time; just invoke it by typing

    ./postprocess_photos.py

while the directory that needs to be processed is the current working
directory.

Currently, it performs the following tasks:
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
    5. If any .SH files are found in the directory being processed, it assumes
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
    * It doesn't do anything with non-JPEG images, except for videos and known raw
      images. It does nothing with PNG, TIFF, BMP, etc.
    * It only operates on the current working directory.
    * It doesn't process any Magic Lantern scripts other than the enfuse/
      enfuse+align scripts. (ARE there others?)
    * It doesn't add the -d or -i (or -x, -y, or -z; or -C) options to the
      align line in rewritten Magic Lantern scripts, but maybe it should.

Currently, it depends (directly itself, or indirectly by virtue of the scripts
it writes) on these external programs:

    program             Debian package name     My version
    -------             -------------------     ----------
    align_image_stack   enfuse                  4.1.3+dfsg-2
    convert             imagemagick             8:6.8.9.9-5
    enfuse              enfuse                  4.1.3+dfsg-2
    exiftool            libimage-exiftool-perl  9.74-1
    exiftran            exiftran                2.09-1+b1

Other versions will often, though not necessarily always, work just fine.
YMMV. Remember that Ubuntu is not Debian and package names may be different.
Synaptic is your friend if you're having trouble finding things.

This script can also be imported as a Python module (it requires Python 3); try
typing

    ./postprocess_photos.py --pythonhelp

in a terminal for more.

This program comes with ABSOLUTELY NO WARRANTY. Use at your own risk.

This program is part of Patrick Mooney's photo postprocessing scripts; the
complete set can be found at https://github.com/patrick-brian-mooney/photo-processing.
All programs in that collection are copyright 2015-2018 by Patrick Mooney; they
are free software released under the GNU GPL, either version 3 or (at your
option) any later version. See the file LICENSE.md for details.
"""


import csv, datetime, glob, os, shlex, shutil, subprocess, sys, time

import exifread                         # https://github.com/ianare/exif-py; sudo pip3 install exifread
from PIL import Image                   # [sudo] pip[3] install Pillow; https://python-pillow.org/

import create_HDR_script as hdr         # https://github.com/patrick-brian-mooney/photo-processing/
import HDR_from_raw as hfr              # https://github.com/patrick-brian-mooney/photo-processing/
import file_utils as fu                 # https://github.com/patrick-brian-mooney/photo-processing/


debugging = True
force_debug = False

raw_must_be_paired_with_JPEG = False    # Delete raw photos that don't have a pre-existing JPEG counterpart
delete_small_raws = True                # Delete raw photos that are paired with small JPEGs.
maximum_short_side_length = 5000        # If the longest side of an image is at least this long, it's not a "small image."

file_name_mappings = fu.FilenameMapper(filename='file_names.csv')      # Maps original names to new names.


def python_help():
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

def _increment_timestamp(file_list):
    """Add one hour to the timestamp for each file in FILE_LIST."""
    assert isinstance(file_list, (list, tuple))
    subprocess.call('exiftool "-alldates+=1:00:00" "-FileModifyDate+=1:00:00" -overwrite_original %s' % ' '.join([shlex.quote(f) for f in file_list]), shell=True)

def _decrement_timestamp(file_list):
    """Subtract one hour from the timestamp for each file in FILE_LIST."""
    assert isinstance(file_list, (list, tuple))
    subprocess.call('exiftool "-alldates-=1:00:00" "-FileModifyDate-=1:00:00" -overwrite_original %s' % ' '.join([shlex.quote(f) for f in file_list]), shell=True)

def spring_forward():
    """Adjust the EXIF timestamps on the batch of photos in this directory by
    adding one hour to them, as if I had forgotten to do this after the DST
    change. This function is NEVER called directly by the code itself and is not
    available from the command line; it's a utility function available from the
    Python interpreter after the script is imported.

    This routine DOES NOT require that you have previously read a set of file name
    mappings into memory; it just operates on all JPEG files in the current
    directory.
    """
    _increment_timestamp(sorted(list(set(glob.glob('*jpg') + glob.glob('*JPG')))))

def fall_back():
    """Adjust the EXIF timestamps on the batch of photos in this directory by
    subtracting one hour from them, as if I had forgotten to do this after the DST
    change. This function is NEVER called directly by the code itself and is not
    available from the command line; it's a utility function available from the
    Python interpreter after the script is imported.

    This routine DOES NOT require that you have previously read a set of file name
    mappings into memory; it just operates on all JPEG files in the current
    directory.
    """
    _decrement_timestamp(sorted(list(set(glob.glob('*jpg') + glob.glob('*JPG')))))

def empty_thumbnails():
    """Create an empty .thumbnails directory and make it writable for no one.
    This routine DOES NOT REQUIRE having previously read in a set of filename
    mappings; it just operates on the current directory.
    """
    print("Keeping directory's .thumbnails subdirectory empty ... ", end='')
    try:
        if os.path.exists('.thumbnails'):
            if os.path.isdir('.thumbnails'):
                shutil.rmtree('.thumbnails')
            else:
                os.unlink('.thumbnails')
        # OK, now create the directory and make it writable for no one
        os.mkdir('.thumbnails')
        os.chmod('.thumbnails', 0o555)
    except:
        print('\n') # If an error occurs, end the status line that's waiting to be ended
        raise           #  then let the error propagate.
    print(' ... done.\n\n')

def delete_spurious_raw_files():
    """This function performs a few related cleanup tasks.

    First, it ensures that every raw file has a corresponding JPEG file. I only
    shoot raw photos in RAW+JPG mode, never raw-only, so any raw photos without
    corresponding JPEGs indicate that the JPEG was deleted in an attempt to erase
    "the photo." Since many quick viewers don't support raw at all, and "the photo"
    here means "both related files," this procedure ensures that JPEGs deleted in
    one of these quick viewers don't leave orphaned raw files behind.

    This first action can be turned off by setting the global variable
    raw_must_be_paired_with_JPEG to False.

    Second, it removes raw files whose JPEG files have been resized to lower-
    resolution versions. I occasionally, through oversight or lack of time to make
    settings adjustments or after-the-fact reconsideration, wind up with raw photos
    whose corresponding JPEG shots are destined to be resized to a lower resolution
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
    if raw_must_be_paired_with_JPEG:
        orphan_raws = [f for f in fu.list_of_raws() if not fu.find_alt_version(f, fu.jpeg_extensions)]
        for which_raw in orphan_raws:
            print("Raw file '%s' has no corresponding JPEG; deleting ..." % which_raw)
            os.remove(which_raw)
    if delete_small_raws:
        # orphan_raws = [][:]
        for which_raw in fu.list_of_raws():
            corresponding_jpg = fu.find_alt_version(which_raw, fu.jpeg_extensions)
            if corresponding_jpg:
                im = Image.open(corresponding_jpg)
                if max(im.size) < maximum_short_side_length:
                    print("Raw file '%s' has low-resolution corresponding JPEG; deleting ..." % which_raw)
                    os.remove(which_raw)
            else:                       # We SHOULD have already covered this ...
                os.remove(which_raw)        # ... but just for the sake of being perfectly sure ...

def rename_photos():
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
        file_list, which_files = [][:], [][:]
        for which_ext in fu.raw_photo_extensions + ('jpg', 'JPG', "MOV", "mov"):
            which_files += glob.glob('*' + which_ext)
        for which_image in sorted(list(set(which_files))):
            new_name = fu.name_from_date(which_image)
            file_list.append([new_name, which_image])

        # OK, now sort that list (twice). First, sort by original filename (globbing filenames does not preserve this). Then, sort
        # again by datetime string. Since Python sorts are stable, the second sort will preserve the order of the first when values
        # for the sort-by key for the second sort are identical.
        file_list.sort(key=lambda item: item[1])
        file_list.sort(key=lambda item: item[0])

        # Finally, actually rename the files, keeping a dictionary that maps the original to the new names.
        try:
            while len(file_list) > 0:
                which_file = file_list.pop(0)
                new_name = fu.find_unique_name(fu.name_from_date(which_file[1])).strip()
                if new_name != which_file[1]:
                    file_name_mappings.rename_and_map(which_file[1], new_name)
                    raw_version = fu.find_alt_version(which_file[1], fu.raw_photo_extensions)
                    if raw_version:
                        new_raw = os.path.splitext(new_name)[0] + os.path.splitext(raw_version)[1]
                        file_name_mappings.rename_and_map(raw_version, new_raw)
                    json_version = fu.find_alt_version(which_file[1], fu.json_extensions)
                    if json_version:
                        file_name_mappings.rename_and_map(json_version, os.path.splitext(new_name)[0] + '.json')
        finally:
            file_name_mappings.write_mappings()     # Write what we've got, no matter what.
    except:
        print('\n')     # If an error occurs, end the status line in progress before letting the error propagate.
        raise
    print('     ... done.\n\n')

def restore_file_names():
    """Restore original file names, based on the dictionary in memory, which is
    assumed to be comprehensive and intact. This routine REQUIRES that a set of
    filename mappings is already in memory; this can be accomplished by calling
    read_filename_mappings() to read an existing file_names.csv file into
    memory.
    """
    for original_name, new_name in file_name_mappings.mapping.items():
        if os.path.exists(new_name):
            print('Renaming "%s" to "%s".' % (new_name, original_name))
            os.rename(new_name, original_name)

def rotate_photos():
    """Auto-rotate all photos using exiftran. DOES NOT REQUIRE that a set of
    filename mappings be in memory; it just operates on the JPEG files in the
    current folder.
       It operates on no more than 128 files per invocation of exiftran to make sure
    that we don't run up against the system's limit on maximum number of files
    passed to an external program.
    """
    print('Auto-rotating images ...\n\n')
    all_photos, rest = sorted(glob.glob('*jpg') + glob.glob('*JPG')), None
    while all_photos:
        if len(all_photos) > 128:
            all_photos, rest = all_photos[:128], all_photos[128:]
        else:
            rest = None
        print()             # Give some indication of when we've ended a block of 128 photos.
        subprocess.call('exiftran -aigp %s' % ' '.join([shlex.quote(f) for f in all_photos]), shell=True)
        all_photos = rest

def process_shell_scripts():
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
    """
    print('\nRewriting enfuse HDR scripts ... ')
    try:
        for which_script in glob.glob('HDR*SH'):
            print('    Rewriting %s' % which_script)
            old_perms = os.stat(which_script).st_mode
            with open(which_script, 'r') as the_script:
                script_lines = the_script.readlines()
                if script_lines[4].startswith('align_image_stack'):         # It's an align-first script, with 8 lines, 5 non-blank.
                    # Getting the script filenames takes some processing time here. It assumes a familiarity with the format of this
                    # line in ML firmware version 1.0.2-ml-v2.3, which currently looks like this:
                    #
                    #    align_image_stack -m -a OUTPUT_PREFIX INFILE1.JPG INFILE2.JPG [...]

                    # The number of infiles depends, of course, on settings that were in effect when the sequence was taken.
                    #
                    # So, the align_line, when tokenized, is, by array index:
                    #   [0] executable name
                    #   [1] -m, a switch meaning "optimize field of view for all images except for the first."
                    #   [2 and 3] -a OUTPUT_PREFIX specifies the prefix for all of the output files.
                    #   [4 to end] the names of the input files.
                    HDR_input_files = [file_name_mappings.mapping[which_file] if which_file in file_name_mappings.mapping
                                       else which_file
                                       for which_file in script_lines[4].split()[4:] ]
                else:                                       # It's a just-call-enfuse script, with 6 lines, 3 non-blank.
                    new_script = script_lines[:-1]          # Tokenize and get the names of the input files.
                    last_line_tokens = script_lines[-1].split()
                    HDR_input_files = [file_name_mappings.mapping[which_file] if which_file in file_name_mappings.mapping
                                       else which_file
                                       for which_file in last_line_tokens[3:]]
            hdr.create_script_from_file_list(HDR_input_files, file_to_move=which_script)
    except:
        print()     # If an error occurs, end the line that's waiting to be ended before letting the error propagate.
        raise
    print('\n ... done rewriting enfuse scripts.\n')

def run_shell_scripts():
    """Run the executable shell scripts in the current directory. Make them non-
    executable after they have been run.

    This routine DOES NOT REQUIRE that filename mappings have been read into
    memory; it just runs all the executable shell scripts in the current
    directory.
    """
    try:
        os.mkdir('HDR_components')
        print("\nHDR_components/ directory created.")
    except FileExistsError: pass                                            # target directory already exists? Cool!
    print("Running executable scripts in %s ..." % os.getcwd())
    file_list = sorted([which_script for which_script in glob.glob("*SH") if os.access(which_script, os.X_OK)])
    for which_script in file_list:
        print('\n\n    Running script: %s' % which_script)
        subprocess.call('./' + shlex.quote(which_script))
        os.system('chmod a-x -R %s' % shlex.quote(which_script))
    print("\n\n ... done running scripts.")

def create_HDRs_from_raws():
    """For every raw file, create a tonemap from it, creating an intermediate
    script along the way, which it runs in order to create the tonemap.

    This routine DOES NOT REQUIRE that filename mappings have been read into
    memory; it just operates on all of the identifiable raw photos in the current
    directory."""
    the_raws = sorted(fu.list_of_raws())
    if the_raws:
        print("\nCreating HDR JPEGs (and intermediate scripts) from %d raw files ...\n\n" % len(the_raws))
        for which_raw in the_raws:
            hfr.HDR_tonemap_from_raw(which_raw)

def hang_around():
    """Offers to hang around, watching for executable shell scripts in the
    directory and running them if they appear. This might be handy if, for
    instance, all of the shell scripts had been accidentally deleted: this
    script can be left running while the files in the directory are manually
    examined and new shell scripts are created (perhaps by running
    create_HDR_script.py). Note that this will have to be interrupted with Ctrl+C;
    it will otherwise just run forever, waiting.

    This routine DOES NOT REQUIRE that filename mappings have been read into
    memory; it just runs all the executable shell scripts in the current
    directory.
    """
    while True:
        print('Looking for executable shell scripts at %s...' % (datetime.datetime.now().isoformat()))
        file_list = [which_script for which_script in glob.glob("*SH") if os.access(which_script, os.X_OK, effective_ids=True)]
        if len(file_list) > 0:
            print('Found %d script(s); executing ...' % len(file_list))
            run_shell_scripts()
        else:
            time.sleep(30)

# OK, let's go
if __name__ == "__main__":

    if force_debug:
        # Whatever statements actually need to be run in an IDE go here.
        os.chdir('/home/patrick/Photos/2017-09-30')
        # sys.exit()

    if len(sys.argv) > 1:
        if sys.argv[1] == '--help' or sys.argv[1] == '-h':
            print_usage()
            sys.exit(0)
        elif sys.argv[1] == '--pythonhelp':
            python_help()
            sys.exit(0)
        else:               # There should be no command-line arguments other than those we just processed.
            print_usage()
            sys.exit(1)

    if input('\nDo you want to postprocess the directory %s?  ' % os.getcwd())[0].lower() != 'y':
        print('\n\nREMEMBER: this script only works on the current working directory.\n')
        sys.exit(1)

    try:        # Read existing filename mappings if there are any.
        file_name_mappings.read_mappings('file_names.csv')
    except OSError:
        pass
    empty_thumbnails()
    delete_spurious_raw_files()
    rename_photos()
    create_HDRs_from_raws()
    rotate_photos()
    process_shell_scripts()
    run_shell_scripts()
    if input("Want me to hang around and run scripts that show up? (Say NO if unsure.) --|  ").strip().lower()[0] == "y":
        print('\n\nOK, hit ctrl-C when finished.\n')
        hang_around()
   # We're done!
