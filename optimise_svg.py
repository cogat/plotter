#!/usr/bin/env python3
import argparse
from os.path import splitext

from svgpathtools import svg2paths, wsvg

from penkit_optimize.greedy import greedy_walk
from penkit_optimize.path_graph import PathGraph
from penkit_optimize.svg import load_paths
from penkit_optimize.visualize import visualize_pen_transits
from penkit_optimize.route_util import get_route_from_solution, join_close_paths, cost_of_route
from penkit_optimize.vrp_solver import vrp_solver

DEFAULT_MERGE_THRESHOLD = 1.0


def run_optimizer(input_file, output_file, vis_output, noopt, merge_paths):
    paths, attributes, svg_attributes = svg2paths(input_file, return_svg_attributes=True)

    initial_cost = cost_of_route(paths)
    print('Initial cost: {}'.format(initial_cost))

    if noopt:
        route = paths
    else:
        path_graph = PathGraph(paths)
        greedy_solution = list(greedy_walk(path_graph))
        greedy_route = get_route_from_solution(greedy_solution, path_graph)

        greedy_cost = cost_of_route(greedy_route)
        print('Cost after greedy optimization: {}'.format(greedy_cost))

        route = greedy_route

        if merge_paths is not False:
            if merge_paths is None:
                threshold = DEFAULT_MERGE_THRESHOLD
            else:
                threshold = merge_paths
            print('Routes before merging: {}'.format(len(route)))
            route = join_close_paths(route, threshold)
            print('Routes after merging: {}'.format(len(route)))

    if output_file is None:
        output_file = splitext(input_file)[0] + '-optimized.svg'

    print('Writing results to {}'.format(output_file))

    svg_attributes["debug"] = False

    wsvg(
        route, 
        filename=output_file,
        # margin_size,
        # dimensions,
        # viewbox,
        # attributes = attributes,
        svg_attributes=svg_attributes,
    )

    if vis_output is not None:
        print('Writing visualization to {}'.format(vis_output))
        visualize_pen_transits(route, vis_output)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('input_file')
    parser.add_argument('output_file', nargs='?')
    parser.add_argument('--merge-paths', '-m', nargs='?',
                        type=float, default=False, help='Merge paths that start/end near each other. You may optionally specify a threshold distance (in document units) after this parameter.')
    parser.add_argument(
        '--vis-output', '-v', help='If provided, save a visualization of the path to this SVG file.')
    parser.add_argument('--noopt', '-n', action='store_true',
                        help="Don't run any optimization.")

    args = parser.parse_args()
    run_optimizer(**vars(args))

if __name__ == '__main__':
    main()