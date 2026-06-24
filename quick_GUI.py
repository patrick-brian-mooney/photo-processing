#!/usr/bin/env python3
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


import collections
import functools
import os
import subprocess
import sys

from pathlib import Path
from typing import Any, Callable, Generator, Iterable, List, Literal, Optional, Sequence, Tuple, Type, Union

import tkinter as tk
import tkinter.ttk as ttk
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


def _flatten_list(the_list: Iterable[Any]) -> Generator[Any, None, None]:
    """Regardless of how deep the list (or other iterable) L is, yield the non-list (or
    other iterable) atoms that compose L (and its sub-iterables, if any, to any
    depth). No matter how deeply nested L is, the yielded elements list will not
    contain any lists, tuples, or other iterables, but only the atoms of those lists.

    For purposes of the above paragraph, strings (and bytes objects) are considered
    to be elements, not iterables.

    Note that this actually returns a generator expression, not a list; the
    similarly named convenience wrapper flatten_list, below, may be a better choice
    if an actual list is desired (i.e., usually).
    """
    for elem in the_list:
        if isinstance(elem, collections.abc.Iterable) and not isinstance(elem, (str, bytes)):
            for sub in _flatten_list(elem):
                yield sub
        else:
            yield elem


def flatten_list(the_list: Iterable[Any]) -> Iterable[Any]:
    """Convenience function to wrap _flatten_list and return an actual list. More often
    than not, this is what's desired.
    """
    return list(_flatten_list(the_list))


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


class WrappedCheckbutton(ttk.Checkbutton):
    """Wrapper for the Tk Checkbutton class that automatically creates the necessary
    Tkinter variable to track its state and provides a _getval() method to get its
    state. It also provides a _setval() method to set its state.
    """
    def __init__(self, *pargs, **kwargs):
        assert 'variable' not in kwargs, ("The WrappedCheckbutton constructor cannot take a VARIABLE parameter! Use "
                                          "a standard Tkinter Checkbutton if you want to do that.")
        self.underlying_variable = tk.IntVar()
        ttk.Checkbutton.__init__(self, variable=self.underlying_variable, *pargs, **kwargs)

    def _getval(self) -> bool:
        """Get the value of the widget. Annoyingly, Tkinter widgets don't all have a
        unified name for the routine that gets the current value of the control, and
        though several use .get(), at least one control widget uses that name to mean
        something else, and at least one doesn't have a .get() method at all.
        """
        return bool(self.underlying_variable.get())

    def _setval(self, value: bool = True) -> None:
        """Set the current value of the Checkbutton to True (checked) or False (not
        checked).
        """
        assert isinstance(value, bool)
        self.underlying_variable.set(int(value))


class WrappedCombobox(ttk.Combobox):
    """Just a wrapper for a Combobox widget that consists a consistent interface for use
    with dialog boxes.
    """
    def __init__(self, *pargs,
                 values: Iterable[str],
                 readonly: bool = False,
                 only_num_entry: bool = False,
                 **kwargs):
        assert 'variable' not in kwargs, ("The WrappedCombobox constructor cannot take a VARIABLE parameter! "
                                          "Use a standard Tkinter ttk.Combobox if you want to do that.")
        assert len(values), "Must supply an iterable of options when initializing a WrappedComboxbox!"
        assert all([isinstance(i, str) for i in values]), "Options for a WrappedCombobox must be strings!"

        self.underlying_variable = tk.StringVar()
        ttk.Combobox.__init__(self, textvariable=self.underlying_variable, *pargs, **kwargs)
        self['values'] = tuple(values)
        self._setval(self['values'][1])

        if readonly:
            self.state(["readonly"])
            self.bind('<<ComboboxSelected>>', self.selection_clear)
        elif only_num_entry:
            self.bind('<<ComboboxSelected>>', self._validate_entry)

    def _validate_entry(self, *evt) -> None:
        try:
            arg = int(self._getval())
            if arg <= 1:
                raise TypeError
        except (TypeError,):
            error_message_box("The value must be a positive integer!")
            self._setval(self['values'][0])


    def _getval(self) -> str:
        """Get the value of the widget. Annoyingly, Tkinter widgets don't all have a
        unified name for the routine that gets the current value of the control, and
        though several use .get(), at least one control widget uses that name to mean
        something else, and at least one doesn't have a .get() method at all.
        """
        return self.underlying_variable.get()

    def _setval(self, value: Any) -> None:
        """Set the current value of the Checkbutton to True (checked) or False (not
        checked).
        """
        self.underlying_variable.set(value if isinstance(value, str) else str(value))


class WrappedEntry(ttk.Entry):
    """Just a wrapper for an Entry field that presents a consistent interface for use
    with a DataGetter frame.
    """
    def _getval(self) -> str:
        """Get the value of the widget. Annoyingly, Tkinter widgets don't all have a
        unified name for the routine that gets the current value of the widget, and
        though several use .get(), at least one control widget uses that name to mean
        something else, and at least one doesn't have a .get() method at all.
        """
        return self.get()

    def _setval(self, value: Any) -> None:
        """Set the current text displayed in SELF to be the stringified version of TEXT,
        replacing any text that's already in the widget.
        """
        self.delete(0, tk.END)
        self.insert(0, str(value))


class DateTimeAdjustDialog(tk.Frame):
    """Get a date/time combo from the user. Used in EXIF data-related situations.
    """
    def ret_func(self) -> None:
        """Called when OK is pushed.
        """
        d = {f: self.new_date[f].get() for f in DATE_FIELDS}
        self.callback(int(d['YYYY']), int(d['MO']), int(d["DD"]), int(d['HH']), int(d['MM']), int(d['SS']))
        self._root().destroy()

    def cancel_func(self) -> None:
        """Destroy the window without doing anything else.
        """
        self._root().destroy()

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
        self.option_add('*tearOff', tk.FALSE)

        self.title('Image Processing Options')

        top_label = tk.Label(self, text=f'What would you like to do with these {len(file_list)} files?')
        top_label.grid(column=0, row=0, columnspan=3, sticky=(tk.W, tk.E, tk.S), pady=10)
        self.rowconfigure(0, weight=1)

        adj_rename_btn = tk.Button(self, text="Adjust timestamp(s)", command=self.adjust_timestamp)
        adj_rename_btn.grid(column=0, row=1, columnspan=1, sticky=(tk.W, tk.N, tk.E, tk.S))
        self.timestamp_adj_rename_chk = WrappedCheckbutton(self, text="also rename file(s)")
        self.timestamp_adj_rename_chk.grid(column=1, row=1, columnspan=2, sticky=(tk.W,))

        assign_no_rename_btn = tk.Button(self, text="Assign timestamp(s)",
                                         command=self.set_timestamp)
        assign_no_rename_btn.grid(column=0, row=3, columnspan=1, sticky=(tk.W, tk.N, tk.E, tk.S))
        self.timestamp_ass_rename_chk = WrappedCheckbutton(self, text="also rename file(s)")
        self.timestamp_ass_rename_chk.grid(column=1, row=3, columnspan=2, sticky=(tk.W,))

        del_w_sidecars_btn = tk.Button(self, text="Delete, and delete all sidecars",
                                       command=self.delete_with_alternates)
        del_w_sidecars_btn.grid(column=0, row=6, columnspan=3, sticky=(tk.W, tk.N, tk.E, tk.S))

        resize_label = tk.Label(self, text='\nResize files')
        resize_label.grid(column=0, row=7, columnspan=3, sticky=(tk.W, tk.E, tk.S), pady=10)
        self.rowconfigure(7, weight=1)

        proportional_resize_btn = tk.Button(self, text="Resize to ", command=lambda: self.resize_files(720))
        proportional_resize_btn.grid(column=0, row=8, sticky=(tk.W, tk.N, tk.E, tk.S))
        self.proportional_resize_menu = WrappedCombobox(self, only_num_entry=True,
                                                        values=('480', '720', '1080', '1440', '1920', '2160', '2272',
                                                                '2560', '2848', '4032', '4320', '5184', '6000'))
        tk.Label(self, text=' max. pixels').grid(column=2, row=8, sticky=(tk.S, tk.W, tk.N))

        free_resize_btn = tk.Button(self, text='Free resize ...', command=self.manually_resize)
        free_resize_btn.grid(column=0, row=9, columnspan=3, sticky=(tk.S, tk.W, tk.N, tk.E))

        jpg_transform_label = tk.Label(self, text='\nEXIF-aware JPEG transformations')
        jpg_transform_label.grid(column=0, row=10, columnspan=3, sticky=(tk.W, tk.E, tk.S), pady=10)
        self.rowconfigure(10, weight=1)

        rotate_btn = tk.Button(self, text="Rotate", command=self.exif_rotate)
        rotate_btn.grid(column=0, row=11, columnspan=1, sticky=(tk.W, tk.N, tk.E, tk.S))
        self.rotate_menu = WrappedCombobox(self, values=('automatically', 'clockwise',
                                                                'counterclockwise', '180 degrees'),
                                                        readonly=True)
        self.rotate_menu.grid(column=1, row=11, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S))

        regen_thumb_btn = tk.Button(self, text="Regenerate JPEG thumbnail", command=self.regen_thumb)
        regen_thumb_btn.grid(column=0, row=15, columnspan=3, sticky=(tk.W, tk.N, tk.E, tk.S))

        hdr_label = tk.Label(self, text='\n\nHDR and Panorama Processing')
        hdr_label.grid(column=0, row=16, columnspan=3, sticky=(tk.W, tk.E, tk.S), pady=10)
        self.rowconfigure(16, weight=1)

        hdr_script_all_btn = tk.Button(self, text="Create HDR script for all selected files",
                                       command=self.script_from_files)
        hdr_script_all_btn.grid(column=0, row=17, columnspan=3, sticky=(tk.W, tk.N, tk.E, tk.S))

        hdr_script_from_raw_btn = tk.Button(self, text="Create HDR tonemap script(s) from corresponding raw(s)",
                                            command=self.produce_raw_scripts)
        hdr_script_from_raw_btn.grid(column=0, row=18, columnspan=3, sticky=(tk.W, tk.N, tk.E, tk.S))

        hdr_map_from_raw_btn = tk.Button(self, text="HDR tonemap(s) from (corresponding) raw(s)",
                                         command=self.tonemap_raws)
        hdr_map_from_raw_btn.grid(column=0, row=19, columnspan=3, sticky=(tk.W, tk.N, tk.E, tk.S))

        hdr_to_luminance_btn = tk.Button(self, text="Open (corresponding) raw(s) in Luminance",
                                         command=self.open_in_luminance)
        hdr_to_luminance_btn.grid(column=0, row=20, columnspan=3, sticky=(tk.W, tk.N, tk.E, tk.S))

        pano_script_btn = tk.Button(self, text="Panorama script from all selected files",
                                    command=self.create_pano_script)
        pano_script_btn.grid(column=0, row=21, columnspan=3, sticky=(tk.W, tk.N, tk.E, tk.S))

        self.columnconfigure(1, weight=1)

    @trap_and_report_errors
    def adjust_timestamp(self):
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
            for f in tqdm.tqdm(self.file_list):
                pp.adjust_timestamps([f], yr, mo, days, hr, m, s,
                                     rename=self._root().timestamp_adj_rename_chk._getval())

        dialog = tk.Toplevel()
        tk.Label(self, text='Indicate the amount to adjust each part of the timestamp').pack(side=tk.BOTTOM, expand=tk.YES, fill=tk.X)
        DateTimeAdjustDialog(master=dialog, callback=do_adjust).pack(expand=tk.YES, file=tk.BOTH)
        dialog.grab_set()
        dialog.focus_set()
        dialog.wait_window()
        dialog._root().destroy()

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
            for f in tqdm.tqdm(self.file_list):
                pp.set_timestamps([f], yr, mo, days, hr, m, s,
                                  rename=self._root().timestamp_ass_rename_chk._getval())

        dialog = tk.Toplevel()
        tk.Label(self, text='Set each part of the timestamp').pack(side=tk.BOTTOM, expand=tk.YES, fill=tk.X)
        DateTimeSetDialog(master=dialog, callback=do_adjust).pack()
        dialog.grab_set()
        dialog.focus_set()
        dialog.wait_window()
        dialog._root().destroy()

    @trap_and_report_errors
    def manually_resize(self):
        """Pop up a dialog that asks the user what the EXIF timestamp should be.
        """
        def do_resize(height: int,
                      width: int) -> None:
            """Convenience wrapper that provides a closure to capture outer-scope value.
            """
            for f in tqdm.tqdm(self.file_list):
                subprocess.call([photo_config.executable_location('mogrify'), '-resize',
                                 f'{width}x{height}!', str(f)])

        def do_OK() -> None:
            try:
                width = int(dialog.width_field._getval())
                if width <= 0:
                    raise ValueError
            except (TypeError, ValueError):
                error_message_box(f"{dialog.width_field._getval()} is not a positive integer!")
                return

            try:
                height = int(dialog.height_field._getval())
                if height <= 0:
                    raise ValueError
            except (TypeError, ValueError):
                error_message_box(f"{dialog.height_field._getval()} is not a positive integer!")
                return

            do_resize(height, width)
            dialog._root().destroy()

        def do_cancel() -> None:
            dialog.destroy()

        dialog = tk.Toplevel()

        tk.Label(dialog, text='Width: ').grid(row=0, column=0, sticky=(tk.N, tk.E, tk.S))
        dialog.width_field = WrappedEntry(dialog)
        dialog.width_field.grid(row=0, column=1, columnspan=2, sticky=(tk.E, tk.N, tk.W, tk.S))

        tk.Label(dialog, text='Height: ').grid(row=1, column=0, sticky=(tk.N, tk.E, tk.S))
        dialog.height_field = WrappedEntry(dialog)
        dialog.height_field.grid(row=1, column=1, columnspan=2, sticky=(tk.N, tk.E, tk.S, tk.W))

        tk.Label(dialog, text='\nFile(s) will be resized to exactly the specified\n'
                            'size without regard for aspect ratio\n').grid(row=2, column=0, columnspan=3,
                                                                           sticky=(tk.N, tk.E, tk.S, tk.W))

        tk.Button(dialog, text='Cancel', command=do_cancel).grid(row=3, column=1, sticky=(tk.W, tk.N, tk.E, tk.S))
        tk.Button(dialog, text='OK', command=do_OK).grid(row=3, column=2, sticky=(tk.W, tk.N, tk.E, tk.S))

        dialog.grab_set()
        dialog.focus_set()
        dialog.wait_window()

    @trap_and_report_errors
    def increment_and_rename(self):
        """Bump up the timestamp for each file in FILE_LIST by one hour, then rename
        each file based on the new timestamp.
        """
        log_it(f"INFO: increment_and_rename() called for {len(self.file_list)} files", 2)
        log_it(f"INFO: current directory is {os.getcwd()}", 3)
        log_it(f"INFO: those files are: {self.file_list}", (4 if len(self.file_list) > 4 else 2))

        for f in tqdm.tqdm(self.file_list):
            log_it(f"INFO: incrementing timestamp on '{f}' and renaming", 3)
            pp.increment_timestamp([f])
            # Note that increment_timestamp() will automatically rename the file

        self._root().destroy()

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

        for f in tqdm.tqdm(self.file_list):
            log_it(f"INFO: decrementing timestamp on '{f}' and renaming", 3)
            pp.decrement_timestamp([f])  # decrement_timestamp() will automatically rename the file

        self._root().destroy()

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

        self._root().destroy()

    @trap_and_report_errors
    def resize_files(self):
        """Proportionally resize each file in FILE_LIST so that its longest side is the
        length specified by LONGEST_SIDE.
        """
        longest_side = int(self.proportional_resize_menu._getval())
        for f in tqdm.tqdm(self.file_list):
            subprocess.call([photo_config.executable_location('mogrify'), '-resize',
                             f'{longest_side}x{longest_side}'] + [str(f)])
        self._root().destroy()

    @trap_and_report_errors
    def exif_rotate(self):
        """Rotate each JPEG file in FILE_LIST to the specified ORIENTATION. ORIENTATION
        is a string constant that constitutes a command-line flag to the exiftran
        program.
        """
        orientation = {'automatically': 'a',        # Look up the exiftran argument based on the menu value
                       'clockwise': '9',
                       'counterclockwise': '2',
                       '180 degrees': '1'}[self.rotate_menu._getval()]
        for f in tqdm.tqdm(self.file_list):
            subprocess.call([photo_config.executable_location('exiftran'),
                             f'-{orientation}ig', str(f)])
        self._root().destroy()

    @trap_and_report_errors
    def regen_thumb(self):
        """Regenerate the thumbnail image for a JPEG file.
        """
        for f in tqdm.tqdm(self.file_list):
            subprocess.call([photo_config.executable_location('exiftran'), '-ig', str(f)])
        self._root().destroy()

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

        self._root().destroy()

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

        self._root().destroy()

    @trap_and_report_errors
    def script_from_files(self):
        """Create an HDR script from selected files. This function is just a
        convenience wrapper for an external function.
        """
        cHs.create_script_from_file_list(self.file_list)
        self._root().destroy()

    @trap_and_report_errors
    def open_in_luminance(self):
        """Create an HDR script from selected files. This function is just a
        convenience wrapper for an external function.
        """
        raws = flatten_list([fu.find_alt_version(x, fu.raw_photo_extensions) for x in self.file_list])
        subprocess.call([photo_config.executable_location('luminance-hdr')] + raws)
        self._root().destroy()

    @trap_and_report_errors
    def create_pano_script(self):
        """Creates a default panorama-creation script from the selected files.
        """
        cps.produce_script(self.file_list)
        self._root().destroy()


force_debug = False


@trap_and_report_errors
def startup() -> List[Path]:
    photo_config.startup()              # Check that the system meets minimum requirements; find necessary executables
    if force_debug:
        # import glob
        # sys.argv[1:] = glob.glob('/home/patrick/Photos/2024-11-14/canon/*cr2')
        # sys.argv.append("/home/patrick/Photos/2024-11-14/2024-11-10_13_50_29_1.cr2")
        sys.argv.append("/tmp/13d1b0d6-931b-46ae-9088-f7a22ead1ccd (1).png")

    file_list = sorted([Path(f) for f in sys.argv[1:]], key=str)
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
