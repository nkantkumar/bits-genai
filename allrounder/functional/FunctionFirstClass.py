def greet(name):
    return f"Hello, {name}!"

say_hi = greet                 # assign to a variable
print(say_hi("Ana"))           # Hello, Ana!

def apply(func, value):        # pass a function as an argument
    return func(value)

print(apply(str.upper, "python"))   # PYTHON