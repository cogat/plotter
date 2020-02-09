#!/usr/bin/env python3
"""
Take an SVG file and output a gcode equivalent.
"""

import os
import sys
import xml.etree.ElementTree as ET
import importlib
from lib import shapes

SVG_TAGS = set(['rect', 'circle', 'ellipse', 'line', 'polyline', 'polygon', 'path'])

import argparse
parser = argparse.ArgumentParser(description='Take an svg input and convert to gcode commands, '
    'using the parameters set in settings.py. By default the input will be maximised in size and '
    'centered in the work area.'
)
parser.add_argument('svg_path')
parser.add_argument('--settings', default='settings', help="use the settings for a particular machine")

parser.add_argument('--position-at-origin', action='store_true', help="position the lower left corner of the output at the corner of the work area")
parser.add_argument('--x-offset', type=float, default=0.0, help="move the output right by x mm")
parser.add_argument('--y-offset', type=float, default=0.0, help="move the output up by y mm")

parser.add_argument('--x-size', type=float, help="set the x size of the output in mm (cannot be bigger than the work area)")
parser.add_argument('--y-size', type=float, help="set the y size of the output in mm (cannot be bigger than the work area)")


class GCodeFile():
    """
    Wrapper round a file that writes GCode
    """
    def __init__(self, filename, settings):
        '''Open the file and write the preamble'''
        self.settings = settings
        self.file = open(filename, 'w')
        self.writeln(self.settings.preamble)
        self.writeln(f'G01 F{self.settings.feed_rate}')

    def write(self, gcode):
        '''Write a string to the file'''
        self.file.write(gcode)

    def writeln(self, gcode):
        '''Write a string to the file, appending \\n'''
        self.file.write(gcode + '\n')

    def close(self):
        '''Write the postamble and close the file'''
        self.writeln(self.settings.postamble)
        self.file.close()


