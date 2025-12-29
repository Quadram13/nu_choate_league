"""
Nu Choate League API - Main FastAPI application
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from app.config import settings
from app.database import connect_to_mongo, close_mongo_connection
from app.routers import leagues, stats

# Initialize FastAPI app
app = FastAPI(
    title="Nu Choate League API",
    description="Fantasy Football League Hub - Data from Sleeper API",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# CORS middleware - allow all origins for now
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Startup event - connect to database
@app.on_event("startup")
async def startup_event():
    """Run on application startup"""
    print("Starting Nu Choate League API...")
    await connect_to_mongo()
    print("API ready!")


# Shutdown event - close database connection
@app.on_event("shutdown")
async def shutdown_event():
    """Run on application shutdown"""
    print("Shutting down Nu Choate League API...")
    await close_mongo_connection()


# Health check endpoints
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "Nu Choate League API",
        "version": "1.0.0",
        "status": "healthy",
        "environment": settings.API_ENV
    }


@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    return {"status": "ok"}


# Include API routers
app.include_router(leagues.router, prefix="/api/v1", tags=["leagues"])
app.include_router(stats.router, prefix="/api/v1", tags=["stats"])


# Serve static files (HTML reports from docs/)
# Mount the docs directory to serve the existing HTML pages
docs_path = Path(__file__).parent.parent.parent / "docs"
if docs_path.exists():
    app.mount("/static", StaticFiles(directory=str(docs_path)), name="static")
    
    @app.get("/site/{path:path}")
    async def serve_site(path: str):
        """Serve static HTML site"""
        file_path = docs_path / path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        # Try with .html extension
        html_path = docs_path / f"{path}.html"
        if html_path.exists():
            return FileResponse(html_path)
        # Return index if path is directory
        index_path = docs_path / path / "index.html"
        if index_path.exists():
            return FileResponse(index_path)
        return {"error": "Page not found"}, 404


# Run with: uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
