from fastapi import FastAPI
from app.api.webhook import router as webhook_router
from app.utils.visualizaton import generate_graph_visualization
import uvicorn

app = FastAPI(
    title="RCA Agent",
    version="1.0.0",
    description="jenkins root cause analyser agent system"
)

app.include_router(webhook_router)


@app.get("/health")
def health_checker():
    return {
        "status":"healthy"
    }

if __name__ == "__main__":
    generate_graph_visualization()
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
