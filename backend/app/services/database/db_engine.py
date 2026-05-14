"""
Database Engine Module

Centralised async SQLAlchemy engine, session factory, and reflected
metadata. All database-touching services in the application share these
instances. The sync engine is kept for metadata reflection at startup,
which is not fully async in SQLAlchemy.

Configuration:
    DATABASE_URL  - Postgres URL, e.g.
                    'postgresql://user:pass@host:5432/dbname'
                    The async engine derives a +asyncpg variant; any
                    sslmode query param is stripped because asyncpg uses
                    a different SSL config style.
"""
from __future__ import annotations

import os
import re
import ssl

from dotenv import load_dotenv
from sqlalchemy import MetaData, create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from app.utils.logger import AppLogger

logger = AppLogger.get_logger(__file__)

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set.")

# Strip sslmode query param (asyncpg can't consume it; use connect_args ssl=)
ASYNC_DATABASE_URL = re.sub(
    r"([?&])sslmode=[^&]+(&?)",
    lambda m: m.group(1) if m.group(2) else "",
    DATABASE_URL,
)
ASYNC_DATABASE_URL = re.sub(r"[?&]$", "", ASYNC_DATABASE_URL)

if ASYNC_DATABASE_URL.startswith("postgresql://"):
    ASYNC_DATABASE_URL = ASYNC_DATABASE_URL.replace(
        "postgresql://", "postgresql+asyncpg://", 1
    )

# SSL context for cloud-hosted Postgres (AWS RDS, etc.). Enabled only when
# the original URL requested it; otherwise asyncpg uses an unencrypted
# connection appropriate for local dev.
_ssl_required = "sslmode=require" in (DATABASE_URL or "")
_async_connect_args = {"ssl": "require"} if _ssl_required else {}

async_engine = create_async_engine(
    ASYNC_DATABASE_URL,
    connect_args=_async_connect_args,
    pool_pre_ping=True,
    pool_size=8,
    max_overflow=6,
    pool_timeout=30,
    pool_recycle=3600,
    pool_reset_on_return="rollback",
    echo=False,
)

AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    async_engine, class_=AsyncSession, expire_on_commit=False
)

# Sync engine: used for metadata reflection (not fully async in SQLAlchemy).
sync_engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)

Base = declarative_base()
metadata = MetaData()

# Reflect tables at import time so services can access them as
# metadata.tables[<name>].
logger.info("Attempting to reflect database tables...")
try:
    metadata.reflect(bind=sync_engine)
    table_list = list(metadata.tables.keys())
    logger.info("Reflected %d tables: %s", len(table_list), table_list)
    if not table_list:
        logger.error("No tables reflected. Database appears empty.")
except Exception as exc:
    logger.error("Failed to reflect metadata: %s", exc, exc_info=True)
    raise
