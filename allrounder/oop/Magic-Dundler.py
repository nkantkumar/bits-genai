class Book:
    def __init__(self, title, pages):
        self.title = title
        self.pages = pages

    # 1. __str__: Called when using print() or str()
    def __str__(self):
        return f"'{self.title}' ({self.pages} pages)"

    # 2. __len__: Called when using len()
    def __len__(self):
        return self.pages

    # 3. __add__: Called when using the + operator to combine two books
    def __add__(self, other):
        # Let's say adding two books combines their page counts
        return self.pages + other.pages


# --- Using the Dunder Methods ---

b1 = Book("Python 101", 300)
b2 = Book("Advanced Algorithms", 500)

# Python automatically calls __str__ behind the scenes:
print(b1)
# Output: 'Python 101' (300 pages)

# Python automatically calls __len__ behind the scenes:
print(len(b1))
# Output: 300

# Python automatically calls __add__ behind the scenes (b1.__add__(b2)):
total_pages = b1 + b2
print(total_pages)
# Output: 800
