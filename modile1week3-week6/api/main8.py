from fastapi import FastAPI, HTTPException

from models.task6 import TaskRequest, TaskResponse
from services.task_service7 import execute_task


app = FastAPI(
    title="LLM Task API",
    version="1.0"
)


@app.post(
    "/task",
    response_model=TaskResponse
)
def task_endpoint(request: TaskRequest):

    try:

        return execute_task(
            task=request.task,
            text=request.text
        )

    except ValueError as e:

        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

    except Exception as e:

        print(f"Unexpected error: {e}")

        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )