from abc import ABC, abstractmethod

class Shape(ABC):
    @abstractmethod
    def area(self):
        pass

class Circle(Shape):
    def __init__(self, r):
        self.r = r

    def area(self):
        return 3.14159 * self.r ** 2

class Rectangle(Shape):
    def __init__(self, w, h):
        self.w, self.h = w, h

    def area(self):
        return self.w * self.h

# s = Shape()   # TypeError: can't instantiate abstract class
shapes = [Circle(2), Rectangle(3, 4)]
for s in shapes:
    print(f"{type(s).__name__}: {s.area():.2f}")