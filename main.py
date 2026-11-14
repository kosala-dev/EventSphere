import asyncio
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from database import engine, Base, SessionLocal
from models import *  # Registers all SQLAlchemy models with Base
from routers import venues, events, bookings, tickets, private_hire, dashboard, users
from agents.waitlist_agent import WaitlistAgent

# Automatically create all database tables on application startup
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="EventSphere Platform",
    description="Mobile-friendly venue booking and digital ticketing platform powered by a Multi-Agent System (MAS). ICA 02 Submission.",
    version="2.0"
)

# Enable CORS for mobile web browsers and responsive frontend testing (Bootstrap / 375px width support)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register all application routers
app.include_router(venues.router)
app.include_router(events.router)
app.include_router(bookings.router)
app.include_router(tickets.router)
app.include_router(private_hire.router)
app.include_router(dashboard.router)
app.include_router(users.router)

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/ui")
def render_ui():
    return FileResponse(Path(__file__).parent / "static" / "index.html")


@app.on_event("startup")
async def startup_event():
    """
    Proactive Behavior & Background Agent Loop (Part B Rule 4):
    Launches the WaitlistAgent expiry sweep background task asynchronously on startup 
    so it runs independently without requiring user interaction.
    """
    asyncio.create_task(WaitlistAgent.run_expiry_sweep_loop(SessionLocal))
    print("🚀 EventSphere Multi-Agent System initialized. Background agent loops are active.")


@app.get("/")
def read_root():
    return FileResponse(Path(__file__).parent / "static" / "index.html")


@app.get("/api-status")
def read_api_status():
    return {
        "platform": "EventSphere Multi-Agent Platform",
        "status": "online",
        "docs_url": "/docs",
        "assignment": "IT4123 ICA 02 Live Viva Evaluation"
    }