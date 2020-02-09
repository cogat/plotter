from .rect import Rect
from vectormath import Vector2
from math import cos, sin


def rotate(vec, theta):
    '''rotate vector clockwise by theta radians'''
    sintheta = sin(theta)
    costheta = cos(theta)
    return Vector2(
        vec.x * costheta - vec.y * sintheta,
        vec.x * sintheta + vec.y * costheta,
    )