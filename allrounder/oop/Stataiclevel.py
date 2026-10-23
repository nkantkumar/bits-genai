class Pizza:
    def __init__(self, toppings):
        self.toppings = toppings

    @classmethod
    def margherita(cls):              # alternative constructor
        return cls(["tomato", "mozzarella", "basil"])

    @staticmethod
    def is_valid_topping(topping):    # doesn't need self or cls
        return topping in {"tomato", "cheese", "basil", "mozzarella", "ham"}

p = Pizza.margherita()
print(p.toppings)
print(Pizza.is_valid_topping("ham"))  # True