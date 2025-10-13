from fastapi import FastAPI, WebSocket, Query, Depends
from database import get_db
from routers.api_v1.routers import router
from models import Base
from database import engine
from fastapi.middleware.cors import CORSMiddleware
from ws_modules.global_ws import server_ws, manager
import asyncio

Base.metadata.create_all(bind=engine)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 或指定你的前端網域
    allow_credentials=True,
    allow_methods=["*"],  # 允許所有方法 GET/POST/OPTIONS
    allow_headers=["*"],  # 允許所有 headers（包含 Authorization）
)

app.include_router(router, prefix="/api/v1")

@app.on_event("startup")
async def startup_event():
    await manager.start_background_tasks()
    print("Server startup complete")

@app.websocket("/ws")
async def ws_route(websocket: WebSocket, db=Depends(get_db)):
    # 取得 query string 的 client_type
    client_type = websocket.query_params.get("client_type", "unknown").lower()

    if client_type == "web":
        await server_ws.websocket_endpoint_web(websocket, db=db)
    elif client_type == "flutter":
        await server_ws.websocket_endpoint_flutter(websocket, db=db)
    elif client_type == "ros":
        await server_ws.websocket_endpoint_ros(websocket)
    else:
        # 不支援的 client_type
        await websocket.close(code=4000, reason="Unsupported client_type")

""" @app.websocket("/ws")
async def ws_route(websocket: WebSocket):
    # 取得 query string
    client_type = websocket.query_params.get("client_type", "unknown")
    await server_ws.websocket_endpoint(websocket, client_type=client_type) """


""" 
@app.on_event("startup")
async def startup_event():
    await manager.start_background_tasks()
    print("Server startup complete")

@app.websocket("/ws")
async def ws_route(websocket: WebSocket):
    await server_ws.websocket_endpoint(websocket) 

@app.websocket("/ws")
async def ws_route(websocket: WebSocket, client: str = Query("unknown")):
    # 前端可用 ws://localhost:8000/ws?client=ros
    await server_ws.websocket_endpoint(websocket, client_type=client)
"""

""" # -----------------------------
# 啟動背景任務：ROS client + Server WS
# -----------------------------
# 全域 WebSocketServer
server_ws = WebSocketServer(host="0.0.0.0", port=8000)

@app.on_event("startup")
async def startup_event():
    async def start_ros_client():
        while True:
            try:
                ros_client = ROSBridgeClient("wss://lamar-subconjunctival-unwhiningly.ngrok-free.dev")
                #ros_client = ROSBridgeClient()
                payload = {
                "pick_up": {"lat": 24.123, "lon": 120.456, "yaw_deg": 0},
                "drop_off": {"lat": 24.234, "lon": 120.567, "yaw_deg": 90}
                }
                # 連線並發送一次 JSON，之後持續接收
                await ros_client.connect_and_send(payload)
            except Exception as e:
                #print("ROSBridge connection failed, retry in 5s:", e)
                await asyncio.sleep(5)

    # 丟到背景，不 await，避免阻塞 FastAPI
    asyncio.create_task(start_ros_client())
    asyncio.create_task(server_ws.start())  # 也可以改成背景 task

@app.websocket("/ws")
async def ws_route(websocket: WebSocket):
    await server_ws.websocket_endpoint(websocket)
 """