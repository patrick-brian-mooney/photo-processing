#!/home/patrick/Documents/programming/python_projects/photo-processing/bin/python3
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


import functools
import os
import subprocess
import sys

from pathlib import Path
from typing import Any, Callable, List, Literal, Optional, Sequence, Type, Union

import tkinter as tk
import tkinter.messagebox as tk_msgbox

import tqdm                         # [sudo] pip[3] install tqdm; https://tqdm.github.io/

import patrick_logger               # https://github.com/patrick-brian-mooney/python-personal-library/blob/master/patrick_logger.py
from patrick_logger import log_it

import postprocess_photos as pp
import photo_file_utils as fu
import create_HDR_script as cHs
import HDR_from_raw as Hfr
import create_panorama_script as cps

import photo_config


patrick_logger.verbosity_level = 5


DATE_FIELDS = ('YYYY', 'MO', 'DD', 'HH', 'MM', 'SS')


def error_message_box(explanatory_text: str,
                      system_error: Optional[Union[Type[BaseException], str]] = None) -> None:
    """Show an error message box, reporting the system error as well.
    #FIXME: ugly dialog box.
    """
    if system_error:
        tk_msgbox.showerror('Error', message=explanatory_text, detail=str(system_error))
    else:
        tk_msgbox.showerror("Error", message=explanatory_text)


def trap_and_report_errors(func: Callable) -> Callable:
    """A function decorator for basic error reporting. It runs the FUNC function,
    trapping any uncaught errors and reporting them by popping up a dialog box.

    This is a rough way to report errors, but it's better than nothing.
    """
    @functools.wraps(func)
    def on_call(*args, **kwargs) -> Any:
        try:
            return func(*args, **kwargs)
        except Exception as errrr:
            error_message_box("Unable to complete task!", errrr)
    return on_call


class DateTimeAdjustDialog(tk.Frame):
    """Get a date/time combo from the user. Used in EXIF data-related situations.
    """
    def ret_func(self) -> None:
        """Called when OK is pushed.
        """
        d = {f: self.new_date[f].get() for f in DATE_FIELDS}
        self.callback(int(d['YYYY']), int(d['MO']), int(d["DD"]), int(d['HH']), int(d['MM']), int(d['SS']))
        self.master.destroy()

    def cancel_func(self) -> None:
        """Destroy the window without doing anything else.
        """
        self.master.destroy()

    def __init__(self, master=None, callback=None):
        """We pack bottom-up here so that subclasses can easily add to the top of the
        frame, should they so desire.
        """
        assert callback is not None
        self.new_date = {}
        self.callback = callback
        tk.Frame.__init__(self, master)
        self.pack()

        row = tk.Frame(master)
        tk.Button(row, text="OK", command=self.ret_func).pack(side=tk.RIGHT, expand=tk.YES, fill=tk.X)
        tk.Button(row, text="Cancel", command=self.cancel_func).pack(side=tk.LEFT, expand=tk.YES, fill=tk.X)
        row.pack(side=tk.BOTTOM)
        warning_label = tk.Label(master, text="WARNING: all values must be numeric. No validation is performed!")
        warning_label.pack(side=tk.BOTTOM, expand=tk.YES, fill=tk.X)

        for field in DATE_FIELDS:
            row = tk.Frame(master)
            lab = tk.Label(row, width=5, text=field)
            ent = tk.Entry(row)
            ent.insert(0, "0")
            self.new_date[field] = ent
            row.pack(side=tk.TOP, fill=tk.X)
            lab.pack(side=tk.LEFT)
            ent.pack(side=tk.RIGHT, expand=tk.YES, fill=tk.X)


class DateTimeSetDialog(DateTimeAdjustDialog):
    pass


