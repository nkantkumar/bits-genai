class NullUser:
    name = "Guest"
    email = ""
    is_authenticated = False
class User:
    name = "user"
    email = ""
    is_authenticated = False
def get_current_user() -> User | NullUser:
    user = User
    return user if user is not None else NullUser()

# Callers never worry about AttributeError
user = get_current_user()
print(user.name)
