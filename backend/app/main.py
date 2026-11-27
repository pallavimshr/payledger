"""FastAPI application entry point."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.orders import router as orders_router
from app.api.recon import router as recon_router
from app.api.routes import router
from app.api.stats import router as stats_router
from app.api.webhooks import router as webhooks_router

app = FastAPI(
    title="PayLedger",
    description="Double-entry payments ledger with exactly-once webhooks.",
    version="0.1.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # the Next.js dashboard
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)
app.include_router(orders_router)
app.include_router(webhooks_router)
app.include_router(stats_router)
app.include_router(recon_router)
