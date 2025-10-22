from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# 使用 asyncpg 驅動
DATABASE_URL = "postgresql+asyncpg://postgres:123456@localhost:5432/test"

# 建立 async engine
async_engine = create_async_engine(DATABASE_URL, echo=False)

# 建立 async session maker
AsyncSessionLocal = sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,  # commit 後不 expire
)

# base
Base = declarative_base()

# ----------------------------
# Dependency for FastAPI
# ----------------------------
async def get_db():
    async with AsyncSessionLocal() as db:
        yield db
