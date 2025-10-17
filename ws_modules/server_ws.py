from fastapi import WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.orm import Session
from database import get_db
from services import get_current_user, admin_viewer_required
import json
import asyncio

class WebSocketServer:
    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {
            "flutter": [], "ros": [], "web": []
        }
        self.user_map: dict[str, WebSocket] = {}  # user_id → websocket
        self.ros_message_callback = None
        self.manager = None

    def set_ros_callback(self, callback):
        self.ros_message_callback = callback

    # ----------------------
    # 連線管理
    # ----------------------
    async def connect(self, websocket: WebSocket, client_type: str):
        self.active_connections.setdefault(client_type, []).append(websocket)
        print(f"new WebSocket connection: {client_type}")

    def disconnect(self, websocket: WebSocket):
        for ctype, conns in self.active_connections.items():
            if websocket in conns:
                conns.remove(websocket)
                print(f"WebSocket disconnected: {ctype}")
        # 移除 user_map 中綁定
        to_delete = [uid for uid, ws in self.user_map.items() if ws == websocket]
        for uid in to_delete:
            del self.user_map[str(uid)]

    # ----------------------
    # 驗證方法
    # ----------------------
    # Web
    async def verify_web_user(self, websocket, db: Session, timeout: float = 5.0):
        try:
            data = await asyncio.wait_for(websocket.receive_text(), timeout=timeout)
        except asyncio.TimeoutError:
            await websocket.close(code=4004, reason="Auth timeout(5 secs).")
            raise WebSocketDisconnect()
        
        msg = self._parse_json_or_close(websocket, data, "Auth must be JSON.")
        token = msg.get("token") or await self._close_missing_token(websocket)
        user = await asyncio.to_thread(lambda: admin_viewer_required(current_user=get_current_user(token, db), db=db))
        return user

    """ # Flutter
    async def verify_flutter_user(self, websocket, db: Session, timeout: float = 5.0):
        try:
            data = await asyncio.wait_for(websocket.receive_text(), timeout=timeout)
        except asyncio.TimeoutError:
            await websocket.close(code=4004, reason="Auth timeout(5 secs).")
            raise WebSocketDisconnect()
        
        msg = self._parse_json_or_close(websocket, data, "Auth must be JSON.")
        token = msg.get("token") or await self._close_missing_token(websocket)
        vehicle = msg.get("vehicle_name")
        user_id = msg.get("user_id")

        if vehicle is None:
            await websocket.close(code=4003, reason="Missing vehicle name.")
            raise WebSocketDisconnect()
        
        if user_id is None:
            await websocket.close(code=4003, reason="Missing user id.")
            raise WebSocketDisconnect()
        
        user = await asyncio.to_thread(lambda: get_current_user(token, db))
        if str(user.id) != str(user_id):
            await websocket.close(code=4005, reason="User ID mismatch with token.")
            raise WebSocketDisconnect()
        return user, user_id, vehicle """
    
    async def verify_flutter_user(self, websocket, db: Session, timeout: float = 5.0):
        try:
            print("[verify] 等待 Flutter 傳入驗證資料中...")
            data = await asyncio.wait_for(websocket.receive_text(), timeout=timeout)
            print(f"[verify] 收到原始資料: {data}")
        except asyncio.TimeoutError:
            print("[verify] ❌ 驗證逾時（5 秒內未收到任何資料）")
            await websocket.close(code=4004, reason="Auth timeout(5 secs).")
            raise WebSocketDisconnect()
        
        msg = self._parse_json_or_close(websocket, data, "Auth must be JSON.")
        print(f"[verify] 解析後資料: {msg}")

        token = msg.get("token") or await self._close_missing_token(websocket)
        vehicle = msg.get("vehicle_name")
        user_id = msg.get("user_id")

        if vehicle is None:
            print("[verify] ❌ 缺少 vehicle_name")
            await websocket.close(code=4003, reason="Missing vehicle name.")
            raise WebSocketDisconnect()
        
        if user_id is None:
            print("[verify] ❌ 缺少 user_id")
            await websocket.close(code=4003, reason="Missing user id.")
            raise WebSocketDisconnect()
        
        try:
            print(f"[verify] 開始驗證 token 對應的 user（user_id={user_id}）")
            user = await asyncio.to_thread(lambda: get_current_user(token, db))
            print(f"[verify] token 驗證成功，用戶 ID: {user.id}")
        except Exception as e:
            print(f"[verify] ❌ get_current_user 失敗: {e}")
            await websocket.close(code=4006, reason="Token verification failed.")
            raise WebSocketDisconnect()

        if str(user.id) != str(user_id):
            print(f"[verify] ❌ 用戶 ID 不匹配：token內 {user.id} ≠ 傳入 {user_id}")
            await websocket.close(code=4005, reason="User ID mismatch with token.")
            raise WebSocketDisconnect()

        print("[verify] ✅ 驗證通過，成功登入！")
        return user, user_id, vehicle



    # ----------------------
    # 各 client endpoint
    # ----------------------
    async def websocket_endpoint_web(self, websocket: WebSocket, db: Session = Depends(get_db)):
        await websocket.accept()
        user = await self.verify_web_user(websocket, db)
        print(f"Manager {user.id} connection established.")
        await self.connect(websocket, "web")
        
        await self.send_json(websocket, {
            "type": "auth",
            "status": "success",
            "message": f"Manager {user.id} connection established."
        })

        await self.handle_messages(websocket, "web")

    async def websocket_endpoint_flutter(self, websocket: WebSocket, db: Session = Depends(get_db)):
        await websocket.accept()
        user, user_id, vehicle = await self.verify_flutter_user(websocket, db)
        print(f"User {user_id} connection established.")
        await self.connect(websocket, "flutter")

        # 綁定 user_id → websocket
        self.user_map[str(user_id)] = websocket

        if vehicle not in self.manager.vehicle_user_map:
            self.manager.vehicle_user_map[vehicle] = set()
        self.manager.vehicle_user_map[vehicle].add(str(user_id))
    
        await self.send_json(websocket, {
            "type": "auth",
            "status": "success",
            "message": f"User {user_id} connection established."
        })

        try:
            await self.handle_messages(websocket, "flutter")
        finally:
            # 當 websocket 關閉時，自動移除該 user
            if vehicle in self.manager.vehicle_user_map:
                self.manager.vehicle_user_map[vehicle].discard(str(user_id))
                if not self.manager.vehicle_user_map[vehicle]:
                    # 如果該車沒剩任何使用者，刪掉 key
                    del self.manager.vehicle_user_map[vehicle]
            print(f"User {user_id} disconnected from vehicle {vehicle}")

    async def websocket_endpoint_ros(self, websocket: WebSocket):
        await websocket.accept()
        print("ROS 連線成功")
        await self.connect(websocket, "ros")
        await self.handle_messages(websocket, "ros")

    # ----------------------
    # JSON 與 ROS 處理輔助
    # ----------------------
    def _parse_json(self, data, websocket):
        try:
            return json.loads(data)
        except json.JSONDecodeError:
            print(f"收到非 JSON 資料: {data}")
            return None

    def _parse_json_or_close(self, websocket, data, reason):
        try:
            return json.loads(data)
        except json.JSONDecodeError:
            asyncio.create_task(websocket.close(code=4001, reason=reason))
            raise WebSocketDisconnect()

    async def _close_missing_token(self, websocket):
        await websocket.close(code=4002, reason="Missing token")
        raise WebSocketDisconnect()

    async def _handle_ros_message(self, message: dict):

        t = message.get("type")

        if t == "odom" and self.manager:
            try: await self.manager.handle_ros_odom(message)
            except Exception as e: print("handle_ros_odom error:", e)

        elif (t == "dispatched" or t == "queued") and self.manager:
            order_id = message.get("order_id")
            if order_id:
                try:
                    self.manager.set_ros_response(order_id, message)
                except Exception as e:
                    print("set_ros_response error:", e)
            try:
                await self.manager.handle_ros_dispatched_queued(message)
            except Exception as e:
                print("handle_ros_dispatched error:", e)

            if self.ros_message_callback:
                try:
                    ret = self.ros_message_callback(message)
                    if asyncio.iscoroutine(ret):
                        asyncio.create_task(ret)
                except Exception as e:
                    print("ros_message_callback error:", e)

        elif t == "estimate" and self.manager:
            msg_id = message.get("message_id")
            try:
                if msg_id: self.manager.set_ros_response(msg_id, message)
            except Exception as e: print("set_ros_response error:", e)
            if self.ros_message_callback:
                try:
                    ret = self.ros_message_callback(message)
                    if asyncio.iscoroutine(ret): asyncio.create_task(ret)
                except Exception as e: print("ros_message_callback error:", e)
        
        elif t == "ready_2_trip" and self.manager:
            try: await self.manager.handle_ros_ready_to_trip(message)
            except Exception as e: print("handle_ros_odom error:", e)
            
    async def _handle_flutter_message(self, message: dict):
        t = message.get("type")

        if t == "geton" and self.manager:
            try:
                await self.manager.broadcast_to_ros(message)
            except Exception as e:
                print(f"[geton] broadcast_to_ros error: {e}")

            try:
                await self.broadcast(message, "web")
            except Exception as e:
                print(f"[geton] broadcast_to_web error: {e}")
            
    # ----------------------
    # 共用 JSON 循環
    # ----------------------
    async def handle_messages(self, websocket: WebSocket, client_type: str):
        try:
            while True:
                try:
                    data = await websocket.receive_text()
                except WebSocketDisconnect:
                    break

                message = self._parse_json(data, websocket)
                if not message:
                    continue
                
                if not message.get("type") == "odom":
                    print(f"收到 {client_type} 的訊息: {message}")

                if client_type == "ros":
                    await self._handle_ros_message(message)
                elif client_type == "flutter":
                    await self._handle_flutter_message(message)
                    pass
        finally:
            self.disconnect(websocket)

    # ----------------------
    # 送訊息
    # ----------------------
    async def send_json(self, websocket: WebSocket, message: dict):
        await websocket.send_text(json.dumps(message))

    async def broadcast(self, message: dict, client_type: str = None):
        if client_type:
            conns = self.active_connections.get(client_type, [])
        else:
            conns = [ws for group in self.active_connections.values() for ws in group]

        disconnected = []
        for ws in conns:
            try: await self.send_json(ws, message)
            except WebSocketDisconnect: disconnected.append(ws)

        for ws in disconnected:
            self.disconnect(ws)

    async def broadcast_to_user(self, user_id: str, message: dict):
        ws = self.user_map.get(str(user_id))
        if not ws:
            print(f"Failed to send, user {user_id} offline.")
            self.disconnect(ws)
            return

        if ws.client_state.name != "CONNECTED":
            print(f"user {user_id} offline, remove from map")
            self.user_map.pop(str(user_id), None)
            return

        try:
            await self.send_json(ws, message)
            print(f"Msg send to {user_id}: {message}")
        except Exception as e:
            print(f"Send error: {e}, remove user {user_id}")
            self.user_map.pop(str(user_id), None)
