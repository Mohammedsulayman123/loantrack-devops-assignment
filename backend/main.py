import asyncio
import logging
import os
import socket
import sys
from contextlib import asynccontextmanager
from typing import Optional

import asyncpg
from fastapi import FastAPI, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("loantrack-api")

# Configuration via Environment Variables (Strictly no hardcoded credentials)
DB_HOST = os.getenv("DB_HOST", "postgres")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "loantrack")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")
SERVER_PORT = int(os.getenv("PORT", "8000"))
POD_NAME = os.getenv("HOSTNAME", socket.gethostname())

# Global connection pool
db_pool: Optional[asyncpg.Pool] = None
is_connecting = False


async def connect_with_retry():
    """
    Connect to PostgreSQL with exponential backoff.
    Ensures backend does not crash on startup if DB is unavailable.
    """
    global db_pool, is_connecting
    if db_pool is not None or is_connecting:
        return

    is_connecting = True
    base_delay = 1.0
    max_delay = 15.0
    factor = 2.0
    attempt = 1

    logger.info("Initializing database connection pool to %s:%s/%s...", DB_HOST, DB_PORT, DB_NAME)

    while db_pool is None:
        try:
            logger.info("Database connection attempt #%d connecting to %s:%s...", attempt, DB_HOST, DB_PORT)
            pool = await asyncpg.create_pool(
                host=DB_HOST,
                port=DB_PORT,
                user=DB_USER,
                password=DB_PASSWORD,
                database=DB_NAME,
                min_size=2,
                max_size=10,
                command_timeout=10,
            )
            # Test query
            async with pool.acquire() as conn:
                await conn.fetchval("SELECT 1")

            db_pool = pool
            is_connecting = False
            logger.info(
                "SUCCESS: Connected to PostgreSQL successfully on attempt #%d! Connection pool ready.",
                attempt,
            )
            return
        except Exception as exc:
            delay = min(base_delay * (factor ** (attempt - 1)), max_delay)
            logger.warning(
                "Database connection failed on attempt #%d: %s. Retrying in %.1f seconds...",
                attempt,
                str(exc),
                delay,
            )
            attempt += 1
            await asyncio.sleep(delay)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Launch connection loop in background so app starts instantly and /healthz is alive
    task = asyncio.create_task(connect_with_retry())
    yield
    # Graceful shutdown
    if db_pool:
        logger.info("Closing database connection pool...")
        await db_pool.close()
    if not task.done():
        task.cancel()


app = FastAPI(
    title="LoanTrack API",
    description="Backend microservice for LoanTrack financial operations",
    version="1.0.0",
    lifespan=lifespan,
)

# Enable CORS for frontend requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class LoanCreate(BaseModel):
    borrower_name: str = Field(..., min_length=2, max_length=100)
    loan_amount: float = Field(..., gt=0)
    property_city: str = Field(..., min_length=2, max_length=100)
    status: str = Field(default="PENDING")


@app.get("/healthz", summary="Liveness Probe")
async def healthz():
    """
    Process liveness check. Always returns 200 if the process is running.
    Does NOT depend on database availability.
    """
    return {
        "status": "healthy",
        "service": "loantrack-backend",
        "pod_name": POD_NAME,
    }


@app.get("/readyz", summary="Readiness Probe")
async def readyz(response: Response):
    """
    Readiness check. Validates that database connection pool is active and reachable.
    Returns 503 if database is disconnected or unreachable.
    """
    global db_pool
    if db_pool is None:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "not_ready",
            "reason": "Database connection pool is not yet initialized",
            "pod_name": POD_NAME,
        }

    try:
        async with db_pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return {
            "status": "ready",
            "database": "connected",
            "pod_name": POD_NAME,
        }
    except Exception as exc:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "not_ready",
            "reason": f"Database probe failed: {str(exc)}",
            "pod_name": POD_NAME,
        }


@app.get("/loans", summary="List all loans")
async def get_loans():
    """Fetch all loan records from PostgreSQL."""
    global db_pool
    if db_pool is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is currently unavailable. Retry shortly.",
        )

    try:
        async with db_pool.acquire() as conn:
            records = await conn.fetch(
                """
                SELECT id, borrower_name, loan_amount::float, property_city, status, created_at
                FROM loans
                ORDER BY id ASC
                """
            )
            loans = [dict(record) for record in records]
            return {
                "loans": loans,
                "count": len(loans),
                "pod_name": POD_NAME,
            }
    except Exception as exc:
        logger.error("Failed to fetch loans: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database query error: {str(exc)}",
        )


@app.post("/loans", status_code=status.HTTP_201_CREATED, summary="Create a new loan")
async def create_loan(payload: LoanCreate):
    """Create a new loan record."""
    global db_pool
    if db_pool is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is currently unavailable. Retry shortly.",
        )

    try:
        async with db_pool.acquire() as conn:
            record = await conn.fetchrow(
                """
                INSERT INTO loans (borrower_name, loan_amount, property_city, status)
                VALUES ($1, $2, $3, $4)
                RETURNING id, borrower_name, loan_amount::float, property_city, status, created_at
                """,
                payload.borrower_name,
                payload.loan_amount,
                payload.property_city,
                payload.status,
            )
            return {
                "message": "Loan created successfully",
                "loan": dict(record),
                "pod_name": POD_NAME,
            }
    except Exception as exc:
        logger.error("Failed to create loan: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database insert error: {str(exc)}",
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=SERVER_PORT, log_level="info")
