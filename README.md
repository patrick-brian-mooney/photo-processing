# `photo-processing` collection

<div class="vcard vevent">
<a class="url u-url p-name" rel="me" href="http://patrickbrianmooney.nfshost.com/~patrick/">Patrick Mooney</a><br />
<abbr class="summary description" tile="date of current release">v 0.5</abbr>: <abbr class="dtstart" title='2017-06-05'>5 June 2017</abbr>
</div>

This is a collection of Python 3.X scripts I use to postprocess photos from the Linux terminal. It depends on a large number of other programs; see the docstrings for individual scripts for more information.

Use of these scripts presupposes some familiarity with Linux, Python 3, and (at least the graphical interfaces to) the command-line programs involved. 

There will hopefully be a series of write-ups later about how I use this series of scripts, but for now, here's my postprocessing workflow:

1. I copy photos onto my hard drive from my memory cards and from all devices that captured photos, and do any necessary time adjustments from a terminal, then immediately produce a backup of all photos by force-starting my normal nightly backup process.
   * Manual time adjustment is usually necessary for some photos if I cross a time zone boundary: I keep my camera permanently in my home time zone and treat my home time zone as the "real" time of all photos throughout a trip. This ensures that all photos constitute selections, in order, of a continuous narrative of any trip or activity they document or describe or record.
   * However, my phone and tablet automatically adjust their times to local time when I cross a time zone boundary based on their network interactions, and it's easier to adjust the timestamps on a fraction of photos later than to try to prevent the camera and tablet from adjusting, so I just do that; usually I'll import `postprocess_photos` into a Python terminal and then use its functions `spring_forward()` or `fall_back()`; but they're just convenience wrappers for `exiftool`, which I sometimes just use directly.
   * Forgetting to adjust the timestamps of photos from my phone is the biggest regular pain in my ass from my postprocessing procedure. 
2. I run `postprocess_photos.py`, which does three primary things:
   * It renames all of the photos according to their timestamps (which is why timestamps need to be already adjusted)
   * It processes any necessary HDR tonemaps that should be created from data on the camera, by both ...
     a. identifying HDR-creation scripts written by Magic Lantern, and running those scripts; and
     b. attempting to automatically create tonemaps from any raw camera photos. 
   * It rotates each of the JPEGs to what the camera's EXIF information suggests is the appropriate orientation for it.
3. I then go through the processed photos visually in a viewer (I myself prefer an GQView's old version, 2.0.4), and making any other adjustments necessary. Typically, the adjustments include:
   * deletion of shots with absolutely no merit, or of most copies of very-near duplicate shots: typically around 10% of total photos from a collection.
   * rotation correction in the rare case that the camera guessed wrong.
   * reduction in size for photos that have no artistic merit, but merely record information that is recorded perfectly well when the photo recording it has a lower resolution.
   * adjusting parameters in HDR-creation scripts and re-running them, or re-creating HDR scripts from scratch by running `create_HDR_script.py`.
   * copying photo sequences that constitute groupings to be stitched into panoramas into a folder where they wait to have `create_panorama_script.py`.
   * copying photos to be uploaded to Flickr or Tumblr into folders for those purposes.
   * copying photos that may eventually be posted to DeviantArt to a `to be processed` folder.
4. I re-run any scripts that need to be re-run as a result of step 3, if this has not already happened concurrently during step 3.
5. Eventually, the panorama scripts created by `create_panorama.py` get run, usually on a separate laptop, and either the results are copied into the `to be processed` folder, or the intermediate panorama files are adjusted and set to run through again, or else new scripts are run to re-create the panorama projects before they are set to run through again, or the project as a whole is declared not to be worth processing and deleted.
6. Photos are drawn out of the appropriate folders and uploaded to Flickr and, occasionally, various other places.
7. Photos pop out of the `to be processed` folder periodically and processed, then are uploaded to my DeviantArt gallery. 

