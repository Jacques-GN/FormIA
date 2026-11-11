from fastapi import FastAPI

from app.api.routes import router

app = FastAPI(
    title="FormIA",
    description="L'intelligence africaine, au service de vos idées.",
    version="0.1.0",
)

app.include_router(router)
