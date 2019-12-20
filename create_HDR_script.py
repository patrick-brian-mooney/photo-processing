#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Usage:

    ./create_HDR_script FIRST-FILENAME

This script takes one argument, the name of the first file to be used in an HDR
enfuse script. The bash scripts produced by this script are similar to the
re-written Magic Lantern scripts produced by my postprocess-photos.py script.

This program comes with ABSOLUTELY NO WARRANTY. Use at your own risk.

This program is part of Patrick Mooney's photo postprocessing scripts; the
complete set can be found at https://github.com/patrick-brian-mooney/photo-processing.
All programs in that collection are copyright 2015-2019 by Patrick Mooney; they
are free software released under the GNU GPL, either version 3 or (at your
option) any later version. See the file LICENSE.md for details.

The latest version of these scripts can always be found at
    https://github.com/patrick-brian-mooney/photo-processing
"""

import glob, os, shlex, shutil, sys


total_number_of_files = 5   # Total number of input files that are referenced in the auto-generated enfuse script
debugging = False           # Be chatty about what's going on?


def print_usage(exit_value=0):
    """Print a usage message."""
    print(__doc__)
    sys.exit(exit_value)


def create_script_from_file_list(HDR_input_files,
                                 file_to_move=None,
                                 file_to_delete=None,
                                 metadata_source_file=None,
                                 delete_originals=False,
                                 suppress_align=False):
    """This function creates an enfuse HDR script from a list of files on which the
    script will operate. Note that this function does not run the script.

    If FILE_TO_MOVE is not None, that file is moved into the old_scripts directory
    after a successful script creation. If FILE_TO_DELETE is not None, that file is
    deleted after a successful script creation.

    If METADATA_SOURCE_FILE is not None, the resulting script will attempt to use
    exiftool to copy metadata from that file to the script's final product.

    The parameter DELETE_ORIGINALS controls what the script, when run, does, if
    successful. If delete_originals is True, the files that have been blended into
    the tonemapped file are deleted; otherwise, they're moved into a subfolder
    called HDR_components/. By default, they're moved, not deleted.

    If SUPPRESS_ALIGN is True, the generated script does not make any attempt to
    align the images it's processing. This might be useful if, for instance, all
    of the images are already aligned.
    """
    output_file = os.path.splitext(HDR_input_files[0])[0].strip().lstrip('HDR_AIS_').strip() + "_HDR.TIFF"
    wdir = os.path.split(os.path.realpath(HDR_input_files[0]))[0]

    the_script = """#!/usr/bin/env bash

# %s from %s ... %s, %s
# This script written by Patrick Mooney's create_HDR_script.py script, see
#     https://github.com/patrick-brian-mooney/photo-processing/

OLDDIR=$(pwd)
cd %s
""" % (output_file, HDR_input_files[0], HDR_input_files[-1],
       "assuming pre-aligned images" if (suppress_align) else "aligning first",
       shlex.quote(wdir))

    if not suppress_align:
        the_script += "\nalign_image_stack -xyzdivv -a HDR_AIS %s" % ' '.join([shlex.quote(f) for f in HDR_input_files])

    the_script += "\nenfuse --output=%s HDR_AIS*tif" % (shlex.quote(output_file))
    the_script += "\nconvert %s -quality 98 %s" % (shlex.quote(output_file), shlex.quote(os.path.splitext(output_file)[0] + ".JPG"))
    the_script += "\nrm %s\n\n" % shlex.quote(output_file)

    if metadata_source_file:
        the_script += "exiftool -tagsfromfile %s %s\n" % (shlex.quote(metadata_source_file), shlex.quote(os.path.splitext(output_file)[0] + ".JPG"))
        the_script += """exiftool -n -Orientation=1 %s       # Output of CONVERT is already oriented; correct the JPG orientation\n""" % (shlex.quote(os.path.splitext(output_file)[0] + ".JPG"))
        the_script += "rm *_original\n"

    if delete_originals:
        the_script += "\nrm %s" % ' '.join([shlex.quote(f) for f in HDR_input_files])
    else:
        the_script += "\nmv %s HDR_components/" % ' '.join([shlex.quote(f) for f in HDR_input_files])

    the_script += "\n\n" + """cd "$OLDDIR" """

    script_file_name = os.path.splitext(output_file)[0] + '.SH'
    with open(script_file_name, mode='w') as script_file:
        script_file.write(''.join(the_script))

    os.chmod(script_file_name, os.stat(script_file_name).st_mode | 0o111)    # or, as they say in Bash, "chmod a+x $SCRIPT_FILE_NAME"

    if file_to_move:
        try:
            if not os.path.exists('old_scripts/'):
                os.mkdir('old_scripts')
            shutil.move(file_to_move, os.path.join(os.getcwd(), 'old_scripts/'))
        except Exception as e:
            print('ERROR: unable to move the old script "%s"' % file_to_move)
            print('    The system said "%s".' % str(e))
    if file_to_delete:
        try:
            os.remove(file_to_delete)
        except Exception as e:
            print('ERROR: unable to delete the old script "%s"' % file_to_delete)
    return script_file_name


def create_script_from_first_file(first_file, num_files=total_number_of_files, file_to_delete=None):
    """This script creates an enfuse HDR script from the first file on the list and,
    optionally, the number of files that sequentially follow the first file that
    should be input files for the enfuse operation.

    To adjust the default number of files to use as inputs to the enfuse operation,
    change the value of the total_number_of_files constant, above.

    FILE_TO_DELETE specifies the name of a file (e.g., an old script, for instance)
    to delete if the creation of the new script is successful.
    """
    oldpath = os.getcwd()
    newdir, first_file = os.path.split(first_file)
    if newdir:
        os.chdir(newdir)

    if debugging:
        print('creating script starting with file "%s."' % first_file)
        print('     current directory is %s.' % os.getcwd())

    files_in_directory = sorted(glob.glob('*jpg') + glob.glob('*JPG'))
    selected_file_position = files_in_directory.index(os.path.split(first_file)[1])
    HDR_input_files = files_in_directory[selected_file_position : selected_file_position + num_files]

    if debugging:
        print('     files in use are: %s' % ' '.join(HDR_input_files))

    create_script_from_file_list(HDR_input_files, file_to_delete=file_to_delete)

    os.chdir(oldpath)



if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == '--help' or sys.argv[1] == '-h':
            print_usage()
    else:
        print("ERROR: You must specify the first file in the sequence.\n")
        print_usage(exit_value=1)

    create_script_from_first_file(sys.argv[1])

