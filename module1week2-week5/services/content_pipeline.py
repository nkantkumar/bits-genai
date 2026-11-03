import os
from pathlib import Path

from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate


load_dotenv()


MODEL = os.getenv(
    "OPENAI_MODEL",
    "gpt-4.1-mini"
)


# ==================================================
# LLM
# ==================================================

llm = ChatOpenAI(
    model=MODEL,
    temperature=0.1
)


# ==================================================
# Prompt Loader
# ==================================================

def load_prompt(prompt_name):

    prompt_file = Path("prompts") / prompt_name

    if not prompt_file.exists():
        raise FileNotFoundError(
            f"Prompt not found: {prompt_file}"
        )

    return prompt_file.read_text(
        encoding="utf-8"
    )


# ==================================================
# Step 1: Summarization
# ==================================================

summary_prompt = PromptTemplate(
    template=load_prompt(
        "summarize_v3.txt"
    ),
    input_variables=["text"]
)

summary_chain = summary_prompt | llm


# ==================================================
# Step 2: Keyword Extraction
# ==================================================

keyword_prompt = PromptTemplate(
    template=load_prompt(
        "extract_keywords_v2.txt"
    ),
    input_variables=["summary"]
)

keyword_chain = keyword_prompt | llm


# ==================================================
# Step 3: Headline Generation
# ==================================================

headline_prompt = PromptTemplate(
    template=load_prompt(
        "headline_v2.txt"
    ),
    input_variables=[
        "summary",
        "keywords"
    ]
)

headline_chain = headline_prompt | llm


# ==================================================
# Content Pipeline
# ==================================================

def run_content_pipeline(text):

    # ----------------------------------------------
    # Step 1
    # ----------------------------------------------

    summary_response = summary_chain.invoke({
        "text": text
    })

    summary = summary_response.content.strip()


    # ----------------------------------------------
    # Step 2
    # ----------------------------------------------

    keyword_response = keyword_chain.invoke({
        "summary": summary
    })

    keywords = keyword_response.content.strip()


    # ----------------------------------------------
    # Step 3
    # ----------------------------------------------

    headline_response = headline_chain.invoke({
        "summary": summary,
        "keywords": keywords
    })

    headline = headline_response.content.strip()


    # ----------------------------------------------
    # Return pipeline result
    # ----------------------------------------------

    return {
        "summary": summary,
        "keywords": keywords,
        "headline": headline
    }