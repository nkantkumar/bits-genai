from fastapi import FastAPI, HTTPException

from models.task import TaskRequest
from router import route_task


app = FastAPI(
    title="LLM Task Router",
    version="1.0.0"
)


@app.post("/task")
def task_router(
    request: TaskRequest
):

    try:

        result = route_task(
            request.task
        )

        return result

    except ValueError as e:

        raise HTTPException(
            status_code=400,
            detail=str(e)
        )