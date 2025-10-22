from fastapi import FastAPI, WebSocket, Depends
from database import get_db, async_engine  # async version
from routers.api_v1.routers import router
from models import Base
from fastapi.middleware.cors import CORSMiddleware
from ws_modules.global_ws import server_ws, manager
from config.logging_config import setup_logging
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession

# ----------------------
# 建立 FastAPI app 並設定 lifespan
# ----------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1️⃣ 建表
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 2️⃣ 設定 logging
    setup_logging()

    # 3️⃣ 啟動背景任務
    await manager.start_background_tasks()

    try:
        yield
    finally:
        await manager.stop_background_tasks()


app = FastAPI(lifespan=lifespan)

# ----------------------
# Middleware & Router
# ----------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 或指定你的前端網域
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")


# ----------------------
# WebSocket
# ----------------------
@app.websocket("/ws")
async def ws_route(websocket: WebSocket, db: AsyncSession = Depends(get_db)):
    client_type = websocket.query_params.get("client_type", "unknown").lower()

    if client_type == "web":
        await server_ws.websocket_endpoint_web(websocket, db=db)
    elif client_type == "flutter":
        await server_ws.websocket_endpoint_flutter(websocket, db=db)
    elif client_type == "ros":
        await server_ws.websocket_endpoint_ros(websocket)
    else:
        await websocket.close(code=4000, reason="Unsupported client_type")
