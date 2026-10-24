from pydantic import BaseModel, ValidationError

class User(BaseModel):
    id: int
    name: str
    is_active: bool = True

# A raw JSON string (e.g., from an API request or message queue)
json_string = '{"id": 123, "name": "Alice"}'

# Parse and validate directly from JSON
user = User.model_validate_json(json_string, strict=True)

print(user)        # id=123 name='Alice' is_active=True
print(type(user.id)) # <class 'int'> (Pydantic automatically coerced "123" to 123)
