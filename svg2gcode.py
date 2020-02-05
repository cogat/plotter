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

import argparse
parser = argparse.ArgumentParser()
parser.add_argument('svg_filename')
parser.add_argument('--x-size', type=float, help="fit within x mm")
parser.add_argument('--y-size', type=float, help="fit within y mm")
parser.add_argument('--centred', action='store_true', help="centre the image on the bed")
parser.add_argument('--x-offset', type=float, default=0.0, help="move the image right by x mm")
parser.add_argument('--y-offset', type=float, default=0.0, help="move the image up by y mm")

args = parser.parse_args()

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


def path_to_gcode(path, mtx, scale, offset):
    '''Convert a single svg path to a gcode shape'''

    result = ''
    new_shape = True
    points = shapes.point_generator(path, mtx, settings.smoothness)
    x_curr, y_curr = None, None

    for x, y in points:  # pylint: disable=invalid-name
        x_curr = scale * x + offset[0]
        y_curr = scale * y + offset[1]

        if 0 <= x_curr <= settings.bed_max_x and \
            0 <= y_curr <= settings.bed_max_y:
            result += f'G00 X{x_curr} Y{y_curr}\n'
            if new_shape:
                # move to position, put the pen down
                result += f'{settings.PEN_DOWN_CMD}\n'
                new_shape = False
        else:
            print(
                f'\t--POINT OUT OF RANGE: ({x_curr}, {y_curr})'
            )
    return result


def svg_elem_to_gcode(elem, gcode, scale, offset):
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
            if settings.shape_preamble:
                gcode.writeln(settings.shape_preamble)
            gcode.writeln(path_to_gcode(d_path, mtx, scale, offset))
            if settings.shape_postamble:
                gcode.writeln(settings.shape_postamble)
        else:
            debug_log('\tNO PATH INSTRUCTIONS FOUND!!')
    else:
        debug_log('  --No Name: '+tag_suffix)


def get_scale_offset(root):
    '''Inspect the root SVG element and return the scale factor for the drawing'''
    # Get the Height and Width from the parent svg tag
    width = float(root.get('width', '0').rstrip('px'))
    height = float(root.get('height', '0').rstrip('px'))
    if not (width and height):
        viewbox = root.get('viewBox')
        if viewbox:
            _, _, width, height = viewbox.split()

    width = float(width)
    height = float(height)

    if not (width and height):
        raise ValueError('Unable to get width or height for the svg')

    x_size = args.x_size or settings.bed_max_x
    y_size = args.y_size or settings.bed_max_y

    scale_x = x_size / width
    scale_y = y_size / width
    scale = min(scale_x, scale_y)

    print(f'svg width: {width}')
    print(f'svg height: {height}')
    print(f'output max width: {x_size}mm')
    print(f'output max height: {y_size}mm')
    print(f'scale: {scale}')

    if args.centred:
        offset = (
            (-width * scale + settings.bed_max_x) / 2,
            (-height * scale + settings.bed_max_y) / 2
        )
    else:
        offset = (0, 0)
    offset = (offset[0] + args.x_offset, offset[1] + args.y_offset)

    print(f'offset: {offset[0]}, {offset[1]}mm')

    return scale, offset

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

    scale, offset = get_scale_offset(root)

    gcode = GCode(outfile)
    gcode.writeln(f'G01 F{settings.feed_rate}')

    # Iterate through svg elements
    for elem in root.iter():
        svg_elem_to_gcode(elem, gcode, scale, offset)

    # Write the Result
    gcode.close()


def debug_log(message):
    ''' Simple debugging function. If you don't understand
        something then chuck this frickin everywhere. '''
    if settings.DEBUG:
        print(message)

if __name__ == '__main__':
    svg_to_gcode(os.path.abspath(args.svg_filename))