import time


def call_with_retry(
    llm,
    prompt: str,
    max_retries: int
):

    last_error = None

    total_attempts = max_retries + 1

    for attempt in range(total_attempts):

        try:

            print(
                f"Attempt "
                f"{attempt + 1}/{total_attempts}"
            )

            response = llm.invoke(
                prompt
            )

            return response


        except Exception as e:

            last_error = e

            print(
                f"Attempt "
                f"{attempt + 1} failed: "
                f"{str(e)}"
            )


            if attempt < max_retries:

                wait_time = 2 ** attempt

                print(
                    f"Retrying in "
                    f"{wait_time} seconds..."
                )

                time.sleep(
                    wait_time
                )


    raise last_error