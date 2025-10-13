from fastapi import WebSocket, WebSocketDisconnect
import json
import asyncio

class WebSocketServer:
    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {
            "flutter": [],
            "ros": [],
            "web": [],
        }
        self.ros_message_callback = None  # 允許註冊 callback
        self.manager = None  # 由外部注入 WebSocketManager

    def set_ros_callback(self, callback):
        """讓外部註冊一個 ROS 訊息的回呼函式"""
        self.ros_message_callback = callback

    async def connect(self, websocket: WebSocket, client_type: str):
        if client_type not in self.active_connections:
            self.active_connections[client_type] = []
        self.active_connections[client_type].append(websocket)
        print(f"新 WebSocket 連線: {client_type}")

    def disconnect(self, websocket: WebSocket):
        for ctype, conns in self.active_connections.items():
            if websocket in conns:
                conns.remove(websocket)
                print(f"WebSocket 斷線: {ctype}")

    async def websocket_endpoint(self, websocket: WebSocket, client_type: str = "unknown"):
        await websocket.accept()
        await self.connect(websocket, client_type)

        try:
            while True:
                try:
                    data = await websocket.receive_text()
                except WebSocketDisconnect:
                    break

                # 先處理 JSON 解析錯誤，再處理訊息
                try:
                    message = json.loads(data)
                except json.JSONDecodeError:
                    print(f"收到非 JSON 資料: {data}")
                    continue

                print(f"收到 {client_type} 的訊息: {message}")

                if client_type == "ros":
                    t = message.get("type")
                    # odom 用 manager 的處理函式（保持非同步）
                    if t == "odom":
                        if self.manager:
                            try:
                                await self.manager.handle_ros_odom(message)
                            except Exception as e:
                                print("handle_ros_odom error:", e)
                    
                    if t == "dispatched":
                        if self.manager:
                            try:
                                await self.manager.handle_ros_odom(message)
                            except Exception as e:
                                print("handle_ros_dispatched error:", e)

                    # estimate → **把結果交給 manager 的 pending future**
                    elif t == "estimate":
                        msg_id = message.get("message_id")

                        # 優先用 manager 直接設定 response（最保險、簡潔）
                        if msg_id and self.manager:
                            try:
                                self.manager.set_ros_response(msg_id, message)
                                print(f"已透過 manager 設定 ROS 回覆: {msg_id}")
                            except Exception as e:
                                print("set_ros_response error:", e)

                        # 若有註冊 callback，也呼叫（支援 coroutine）
                        if self.ros_message_callback:
                            try:
                                ret = self.ros_message_callback(message)
                                # 如果 callback 回傳 coroutine，排成 task 執行
                                if asyncio.iscoroutine(ret):
                                    asyncio.create_task(ret)
                            except Exception as e:
                                print("ros_message_callback error:", e)

                else:
                    # 其他 client_type 的訊息你可在此擴充
                    pass

        finally:
            self.disconnect(websocket)


    async def send_json(self, websocket: WebSocket, message: dict):
        await websocket.send_text(json.dumps(message))

    async def broadcast(self, message: dict, client_type: str = None):
        """廣播訊息給指定類型的 client"""
        if client_type:
            conns = self.active_connections.get(client_type, [])
        else:
            conns = [ws for group in self.active_connections.values() for ws in group]

        disconnected = []
        for ws in conns:
            try:
                await self.send_json(ws, message)
            except WebSocketDisconnect:
                disconnected.append(ws)

        for ws in disconnected:
            self.disconnect(ws)
