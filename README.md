# `photo-processing` collection

<div class="vcard vevent">
<a class="url u-url p-name" rel="me" href="http://patrickbrianmooney.nfshost.com/~patrick/">Patrick Mooney</a><br />
<abbr class="summary description" tile="date of current release">v 0.5</abbr>: <abbr class="dtstart" title='2017-06-05'>5 June 2017</abbr>
</div>

<p>&nbsp;</p>

<p>This is a collection of Python 3.X scripts I use to postprocess photos from the Linux terminal. It depends on a large number of other programs. It's a handy toolbox that does my post-offloading processing automatically; creates <code>bash</code> scripts that (in turn) begin to create panoramas from sets of photos; create tonemapped HDR photos from raw photos or sequences of images shot at different exposures; maintain filename mappings; and provides a quick interface to some utilities that I commonly use while sorting and processing photos.</p>

The external programs required by these scripts are:

<table>
  <tr><th>program name</th><th>package name in Debian Linux</th><th>package version on my system</th></tr>
  <tr><td><code>dcraw</code></td><td>dcraw</td><td>9.19-1.1ubuntu1</td></tr>
  <tr><td><code>cjpeg</code></td><td>libjpeg-turbo-progs</td><td>1.3.0-0ubuntu2</td></tr>
  <tr><td><code>exiftool</code></td><td>libimage-exiftool-perl</td><td>9.46-1</td></tr>
  <tr><td><code>exiftran</code></td><td>exiftran</td><td>2.07-11</td></tr>
  <tr><td><code>luminance-hdr</code></td><td>luminance-hdr</td><td>2.3.0-3build1</td></tr>
  <tr><td><code>convert</code></td><td>imagemagick</td><td>8:6.7.7.10-6ubuntu3.7</td></tr>
  <tr><td><code>enfuse</code></td><td>enfuse</td><td>4.1.2+dfsg-2ubuntu2</td></tr>
  <tr><td><code>align_image_stack</code></td><td>hugin-tools</td><td>2013.0.0+dfsg-1ubuntu2</td></tr>
  <tr><td><code>pto_gen</code></td><td>hugin-tools</td><td>2013.0.0+dfsg-1ubuntu2</td></tr>
  <tr><td><code>cpfind</code></td><td>hugin-tools</td><td>2013.0.0+dfsg-1ubuntu2</td></tr>
  <tr><td><code>cpclean</code></td><td>hugin-tools</td><td>2013.0.0+dfsg-1ubuntu2</td></tr>
  <tr><td><code>linefind</code></td><td>hugin-tools</td><td>2013.0.0+dfsg-1ubuntu2</td></tr>
  <tr><td><code>autooptimiser</code></td><td>hugin-tools</td><td>2013.0.0+dfsg-1ubuntu2</td></tr>
  <tr><td><code>pano_modify</code></td><td>hugin-tools</td><td>2013.0.0+dfsg-1ubuntu2</td></tr>
  <tr><td><code>hugin_executor</code></td><td>?</td><td>?</td></tr>
</table>

There are also several Python modules outside of the standard library required by these scripts:

<ul>
  <li><code><a rel="muse" href="https://pypi.python.org/pypi/ExifRead">exifread</a></code></li> (or install with <code>[sudo] pip[3] [-U] install exifread</code>)</li>
  <li><code><a rel="muse" href="https://python-pillow.org/">pillow</a></code></li> (or install with <code>[sudo] pip[3] [-U] install Pillow</code>)</li>
  <li><code><a rel="muse" href="https://docs.python.org/3/library/tkinter.html">tkinter</a></code> (which is almost, but not quite, standard)</li>
  <li><code><a rel="me" href="https://github.com/patrick-brian-mooney/python-personal-library/blob/master/patrick_logger.py">patrick_logger</a></code> and <code><a href="">text_handling</a></code> from <a rel="me" href="https://github.com/patrick-brian-mooney/python-personal-library/blob/master/text_handling.py">my personal library</a>.</li>
</ul>

Use of these scripts presupposes some familiarity with Linux, Python 3, and (at least the graphical interfaces to) the command-line programs involved.

Contents of this directory:

