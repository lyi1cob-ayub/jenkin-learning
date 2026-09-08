from fastapi import FastAPI
from app.api.webhook import router as webhook_router
from app.utils.visualizaton import generate_graph_visualization
import uvicorn
from app.db.db import init_db
from contextlib import asynccontextmanager
from loguru import logger
from prometheus_fastapi_instrumentator import Instrumentator

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Executed on application startup
    try:
        init_db()
        logger.info("Database initialized and schemas verified successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize database on startup: {str(e)}")
    
    yield
    
    # Clean up operations during application shutdown (if needed)
    logger.info("Shutting down application...")

app = FastAPI(
    title="RCA Agent",
    version="1.0.0",
    description="jenkins root cause analyser agent system",
    lifespan=lifespan
)

app.include_router(webhook_router)



@app.get("/health")
def health_checker():
    return {
        "status":"healthy"
    }
# 2. Instrument and expose AFTER all routers are included
Instrumentator(should_group_status_codes=False).instrument(app).expose(app)



if __name__ == "__main__":
    generate_graph_visualization()
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
