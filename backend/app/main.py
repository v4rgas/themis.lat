from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import agent, websocket

app = FastAPI(title="Procurement Fraud Investigation API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(agent.router, prefix="/api", tags=["agent"])
app.include_router(websocket.router, prefix="/api", tags=["websocket"])


@app.get("/")
def health():
    return {"status": "ok"}