* `create_HDR_script.py`: A quick command-line utility to create an enfuse HDR script from the name of the first of five lexicographically sequentially named JPEG photos. It does not actually run the script. It also contains code used by other modules in this unit.
* `create_panorama_script.py`: Creates a `bash` script that creates a PanoTools `.pto` file from all of the JPEG files in the current directory. It does not run the created script itself. The created panorama will most probably be suboptimal in *some substantial way*; this is a first step that automates some of the work but rarely produces a finished overall product.
* `file_mappings.py`: Contains code used by other scripts in the unit to maintain the list of file mappings. Not particularly useful from the command line.
* `HDR_from_all.py`: A convenience script that, when run, creates an enfuse HDR script for all the JPEG files in the current directory. 
* `HDR_from_raw.py`: Creates an HDR tonemap from raw photo files. Makes some attempt to make good choices about how to tonemap the raws. 
* `postprocess_photos.py`: Takes a collection of photos in a folder that have been dumped from various photo-creation devices and converts them into a "normalized" form. Among other actions, this means the photos are renamed based on timestamp, auto-rotated to the ostensibly correct orientation, and tonemaps HDR photos based on Magic Lantern scripts (which it rewrites) or from raw photos. Try running `./postprocess-photos.py --help` from a terminal for more information.
* `quick_utils.py`: contains a GUI exposing various convenience functions that can be registered as an "editor" for GUI photo-viewing clients that support sending filenames to "external editors."
* `README.md`: this file that you're reading right now.

All of the code in this project is licensed under the GNU GPL, either version 3 or (at your option) any later version. See the file <a rel="muse" href="https://github.com/patrick-brian-mooney/photo-processing/blob/master/LICENSE.md">LICENSE.md</a> for more information.

There will hopefully be a series of write-ups later about how I use this series of scripts, but for now, here's my postprocessing workflow:

1. I copy photos onto my hard drive from my memory cards and from all devices that captured photos, and do any necessary time adjustments from a terminal, then immediately produce a backup of all photos by force-starting my (normally automatic) nightly backup process.
   * Manual time adjustment is usually necessary for some photos if I cross a time zone boundary: I keep my camera permanently in my home time zone and treat my home time zone as the "real" time of all photos throughout a trip. This ensures that all photos constitute selections, in order, of a continuous narrative of any trip or activity they document or describe or record.
   * However, my phone and tablet automatically adjust their times to local time when I cross a time zone boundary based on their network interactions, and it's easier to adjust the timestamps on that fraction of photos later than to try to prevent the phone and tablet from adjusting, so I just do that; usually I'll import `postprocess_photos` into a Python terminal and then use its functions `spring_forward()` or `fall_back()`; but they're just convenience wrappers for `exiftool`, which I sometimes just use directly.
   * Forgetting to adjust the timestamps of photos from my phone is the biggest regular pain in my ass from my postprocessing procedure. 
2. I run `postprocess_photos.py`, which does three primary things:
   * It renames all of the photos according to their timestamps (which is why timestamps need to be already adjusted)
   * It processes any necessary HDR tonemaps that should be created from data on the camera, by both ...
     a. identifying HDR-creation scripts written by Magic Lantern, and re-writing and then running those scripts; and
     b. attempting to automatically create tonemaps from any raw camera photos. 
   * It rotates each of the JPEGs to what the camera's EXIF information suggests is the appropriate orientation for it.
3. I then go through the processed photos visually in a viewer (I myself prefer an GQView's old version, 2.0.4), and making any other adjustments necessary. Typically, the adjustments include:
   * deletion of shots with absolutely no merit, or of most copies of very-near-duplicate shots: typically around 10% of total photos from a collection.
   * rotation correction in the rare case that the camera guessed wrong.
   * reduction in size for photos that have no artistic merit, but merely record information that is recorded perfectly well when the photo recording it has a lower resolution.
   * adjusting parameters in HDR-creation scripts and re-running them, or re-creating HDR scripts from scratch by running `create_HDR_script.py`.
   * copying photo sequences that constitute groupings to be stitched into panoramas into a folder where they wait to have `create_panorama_script.py` run over them.
   * copying photos to be uploaded to Flickr or Tumblr into folders for those purposes.
   * copying photos that may eventually be posted to DeviantArt to a `to be processed` folder.
4. I re-run any scripts that need to be re-run as a result of step 3, if this has not already happened concurrently during step 3.
5. Eventually, the panorama scripts created by `create_panorama.py` get run, usually on a separate laptop, and either the results are copied into the `to be processed` folder, or the intermediate panorama files are adjusted and set to run through again, or else new scripts are run to re-create the panorama projects before they are set to run through again, or the project as a whole is declared not to be worth processing and deleted.
6. Photos are drawn out of the appropriate folders and uploaded to Flickr and, occasionally, various other places.
7. Photos pop out of the `to be processed` folder periodically and are processed, then are uploaded to my DeviantArt gallery. 

Known Problems
--------------

* There's still more tweaking to be done on detecting which automatically produced exposures should be included in the HDR photos created by `HDR_from_raw.py`: currently (18 September 2017) my suspicion is that another exposure (or perhaps two) should be dropped from the darkest end of the spectrum, but there's more experimenting to be done first.