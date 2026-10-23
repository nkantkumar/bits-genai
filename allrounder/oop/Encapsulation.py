class BankAccount:
    def __init__(self, owner, balance=0):
        self.owner = owner
        self.__balance = balance      # private-ish

    def deposit(self, amount):
        if amount <= 0:
            raise ValueError("Deposit must be positive")
        self.__balance += amount

    def withdraw(self, amount):
        if amount > self.__balance:
            raise ValueError("Insufficient funds")
        self.__balance -= amount

    @property
    def balance(self):
        print("hello")# read-only access
        return self.__balance

acct = BankAccount("Alice", 100)
acct.deposit(50)
print(acct.balance)     # 150
# acct.balance = 999    # AttributeError: can't set (no setter defined)