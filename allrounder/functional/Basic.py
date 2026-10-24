transactions = ["txn_001", "txn_002", "txn_003"]
transactions.append("txn_004")  # Add to the end
transactions.pop(0)
print(transactions.pop(0) )
print(len(transactions))


from collections import Counter

actions = ["login", "logout", "login", "purchase", "login"]
counts = Counter(actions)

print(counts["purchase"])

from collections import OrderedDict

# Create an OrderedDict
cache = OrderedDict()
cache["a"] = 1
cache["b"] = 2
cache["c"] = 3

print(cache)

