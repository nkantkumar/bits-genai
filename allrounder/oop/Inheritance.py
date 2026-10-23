class Animal:
    def __init__(self, name):
        self.name = name

    def speak(self):
        return "Some generic sound"

class Dog(Animal):                    # Dog inherits from Animal
    def __init__(self, name, breed):
        super().__init__(name)        # call parent's constructor
        self.breed = breed

    def speak(self):                  # override
        return f"{self.name} says Woof!"

class Cat:
    def speak(self):
        return  "says Meow!"

d = Dog("Rex", "Labrador")
print(d.speak())                      # Rex says Woof!
print(isinstance(d, Animal))

animals = [Dog("rex","lab"), Cat(),Animal("gen")]

for animal in animals:
    print(animal.speak())