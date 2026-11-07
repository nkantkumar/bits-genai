import json

from pydantic import BaseModel, ValidationError


def validate_output(
    output: str,
    schema: type[BaseModel]
):
    """
    Parse the LLM response as JSON and validate
    it against the task-specific Pydantic schema.
    """

    # ========================================================
    # Step 1: Parse JSON
    # ========================================================

    try:

        parsed_output = json.loads(output)

    except json.JSONDecodeError as e:

        raise ValueError(
            f"Invalid JSON output: {e}"
        )


    # ========================================================
    # Step 2: Validate JSON structure with Pydantic
    # ========================================================

    try:

        validated_output = schema.model_validate(
            parsed_output
        )

    except ValidationError as e:

        raise ValueError(
            f"Output schema validation failed: {e}"
        )


    # ========================================================
    # Step 3: Return validated Pydantic object
    # ========================================================

    return validated_output