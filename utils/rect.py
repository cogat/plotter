from vectormath import Vector2


class Rect():
    def __init__(self, corner0, corner1):
        self.corner0 = corner0
        self.corner1 = corner1

    @classmethod
    def far_extents(cls):
        'Return a Rect with corners at +/- inf for min-max'
        return cls(
            Vector2(float('inf'), float('inf')),
            Vector2(float('-inf'), float('-inf'))
        )

    def __str__(self):
        return f'{self.corner0} -> {self.corner1}'

    def __repr__(self):
        return f'Rect: {self}'

    @property
    def size(self):
        'Return a Vector2 from one corner to the other'
        return Vector2(self.corner1.x - self.corner0.x, self.corner1.y - self.corner0.y)

    def expand_to(self, vec_or_rect):
        '''
        Return this rectangle expanded to include the passed vector or rectangle
        '''
        if isinstance(vec_or_rect, Rect):
            return Rect(
                self.corner0.clip(max=vec_or_rect.corner0),
                self.corner1.clip(min=vec_or_rect.corner1)
            )
        else:
            return Rect(
                self.corner0.clip(max=vec_or_rect),
                self.corner1.clip(min=vec_or_rect)
            )

    def clip(self, vec0_or_rect, vec1=None):
        '''
        Return this rectangle clipped to another rectangle or vector pair.
        '''
        if vec1 is not None:
            return self.clip(Rect(vec0_or_rect, vec1))
        else:
            return Rect(
                self.corner0.clip(min=vec0_or_rect.corner0),
                self.corner1.clip(max=vec0_or_rect.corner1)
            )

    def __add__(self, other):
        return Rect(self.corner0 + other, self.corner1 + other)

    def __sub__(self, other):
        return Rect(self.corner0 - other, self.corner1 - other)

    def __mul__(self, other):
        return Rect(self.corner0 * other, self.corner1 * other)

    def __truediv__(self, other):
        return Rect(self.corner0 / other, self.corner1 / other)

    def __lt__(self, vec):
        return not self >= vec

    def __le__(self, vec):
        return not self > vec

    def __gt__(self, vec):
        '''Called from rect > vec. Return true if vec is strictly inside this rectangle, false otherwise'''
        return self.corner0.x < vec.x < self.corner1.x and self.corner0.y < vec.y < self.corner1.y
    
    def __ge__(self, vec):
        '''Called from rect >= vec. Return true if the point is inside this rectangle, false otherwise'''
        return self.corner0.x <= vec.x <= self.corner1.x and self.corner0.y <= vec.y <= self.corner1.y

    @property
    def ratio(self):
        size = self.size
        return 1.0 * size.y / size.x


