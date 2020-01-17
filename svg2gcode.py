#!/usr/bin/env python3
"""
Take an SVG file and output a gcode equivalent.
"""

import os
import sys
import xml.etree.ElementTree as ET

import settings

from lib import shapes

SVG_TAGS = set(['rect', 'circle', 'ellipse', 'line', 'polyline', 'polygon', 'path'])

class GCode():
    """
    Wrapper round a file that writes GCode
    """
    def __init__(self, filename):
        '''Open the file and write the preamble'''
        self.file = open(filename, 'w')
        self.writeln(settings.preamble)

    def write(self, gcode):
        '''Write a string to the file'''
        self.file.write(gcode)

    def writeln(self, gcode):
        '''Write a string to the file, appending \\n'''
        self.file.write(gcode + '\n')

    def close(self):
        '''Write the postamble and close the file'''
        self.writeln(settings.postamble)
        self.file.close()


def path_to_gcode(path, mtx, scale):
    '''Convert a single svg path to a gcode shape'''

    result = ''
    new_shape = True
    points = shapes.point_generator(path, mtx, settings.smoothness)
    x_curr, y_curr = None, None

    for x, y in points:  # pylint: disable=invalid-name
        if x_curr is None:
            x_curr = scale * x
            y_curr = scale * y
        x_curr = scale*x
        y_curr = scale*y

        if 0 <= x_curr <= settings.bed_max_x and \
            0 <= y_curr <= settings.bed_max_y:
            result += f'G00 X{x_curr} Y{y_curr}\n'
            if new_shape:
                # move to position, put the pen down
                result += f'{settings.PEN_DOWN_CMD}\n'
                new_shape = False
        else:
            debug_log(
                f'\t--POINT OUT OF RANGE: ({x_curr}, {y_curr})'
            )
    return result


def svg_elem_to_gcode(elem, gcode, scale):
    '''Transform an SVG element into gcode'''
    debug_log(f'--Found Elem: {elem}')
    tag_suffix = elem.tag.split('}')[-1]

    # Checks element is valid SVG_TAGS shape
    if tag_suffix in SVG_TAGS:

        debug_log(f'  --Name: {tag_suffix}')

        # Get corresponding class object from 'shapes.py'
        shape_class = getattr(shapes, tag_suffix)
        shape_obj = shape_class(elem)

        debug_log(f'\tClass : {shape_class}')
        debug_log(f'\tObject: {shape_obj}')
        debug_log(f'\tAttrs : {list(elem.items())}')
        debug_log(f'\tTransform: {elem.get("transform")}')

        ############ HERE'S THE MEAT!!! #############
        # Gets the Object path info in one of 2 ways:
        # 1. Reads the <tag>'s 'd' attribute.
        # 2. Reads the SVG_TAGS and generates the path itself.
        d_path = shape_obj.d_path()

        # The *Transformation Matrix* #
        # Specifies something about how curves are approximated
        # Non-essential - a default is used if the method below
        #   returns None.
        mtx = shape_obj.transformation_matrix()

        if d_path:
            gcode.writeln(settings.shape_preamble)
            gcode.writeln(path_to_gcode(d_path, mtx, scale))
            gcode.writeln(settings.shape_postamble)
        else:
            debug_log('\tNO PATH INSTRUCTIONS FOUND!!')
    else:
        debug_log('  --No Name: '+tag_suffix)


def get_scale(root):
    '''Inspect the root SVG element and return the scale factor for the drawing'''
    # Get the Height and Width from the parent svg tag
    width = root.get('width')
    height = root.get('height')
    if width is None or height is None:
        viewbox = root.get('viewBox')
        if viewbox:
            _, _, width, height = viewbox.split()

    if width is None or height is None:
        raise ValueError('Unable to get width or height for the svg')

    # Scale the file appropriately
    # (Will never distort image - always scales evenly)
    # ASSUMES: Y AXIS IS LONG AXIS
    #          X AXIS IS SHORT AXIS
    # i.e. laser cutter is in 'portrait'
    scale_x = settings.bed_max_x / float(width)
    scale_y = settings.bed_max_y / float(height)
    scale = min(scale_x, scale_y)
    if scale > 1:
        scale = 1

    debug_log(f'width: {width}')
    debug_log(f'height: {height}')
    debug_log(f'scale: {scale}')
    debug_log(f'x%: {scale_x}')
    debug_log(f'y%: {scale_y}')
    return scale

def svg_to_gcode(svg_path):
    ''' The main method that converts svg files into gcode files.
        Still incomplete. See tests/start.svg'''

    # Check File Validity
    if not os.path.isfile(svg_path):
        raise ValueError('File \''+svg_path+'\' not found.')

    if not svg_path.endswith('.svg'):
        raise ValueError('File \''+svg_path+'\' is not an SVG file.')

    debug_log('Input File: '+svg_path)

    outdir, input_filename = os.path.split(svg_path)
    outfile = os.path.join(outdir, input_filename.split('.svg')[0] + '.gcode')
    debug_log('Output File: '+outfile)

    # Get the svg Input File
    input_file = open(svg_path, 'r')
    root = ET.parse(input_file).getroot()
    input_file.close()

    scale = get_scale(root)

    gcode = GCode(outfile)
    gcode.writeln(f'G1 F{settings.feed_rate}')

    # Iterate through svg elements
    for elem in root.iter():
        svg_elem_to_gcode(elem, gcode, scale)

    # Write the Result
    gcode.close()


def debug_log(message):
    ''' Simple debugging function. If you don't understand
        something then chuck this frickin everywhere. '''
    if settings.DEBUG:
        print(message)

if __name__ == '__main__':
    svg_to_gcode(os.path.abspath(sys.argv[1]))
