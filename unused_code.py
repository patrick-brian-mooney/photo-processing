#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Code that used to be used in older versions of the photo-processing code, but
isn't used any more. Kept here in case it turns out to be useful in the future.
"""

min_brightness_value_spread = 100   # Minimum difference between mix and max for image to feed into HDR sequence
min_top_brightness = 150            # Brightest pixel in dark image must have at least this value for image inclusion.
max_low_brightness = 30             # Darkest pixel in bright image must have at least this value for image inclusion.


def is_left_edge_clipping(histo):
    """Returns True if the histogram HISTO is clipped at the right edge, or False
    otherwise.
    
    Assumes that HISTO is a 256-item brightness histogram.
    """
    return (sum(histo[:63]) > sum(histo[63:]))    

def downwards_moving_approval(image_filename, previous_image_filename=None):
    """Given IMAGE_FILENAME, and assuming that the current goal is to proceed toward
    darker and darker images, seeking the darkest image that should be part of the
    set of variant-exposed images to be tonemapped into a single HDR, this function  
    returns True if the image should be included, and False if it should not be
    included.
    
    "Should be included" here means, more specifically, "no significant right-edge
    histogram clipping, and there is at least one previous image which DOES have
    right-edge clipping." Note that, when this function returns False, the calling
    code assumes that this image is darker than the darkest image that should be
    included, i.e. that we've now found out that the previous image was the lower
    edge of the set that will be tonemapped. That is, this function is intended to
    be called repeatedly until it returns False; after that, the calling code will
    begin to seek the upper edge of the set. 
    """
    if not is_right_edge_clipping(get_smoothed_image_histogram(image_filename)):
        return True if not previous_image_filename else is_right_edge_clipping(get_smoothed_image_histogram(previous_image_filename))

def upwards_moving_approval(image_filename, previous_image_filename):
    """Given IMAGE_FILENAME, and assuming that the current goal is to proceed toward
    lighter and lighter images, seeking the lightest image that should be part of
    the set of variant-exposed images to be tonemapped into a single HDR, this
    function returns True if the image should be included, and False if it should
    not be included.
    
    "Should be included" here means, more specifically, "no significant data in the
    lower quarter of the image's histogram." Note that, when this function returns
    False, the calling code assumes that this image is darker than the darkest
    image that should be included, i.e. that we've now found out that the previous
    image was the lower edge of the set that will be tonemapped. That is, this
    function is intended to be called repeatedly until it returns False; after that,
    the calling code will begin to seek the upper edge of the set. 
    """
    if not right_edge_clipping(get_smoothed_image_histogram(image_filename)):
        return True if not previous_image_filename else is_right_edge_clipping(get_smoothed_image_histogram(previous_image_filename))

def hist_spread(image_filename):
    """Gives the width of the brightness histogram for the image passed in."""
    def spread(N, X):
        return abs(X-N)
    return spread(*Image.open(image_filename).convert('L').getextrema())

def approve_brightness_spread(n, x):
    """Given a brightness spread N, X (which is: miN, maX brightness levels in a
    photo), either returns True (meaning "yes, use the photo as part of the HDR
    tonemapping sequence") or False (meaning "no, do not use the photo as part
    of a tonemapping sequence.")
    """
    log_it("INFO: approve_brightness_spread() called to approve spread (%d, %d)" % (n, x), 3)
    if abs(x-n) < min_brightness_value_spread:  # Is brightness spread large enough?
        log_it("    INFO: brightness spread is too small (%d); rejecting ..." % abs(x-n), 3)
        return False                                # If not, don't use the image.
    elif n == 0:                                # Minimum value is pure black?
        log_it('    minimum brightness value is pure black; maximum value is %d' % x, 3)
        return (x >= min_top_brightness)            # Include the image if its brightest point is bright enough.
    elif x == 255:                              # Maximum value is pure white?
        log_it('    maximum brightness value is pure white; minimum value is %d' % n, 3)
        return (n <= max_low_brightness)            # Include the image if its darkest point is bright enough.
    else:                                       # Image brightness data never reaches pure black or pure white?
        log_it('    no reason to reject; including file ...', 3)
        return True                                 # Include the image.


if __name__ == "__main__":
    print("There's no point in trying to run this script from the terminal.")
