#/home/patrick/Documents/programming/python_projects/photo-processing/bin/python3
# -*- coding: utf-8 -*-
"""This quick hack writes a bash script that uses the PTTools to stitch a
panorama from all photos in the current directory. It assumes that all of the
photos are JPEGs in the current directory, and that all of the JPEGs in the
current directory are photos for the panorama. The output scripts written by
this script also make a lot of other assumptions; basically, it automates my
own most common panorama stitching process. It leaves behind a .pto file that
can be modified by hand if the results aren't satisfactory, and in any case,
my experience is that, even with the script getting many things wrong, starting
off automatically with this script is faster overall for large projects than
doing everything manually from the beginning would be.

A short (i.e., non-comprehensive) list of choices the output script makes for
you might include:
    * using CPFind as the control point detector;
    * continuously overwriting the same project file instead of leaving
      multiple project files behind to allow for problem tracing;
    * treating the first file (according to standard lexicographic sort by
      filename) as the reference (or "anchor") image for the purposes of both
      position and exposure, which often winds up not being the best choice;
    * assuming that the input images are taken with a rectilinear lens;
    * running Celeste to remove control points on clouds;
    * running CPFind's version of Celeste instead of Celeste standalone;
    * using the --multirow match detection algorithm, which is generally
      pretty good, but which is not perfect for all possible scenarios, and
      which does unnecessary work in single-row panoramas, sometimes causing
      problems on its own;
    * running CPClean with default parameters;
    * automatically optimizing control points, which is almost certainly a
      good idea in most, but not all, cases;
    * trying to find a suitable projection type, which is often basically
      successful but rarely makes the absolute best possible choice;
    * doing photometric optimization, which wastes time if the shots were
      manually shot at the same exposure;
    * trying to find vertical control points, which is often successful and
      frequently a good idea, though the process can go astray;
    * automatically calculating ostensibly optimal canvas and crop sizes; and
    * using hugin_executor as the stitching program (PTBatchGUI might also be
      used for this purpose).

It also functions as a Python module in which some of these decisions,
including but not limited to which files are used, can be controlled by
changing the parameters passed to the produce_script() function.

This program comes with ABSOLUTELY NO WARRANTY. Use at your own risk.

This program is part of Patrick Mooney's photo postprocessing scripts; the
complete set can be found at https://github.com/patrick-brian-mooney/photo-processing.
All programs in that collection are copyright 2015-2025 by Patrick Mooney; they
are free software released under the GNU GPL, either version 3 or (at your
option) any later version. See the file LICENSE.md for details.

The latest version of these scripts can always be found at
    https://github.com/patrick-brian-mooney/photo-processing
"""


import os
import shlex
import sys

from typing import Sequence
from pathlib import Path


def produce_script(the_files: Sequence[Path]) -> None:
    """Produce the actual script.
    """
    assert isinstance(the_files, Sequence)
    assert len(the_files) > 2, "ERROR! You must specify at least two files to make into a panorama!"
    assert all([isinstance(f, Path) for f in the_files]), "ERROR! FIles passed to produce_script must be Paths!"

    the_files_list = ' '.join([shlex.quote(str(f)) for f in the_files])
    project_file = shlex.quote(str(the_files[0].with_suffix(".pto")))

    if the_files:
        the_script = f"""#!/usr/bin/env bash
# This script written by Patrick Mooney's create_panorama_script.py script, see
#     https://github.com/patrick-brian-mooney/photo-processing/blob/master/create_panorama_script.py
pto_gen -o {project_file} {the_files_list}
"""

        the_script += f"""
cpfind --multirow --celeste -o {project_file} {project_file}
cpclean -o {project_file} {project_file}
linefind -o {project_file} {project_file}
autooptimiser -a -l -s -m -o {project_file} {project_file}
pano_modify --canvas=AUTO --crop=AUTO -o {project_file} {project_file}
# hugin_executor -s {project_file}                              # Uncomment to stitch the panorama immediately
"""

        script_file_name = the_files[0].stem + '-pano.SH'
        with open(script_file_name, mode='w', encoding='utf-8') as script_file:
            script_file.write(''.join(the_script))

        os.chmod(script_file_name, os.stat(script_file_name).st_mode | 0o111)    # `chmod a+x SCRIPT_FILE_NAME`


if __name__ == "__main__":
    files = sorted([f for f in Path().glob('*') if f.suffix.casefold() == '.jpg'])
    if not files:
        print('You must call create_panorama_script.py in a folder with at least one .jpg or .JPG file!')
        print(f'   current working directory is {os.getcwd()}')
        sys.exit(1)

    produce_script(files)