class MainWindow(tk.Tk):
    """Class representing the main window.
    """
    def __init__(self, file_list: Sequence[Path], *pargs, **kwargs):
        tk.Tk.__init__(self, *pargs, **kwargs)

        assert isinstance(file_list, Sequence), "ERROR! Files passed to MainWindow.__init__() must be in a list!"
        assert file_list, "ERROR! Must pass at least one file to work on!"
        assert all([isinstance(f, Path) for f in file_list])

        self.file_list = file_list

        self.title('Image Processing Options')
        top_label = tk.Label(self, text=f'\nWhat would you like to do with these {len(file_list)} files?\n\n')
        top_label.pack(side=tk.TOP, fill=tk.X)

        tk.Button(self, text="Adjust timestamp(s) and rename",
                  command=self.adjust_timestamp).pack(side=tk.TOP, fill=tk.X)
        tk.Button(self, text="Adjust timestamp(s) without renaming",
                  command=lambda: self.adjust_timestamp(rename=False)).pack(side=tk.TOP, fill=tk.X)
        tk.Button(self, text="Assign timestamp(s) without renaming",
                  command=self.set_timestamp).pack(side=tk.TOP, fill=tk.X)
        tk.Button(self, text="Add 1 hour to timestamp(s) and rename",
                  command=self.increment_and_rename).pack(side=tk.TOP, fill=tk.X)
        tk.Button(self, text="Subtract 1 hour from timestamp(s) and rename",
                  command=self.decrement_and_rename).pack(side=tk.TOP, fill=tk.X)
        tk.Button(self, text="Delete, and delete all sidecars",
                  command=self.delete_with_alternates).pack(side=tk.TOP, fill=tk.X)

        tk.Label(self, text='\n\nResize').pack(side=tk.TOP, fill=tk.X)
        tk.Button(self, text="Resize to 720p",
                  command=lambda: self.resize_files(720)).pack(side=tk.TOP, fill=tk.X)
        tk.Button(self, text="Resize to 1920p",
                  command=lambda: self.resize_files(1920)).pack(side=tk.TOP, fill=tk.X)

        tk.Label(self, text='\n\nEXIF-aware JPEG transformations').pack(side=tk.TOP, fill=tk.X)
        tk.Button(self, text="Rotate automatically",
                  command=lambda: self.exif_rotate("a")).pack(side=tk.TOP, fill=tk.X)
        tk.Button(self, text="Rotate clockwise",
                  command=lambda: self.exif_rotate("9")).pack(side=tk.TOP, fill=tk.X)
        tk.Button(self, text="Rotate counterclockwise",
                  command=lambda: self.exif_rotate("2")).pack(side=tk.TOP, fill=tk.X)
        tk.Button(self, text="Rotate 180 degrees",
                  command=lambda: self.exif_rotate("1")).pack(side=tk.TOP, fill=tk.X)
        tk.Button(self, text="Regenerate JPEG thumbnail",
                  command=self.regen_thumb).pack(side=tk.TOP, fill=tk.X)

        tk.Label(self, text='\n\nHDR and Panorama Processing').pack(side=tk.TOP, fill=tk.X)
        tk.Button(self, text="Create HDR script for all selected files",
                  command=self.script_from_files).pack(side=tk.TOP, fill=tk.X)
        tk.Button(self, text="Create HDR tonemap script(s) from corresponding raw(s)",
                  command=self.produce_raw_scripts).pack(side=tk.TOP, fill=tk.X)
        tk.Button(self, text="HDR tonemap(s) from (corresponding) raw(s)",
                  command=self.tonemap_raws).pack(side=tk.TOP, fill=tk.X)
        tk.Button(self, text="Open (corresponding) raw(s) in Luminance",
                  command=self.open_in_luminance).pack(side=tk.TOP, fill=tk.X)
        tk.Button(self, text="Panorama script from all selected files",
                  command=self.create_pano_script).pack(side=tk.TOP, fill=tk.X)

    @trap_and_report_errors
    def adjust_timestamp(self, rename: bool = True):
        """Pop up a dialog that asks the user by how much to adjust an EXIF timestamp. If
        RENAME is True (the default), the files are renamed based on their new
        timestamps after the timestamps are adjusted.
        """
        def do_adjust(yr: int,
                      mo: int,
                      days: int,
                      hr: int,
                      m: int,
                      s: float) -> None:
            """Convenience wrapper that provides a closure to capture outer-scope values.
            """
            pp.adjust_timestamps(self.file_list, yr, mo, days, hr, m, s, rename=rename)

        # FIXME: we need a text label at the top telling the user what to do.
        dialog = tk.Toplevel()
        DateTimeAdjustDialog(master=dialog, callback=do_adjust).pack()
        dialog.grab_set()
        dialog.focus_set()
        dialog.wait_window()
        sys.exit()

    @trap_and_report_errors
    def set_timestamp(self):
        """Pop up a dialog that asks the user what the EXIF timestamp should be.
        """

        def do_adjust(yr: int,
                      mo: int,
                      days: int,
                      hr: int,
                      m: int,
                      s: float) -> None:
            """Convenience wrapper that provides a closure to capture outer-scope value.
            """
            pp.set_timestamps(self.file_list, yr, mo, days, hr, m, s)

        # FIXME: we need a text label at the top telling the user what to do.
        dialog = tk.Toplevel()
        DateTimeSetDialog(master=dialog, callback=do_adjust).pack()
        dialog.grab_set()
        dialog.focus_set()
        dialog.wait_window()
        sys.exit()

    @trap_and_report_errors
    def increment_and_rename(self):
        """Bump up the timestamp for each file in FILE_LIST by one hour, then rename
        each file based on the new timestamp.
        """
        log_it(f"INFO: increment_and_rename() called for {len(self.file_list)} files", 2)
        log_it(f"INFO: current directory is {os.getcwd()}", 3)
        log_it(f"INFO: those files are: {self.file_list}", (4 if len(self.file_list) > 4 else 2))

        mappings = fu.FilenameMapper()
        mappings.read_mappings(Path('file_names.csv'))

        for f in tqdm.tqdm(self.file_list):
            log_it(f"INFO: incrementing timestamp on '{f}' and renaming", 3)
            pp._increment_timestamp([f])
            # Note that _increment_timestamp() will automatically rename the file

        mappings.write_mappings()
        sys.exit()

    @trap_and_report_errors
    def decrement_and_rename(self):
        """Bump the timestamp down for each file in FILE_LIST, then rename it based on
        the new timestamp. Assumes that all the files in FILE_LIST are in the same
        directory, and assumes that they have a file_names.csv file containing the set
        of filename mappings.
        """
        log_it(f"INFO: decrement_and_rename() called for {len(self.file_list)} files", 2)
        log_it(f"INFO: current directory is {os.getcwd()}", 3)
        log_it(f"INFO: those files are: {self.file_list}", (4 if len(self.file_list) > 4 else 2))

        mappings = fu.FilenameMapper()
        mappings.read_mappings(Path('file_names.csv'))

        for f in tqdm.tqdm(self.file_list):
            log_it(f"INFO: decrementing timestamp on '{f}' and renaming", 3)
            pp._decrement_timestamp([f])  # _decrement_timestamp() will automatically rename the file

        mappings.write_mappings()
        sys.exit()

    @trap_and_report_errors
    def delete_with_alternates(self):
        """Delete the file, with any alternate or paratextual associated files.
        """
        log_it(f"INFO: deleting files and their alternates for {len(self.file_list)} files", 2)
        for f in tqdm.tqdm(self.file_list):
            log_it(f"INFO: deleting {f} and all linked files", 3)
            for ext in sorted(fu.all_alternates):
                if f.with_suffix(ext).exists():
                    f.with_suffix(ext).unlink()
            os.unlink(f)

        sys.exit()

    @trap_and_report_errors
    def resize_files(self, longest_side: int):
        """Proportionally resize each file in FILE_LIST so that its longest side is the
        length specified by LONGEST_SIDE.
        """
        for f in tqdm.tqdm(self.file_list):
            subprocess.call([photo_config.executable_location('mogrify'), '-resize',
                             f'{longest_side}x{longest_side}'] + [str(f)])
        sys.exit()

    @trap_and_report_errors
    def exif_rotate(self, orientation: Literal['a', '9', '2', '1']):
        """Rotate each JPEG file in FILE_LIST to the specified ORIENTATION. ORIENTATION
        is a string constant that constitutes a command-line flag to the exiftran
        program.
        """
        subprocess.call([photo_config.executable_location('exiftran'),
                         f'-{orientation}ig'] + [str(f) for f in self.file_list])
        sys.exit()

    @trap_and_report_errors
    def regen_thumb(self):
        """Regenerate the thumbnail image for a JPEG file.
        """
        subprocess.call([photo_config.executable_location('exiftran'), '-ig'] + [str(f) for f in self.file_list])
        sys.exit()

    @trap_and_report_errors
    def tonemap_raws(self):
        """Create automated tonemaps from the specified raw files.
        """
        log_it(f"INFO: creating {len(self.file_list)} tonemaps from raw files", 2)
        for f in tqdm.tqdm(self.file_list):
            log_it(f"INFO: trying to tonemap {f}", 3)
            raw_file = fu.find_alt_version(f, fu.raw_photo_extensions)
            if raw_file:
                log_it(f"INFO: identified raw photo: {raw_file}", 3)
                Hfr.hdr_tonemap_from_raw(raw_file)

        sys.exit()

    @trap_and_report_errors
    def produce_raw_scripts(self):
        """Produce scripts that will tonemap the raw files, along with the necessary
        files that the script will depend on (e.g., the intermediate renderings at
        various Ev values).

        This function does not, itself, run the scripts.
        """
        log_it(f"INFO: creating {len(self.file_list)} tonemaps from raw files", 2)
        for f in tqdm.tqdm(self.file_list):
            log_it("INFO: trying to tonemap {f}", 3)
            raw_file = fu.find_alt_version(f, fu.raw_photo_extensions)
            if raw_file:
                log_it("INFO: identified raw photo: {raw_file}", 3)
                _ = Hfr.create_hdr_script(raw_file)

        sys.exit()

    @trap_and_report_errors
    def script_from_files(self):
        """Create an HDR script from selected files. This function is just a
        convenience wrapper for an external function.
        """
        cHs.create_script_from_file_list(self.file_list)
        sys.exit()

    @trap_and_report_errors
    def open_in_luminance(self):
        """Create an HDR script from selected files. This function is just a
        convenience wrapper for an external function.
        """
        raws = [fu.find_alt_version(x, fu.raw_photo_extensions) for x in self.file_list]
        subprocess.call([photo_config.executable_location('luminance-hdr')] + raws)
        sys.exit()

    @trap_and_report_errors
    def create_pano_script(self):
        """Creates a default panorama-creation script from the selected files.
        """
        cps.produce_script(self.file_list)
        sys.exit()


force_debug = True


@trap_and_report_errors
def startup() -> List[Path]:
    photo_config.startup()              # Check that the system meets minimum requirements; find necessary executables
    if force_debug:
        import glob
        sys.argv[1:] = glob.glob('/home/patrick/Photos/2024-11-14/canon/*cr2')

    file_list = [Path(f) for f in sys.argv[1:]]
    log_it(f"OK, we're starting, and operating on {len(file_list)} files", 2)
    log_it(f"Those files are: {file_list}", 4)

    if not file_list:
        print("ERROR: You must specify at least one file on which to operate.")
        sys.exit(1)

    base_path = file_list[0].parent
    if base_path:
        os.chdir(base_path)
    for i in file_list:
        if not os.path.samefile(base_path, i.parent):
            print(f"ERROR: file {i} is in a different directory than file {file_list[0]}! Quitting ...")
            sys.exit(1)

    return file_list


if __name__ == "__main__":
    files = startup()       # set up, and get the list of files we're operating on
    win = MainWindow(file_list=files)
    win.mainloop()
