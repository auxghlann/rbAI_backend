# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .api.endpoints import execution, telemetry

app = FastAPI(title="rbAI Backend", version="1.0.0")

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite default port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(execution.router)
app.include_router(telemetry.router)

@app.get("/")
async def root():
    return {"message": "rbAI Backend API", "version": "1.0.0"}

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "rbAI"}