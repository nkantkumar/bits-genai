from typing import Optional

# Simulated database of accounts
ACCOUNTS = {
    "acc_101": {"name": "Alice Smith", "balance": 5250.00},
    "acc_102": {"name": "Bob Jones", "balance": 1200.50},
}


def get_account_balance(account_id: str) -> Optional[float]:
    """
    Retrieves the account balance.
    Returns a float if found, or None if the account ID does not exist.
    """
    if account_id in ACCOUNTS:
        return ACCOUNTS[account_id]["balance"]

    # Returning None explicitly requires Optional[float] in the type hint
    return None


def process_withdrawal(account_id: str, amount: float) -> Optional[str]:
    """
    Processes a withdrawal. Returns a confirmation string on success,
    or None if the account cannot be found.
    """
    # 1. Fetch balance (which returns an Optional[float])
    balance = get_account_balance(account_id)

    # 2. Safely handle the None case (Essential when dealing with Optional types!)
    if balance is None:
        return None

    if balance < amount:
        return f"DECLINED: Insufficient funds. Current balance: ${balance}"

    return f"APPROVED: Withdrew ${amount}. Remaining: ${balance - amount}"


# ==========================================
# Execution & Testing
# ==========================================
if __name__ == "__main__":

    # Test Case 1: Valid account ID that exists
    print("--- Test 1: Valid Account ---")
    result_1 = process_withdrawal("acc_101", 250.0)

    if result_1 is not None:
        print(result_1)
    else:
        print("Transaction failed: Account not found.")

    print("\n--- Test 2: Non-Existent Account ---")
    # Test Case 2: Invalid account ID (triggers the Optional None path)
    result_2 = process_withdrawal("acc_999", 100.0)

    if result_2 is not None:
        print(result_2)
    else:
        print("Transaction failed: Account not found.")
