from fastapi import FastAPI, HTTPException

from models.task2 import (TaskRequest, TaskResponse,)
from services.task_service3 import execute_task


app = FastAPI(
    title="Unified LLM Task API",
    version="1.0.0"
)


@app.post("/task", response_model=TaskResponse)
def task_endpoint(
    request: TaskRequest
):

    try:

        result = execute_task(
            task=request.task,
            text=request.text
        )

        return result

    except ValueError as e:

        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )