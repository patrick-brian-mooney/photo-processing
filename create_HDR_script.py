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

import glob
import os
import shlex
import shutil
import sys

from pathlib import Path
from typing import Optional, Sequence


DEFAULT_NUM_ENFUSE_FILES = 5   # Total number of input files that are referenced in the auto-generated enfuse script
debugging = False           # Be chatty about what's going on?


def print_usage(exit_value: int = 0):
    """Print a usage message."""
    print(__doc__)
    sys.exit(exit_value)


def create_script_from_file_list(hdr_input_files: Sequence[Path],
                                 to_move: Optional[Path] = None,
                                 to_delete: Optional[Path] = None,
                                 metadata_source: Optional[Path] = None,
                                 delete_originals: bool = False,
                                 suppress_align: bool = False) -> Path:
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
    the images are already aligned.
    """
    assert isinstance(hdr_input_files, Sequence)
    assert all([isinstance(f, Path) for f in hdr_input_files]), "ERROR! All files passed to create_script_from_file_list must be Paths!"
    assert to_move is None or isinstance(to_move, Path), "ERROR! File TO_MOVE specified was not a Path!"
    assert to_delete is None or isinstance(to_delete, Path), "ERROR! File TO_DELETE specified was not a Path!"
    assert metadata_source is None or isinstance(metadata_source, Path), "ERROR! METADATA_SOURCE is not a Path!"

    if not metadata_source:                        # If no metadata source specified, default to using the first
        metadata_source = hdr_input_files[0]       # file in the list, assuming that's better than nothing.
    if hdr_input_files[0].name.casefold().strip().startswith('hdr_ais_'):
        idx = hdr_input_files[0].name.casefold().find('hdr_ais_') + len('hdr_ais_')
    else:
        idx = 0
    output_file = Path(hdr_input_files[0].stem[idx:].strip() + "_HDR.TIFF")
    wdir = output_file.parent

    method_comment = "assuming pre-aligned images" if suppress_align else "aligning first"
    the_script = f"""#!/usr/bin/env bash

# {output_file} from {hdr_input_files[0]} ... {hdr_input_files[-1]}, {method_comment}
# This script written by Patrick Mooney's create_hdr_script.py script, see
#     https://github.com/patrick-brian-mooney/photo-processing/

OLDDIR=$(pwd)
cd {shlex.quote(str(wdir))}
"""

    if not suppress_align:
        the_script += (f"\nalign_image_stack -xyzdivv -a HDR_AIS "
                       f"{' '.join([shlex.quote(str(f)) for f in hdr_input_files])}")

    the_script += f"\nenfuse --output={shlex.quote(str(output_file))} HDR_AIS*tif"
    the_script += (f"\nconvert {shlex.quote(str(output_file))} -quality 98 "
                   f"{shlex.quote(str(output_file.with_suffix('.JPG')))}")
    the_script += f"\nrm {shlex.quote(str(output_file))}\n\n"

    if metadata_source:
        the_script += (f"exiftool -tagsfromfile {shlex.quote(str(metadata_source))} "
                       f"{shlex.quote(str(output_file.with_suffix('.JPG')))}\n")
        the_script += (f"exiftool -n -Orientation=1 {shlex.quote(str(output_file.with_suffix('.JPG')))}       "
                       f"# Output of CONVERT is already oriented; correct the JPG orientation\n")
        the_script += "rm *_original\n"
    else:
        print("No metadata source file specified! Not attempting to copy metadata ...")
        the_script += "\n# No metadata file specified when script was created. Not copying metadata.\n"

    if delete_originals:
        the_script += f"\nrm {' '.join([shlex.quote(str(f)) for f in hdr_input_files])}"
    else:
        the_script += f"\nmv {' '.join([shlex.quote(str(f)) for f in hdr_input_files])} HDR_components/"

    the_script += '\n\ncd "$OLDDIR"'

    script_file_name = output_file.with_suffix('.SH')
    with open(script_file_name, mode='w', encoding='utf-8') as script_file:
        script_file.write(''.join(the_script))

    os.chmod(script_file_name, os.stat(script_file_name).st_mode | 0o111)    # `chmod a+x $SCRIPT_FILE_NAME`

    if to_move:
        try:
            if not Path('old_scripts/').exists():
                os.mkdir('old_scripts')
            shutil.move(to_move, os.path.join(os.getcwd(), 'old_scripts/'))
        except Exception as e:
            print(f'ERROR: unable to move the old script "{to_move}"')
            print(f'    The system said: {e}".')
    if to_delete:
        try:
            os.remove(to_delete)
        except Exception as e:
            print('ERROR: unable to delete the old script "%s"' % to_delete)
    return script_file_name


def create_script_from_first_file(first_file: Path,
                                  num_files: int = DEFAULT_NUM_ENFUSE_FILES,
                                  file_to_delete: Optional[Path] = None) -> None:
    """This script creates an enfuse HDR script from the first file on the list and,
    optionally, the number of files that sequentially follow the first file that
    should be input files for the enfuse operation.

    To adjust the default number of files to use as inputs to the enfuse operation,
    change the value of the DEFAULT_NUM_ENFUSE_FILES constant, above.

    FILE_TO_DELETE specifies the name of a file (e.g., an old script, for instance)
    to delete if the creation of the new script is successful.
    """
    assert isinstance(first_file, Path), "ERROR! FIRST_FILE must be a Path!"

    oldpath = os.getcwd()
    try:
        newdir = first_file.parent
        if newdir:
            os.chdir(newdir)

        if debugging:
            print(f'creating script starting with file "{first_file}."')
            print(f'     current directory is {os.getcwd()}.')

        files_in_directory = sorted([f for f in Path().glob('*') if f.suffix.casefold() == ".jpg"])
        selected_file_position = files_in_directory.index(first_file[1])
        HDR_input_files = files_in_directory[selected_file_position : selected_file_position + num_files]

        if debugging:
            print('     files in use are: %s' % ' '.join([str(f) for f in HDR_input_files]))

        create_script_from_file_list(HDR_input_files, to_delete=file_to_delete)

    finally:
        os.chdir(oldpath)


force_debug = False

if __name__ == "__main__":
    if force_debug:
        import glob
        os.chdir('/home/patrick/Photos/2020-09-21/HDR_components')
        files = glob.glob('*jpg')
        assert (len(files) % 3) == 0
        for one, two, three in zip(*[iter(files)]*3):
            create_script_from_file_list([one, two, three], metadata_source=one, )
        sys.exit()
    if len(sys.argv) > 1:
        if sys.argv[1] == '--help' or sys.argv[1] == '-h':
            print_usage()
    else:
        print("ERROR: You must specify the first file in the sequence.\n")
        print_usage(exit_value=1)

    create_script_from_first_file(sys.argv[1])