class SVG2GCodeConverter():
    def __init__(
        self,
        settings,
        svg_path,
        gcode_path,
        position_at_origin,
        x_offset,
        y_offset,
        x_size,
        y_size,
    ):

        # Check File Validity
        if not os.path.isfile(svg_path):
            raise ValueError('File \''+svg_path+'\' not found.')

        if not svg_path.endswith('.svg'):
            raise ValueError('File \''+svg_path+'\' is not an SVG file.')

        self.settings = settings
        self.svg_path = svg_path
        self.gcode_path = gcode_path
        self.position_at_origin = position_at_origin
        self.x_offset = x_offset
        self.y_offset = y_offset
        self.x_size = max(x_size or self.settings.bed_area_mm[0], self.settings.bed_area_mm[0])
        self.y_size = max(y_size or self.settings.bed_area_mm[1], self.settings.bed_area_mm[1])

        self.scale = None
        self.offset = None

    def path_to_gcode(self, path, mtx):
        '''Convert a single svg path to a gcode shape'''

        result = ''
        new_shape = True
        points = shapes.point_generator(path, mtx, self.settings.smoothness)
        x_curr, y_curr = None, None

        for x, y in points:  # pylint: disable=invalid-name
            x_curr = self.scale * x + self.offset[0]
            y_curr = self.scale * y + self.offset[1]

            # reflect y about the output centre (y_size / 2 + y_offset)
            reflection_line = self.y_size / 2.0 # TODO: incorporate y_offset...
            y_dist = reflection_line - y_curr
            y_curr += 2 * y_dist

            if 0 <= x_curr <= self.settings.bed_area_mm[0] and \
                0 <= y_curr <= self.settings.bed_area_mm[1]:
                result += f'G01 X{x_curr} Y{y_curr}\n'
                if new_shape:
                    # move to position, put the pen down
                    result += f'{self.settings.TOOL_ON_CMD}\n'
                    new_shape = False
            else:
                print(f'\t--POINT OUT OF RANGE: ({x_curr}, {y_curr})')
                # sys.exit(1)
        return result

    def svg_elem_to_gcode(self, elem):
        '''Transform an SVG element into gcode'''
        self.debug_log(f'--Found Elem: {elem}')
        tag_suffix = elem.tag.split('}')[-1]

        # Checks element is valid SVG_TAGS shape
        if tag_suffix not in SVG_TAGS:
            self.debug_log('  --No Name: '+tag_suffix)
            return

        self.debug_log(f'  --Name: {tag_suffix}')

        # Get corresponding class object from 'shapes.py'
        shape_class = getattr(shapes, tag_suffix)
        shape_obj = shape_class(elem)

        self.debug_log(f'\tClass : {shape_class}')
        self.debug_log(f'\tObject: {shape_obj}')
        self.debug_log(f'\tAttrs : {list(elem.items())}')
        self.debug_log(f'\tTransform: {elem.get("transform")}')

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
            if self.settings.shape_preamble:
                self.gcode_file.writeln(self.settings.shape_preamble)
            self.gcode_file.writeln(self.path_to_gcode(d_path, mtx))
            if self.settings.shape_postamble:
                self.gcode_file.writeln(self.settings.shape_postamble)
        else:
            self.debug_log('\tNO PATH INSTRUCTIONS FOUND!!')            

    def _get_minmax(self, elem):
        elem_min = (float('inf'), float('inf'))
        elem_max = (float('-inf'), float('-inf'))

        tag_suffix = elem.tag.split('}')[-1]
        if tag_suffix not in SVG_TAGS:
            return elem_min, elem_max

        shape_class = getattr(shapes, tag_suffix)
        shape_obj = shape_class(elem)
        path = shape_obj.d_path()
        mtx = shape_obj.transformation_matrix()
        if path:
            points = shapes.point_generator(path, mtx, self.settings.smoothness)
            for point in points:
                elem_min = (min(elem_min[0], point[0]), min(elem_min[1], point[1]))
                elem_max = (max(elem_max[0], point[0]), max(elem_max[1], point[1]))

        return elem_min, elem_max
            

    def _get_scale_offset(self, root):
        '''Inspect the SVG and return the scale factor and offset for the drawing.
        To apply, take SVG, multply svg coord by scale factor, then add the offset.
        '''

        in_min = (float('inf'), float('inf'))
        in_max = (float('-inf'), float('-inf'))

        for elem in root.iter():
            elem_min, elem_max = self._get_minmax(elem)
            in_min = (min(elem_min[0], in_min[0]), min(elem_min[1], in_min[1]))
            in_max = (max(elem_max[0], in_max[0]), max(elem_max[1], in_max[1]))

        print(f'input (svg) extents: {in_min[0]:.2f}, {in_min[1]:.2f} -> {in_max[0]:.2f}, {in_max[1]:.2f}')

        work_size = in_max[0] - in_min[0], in_max[1] - in_min[1], 

        scale_x = 1.0 * self.x_size / work_size[0]
        scale_y = 1.0 * self.y_size / work_size[1]
        scale = min(scale_x, scale_y)

        # set offset to user offset
        offset = [
            self.x_offset - in_min[0] * scale, 
            self.y_offset - in_min[1] * scale
        ]

        if not self.position_at_origin:
            # centre in work area
            offset[0] += (self.settings.bed_area_mm[0] - scale * work_size[0]) / 2.0
            offset[1] += (self.settings.bed_area_mm[1] - scale * work_size[1]) / 2.0

        print(f'output (plot area) extents: {in_min[0] * scale + offset[0]:.2f} x {in_min[1] * scale + offset[1]:.2f}mm -> {in_max[0] * scale + offset[0]:.2f} x {in_max[1] * scale + offset[1]:.2f}mm')

        print(f'scale: {scale:.4f}; offset: {offset[0]:.2f} x {offset[1]:.2f}mm')

        return scale, tuple(offset)

    def convert(self):
        ''' The main method that converts svg files into gcode files.
            Still incomplete. See tests/start.svg'''

        # Get the svg Input File
        input_file = open(self.svg_path, 'r')
        root = ET.parse(input_file).getroot()
        input_file.close()

        self.scale, self.offset = self._get_scale_offset(root)
        self.gcode_file = GCodeFile(self.gcode_path, self.settings)

        # Iterate through svg elements
        for elem in root.iter():
            self.svg_elem_to_gcode(elem)

        # Write the Result
        self.gcode_file.close()

    def debug_log(self, message):
        ''' Simple debugging function. If you don't understand
            something then chuck this frickin everywhere. '''
        if self.settings.DEBUG:
            print(message)


if __name__ == '__main__':
    args = parser.parse_args()
    _settings = importlib.import_module(args.settings)
    kwargs = vars(args)
    kwargs['settings'] = _settings
    outdir, input_filename = os.path.split(kwargs['svg_path'])
    gcode_path = os.path.join(outdir, input_filename.split('.svg')[0] + '.gcode')
    print('Output File: ' + gcode_path)
    kwargs['gcode_path'] = gcode_path

    gcode_converter = SVG2GCodeConverter(**kwargs)
    gcode_converter.convert()