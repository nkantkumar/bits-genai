import sys
from pathlib import Path

# Ensure repository root is on sys.path so common logger can be imported from any working directory
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from common.logger import get_logger

logger = get_logger("bank_account")

class BankAccount:
    def __init__(self, owner, balance=0):
        self.owner = owner
        self.__balance = balance      # private-ish
        logger.info("account_created", owner=self.owner, initial_balance=self.__balance)

    def deposit(self, amount):
        if amount <= 0:
            logger.error("deposit_failed", owner=self.owner, amount=amount, reason="Deposit must be positive")
            raise ValueError("Deposit must be positive")
        self.__balance += amount
        logger.info("deposit_successful", owner=self.owner, amount=amount, new_balance=self.__balance)

    def withdraw(self, amount):
        if amount > self.__balance:
            logger.error("withdrawal_failed", owner=self.owner, amount=amount, current_balance=self.__balance, reason="Insufficient funds")
            raise ValueError("Insufficient funds")
        self.__balance -= amount
        logger.info("withdrawal_successful", owner=self.owner, amount=amount, remaining_balance=self.__balance)

    @property
    def balance(self):
        logger.info("balance_accessed", owner=self.owner, balance=self.__balance)  # read-only access
        return self.__balance

if __name__ == "__main__":
    acct = BankAccount("Alice", 100)
    acct.deposit(50)
    print(f"Current Balance: {acct.balance}")     # 150
    acct.withdraw(30)

    # Demonstrate structured error logging
    try:
        acct.withdraw(500)
    except ValueError:
        pass

    # acct.balance = 999    # AttributeError: can't set (no setter defined)