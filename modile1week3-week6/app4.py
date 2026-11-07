from pathlib import Path

from services.content_pipeline import (
    run_content_pipeline
)


def main():

    text = Path(
        "long_text.txt"
    ).read_text(
        encoding="utf-8"
    )


    result = run_content_pipeline(
        text
    )


    print("\n==============================")
    print("CONTENT PIPELINE RESULT")
    print("==============================")


    print("\nSUMMARY:")
    print(result["summary"])


    print("\nKEYWORDS:")
    print(result["keywords"])


    print("\nHEADLINE:")
    print(result["headline"])


if __name__ == "__main__":
    main()