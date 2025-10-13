from sqlalchemy.orm import Session
from models import Driver
import asyncio

class WebSocketManager:
    def __init__(self, server_ws, db_session=None):
        self.server_ws = server_ws
        self.db_session = db_session
        self.pending_responses: dict[str, asyncio.Future] = {}

    async def start_background_tasks(self):
        # 可增加多個 background task
        asyncio.create_task(self.periodic_broadcast())

    async def periodic_broadcast(self):
        while True:
            await asyncio.sleep(10)  # 每 10 秒推播
            await self.server_ws.broadcast({"client_type": "server", "msg": "ping"})
            #print("Server broadcast: ping")

    async def broadcast_to_ros(self, ros_message: dict):
        """
        封裝發送給 ROS client 的訊息邏輯
        """
        payload = ros_message
        await self.server_ws.broadcast(payload, client_type="ros")
        print("已推送給 ROS:", payload)

    async def wait_for_ros_response(self, message_id: str, timeout: int = 10):
        """
        等待 ROS 回覆結果，超時就拋出 asyncio.TimeoutError
        """
        fut = asyncio.get_event_loop().create_future()
        self.pending_responses[message_id] = fut
        try:
            return await asyncio.wait_for(fut, timeout)
        finally:
            # 等待結束後清理
            self.pending_responses.pop(message_id, None)

    def set_ros_response(self, message_id: str, data: dict):
        """
        ROS 收到回覆後呼叫這個方法，把資料丟給對應的 Future
        """
        fut = self.pending_responses.get(message_id)
        if fut and not fut.done():
            fut.set_result(data)
            print(f"已設定 ROS 回覆: {message_id}")
    
    # 新增處理 odom 訊息的方法
    async def handle_ros_odom(self, message: dict):
        # 先推給 web client
        await self.server_ws.broadcast(message, client_type="web")

        # 如果是 odom 訊息，更新資料庫
        if message.get("type") == "odom":
            name = message.get("name")  # 例如 'ego_vehicle'
            pose = message.get("pose", {})
            position = pose.get("position", {})
            yaw = pose.get("yaw")

            if position.get("lat") is not None and position.get("lon") is not None:
                driver = self.db_session.query(Driver).filter(Driver.name == name).first()
                if driver:
                    driver.current_lat = position["lat"]
                    driver.current_lng = position["lon"]
                    driver.yaw = yaw
                    self.db_session.commit()
                    #print(f"更新 driver {driver.name} 位置: lat={driver.current_lat}, lng={driver.current_lng}, yaw={driver.yaw}")

    async def handle_ros_dispatched(self, message: dict):
        # 先推給 web client
        await self.server_ws.broadcast(message, client_type="web")

        # 如果是 odom 訊息，更新資料庫
        if message.get("type") == "odom":
            name = message.get("name")  # 例如 'ego_vehicle'
            pose = message.get("pose", {})
            position = pose.get("position", {})
            yaw = pose.get("yaw")

            if position.get("lat") is not None and position.get("lon") is not None:
                driver = self.db_session.query(Driver).filter(Driver.name == name).first()
                if driver:
                    driver.current_lat = position["lat"]
                    driver.current_lng = position["lon"]
                    driver.yaw = yaw
                    self.db_session.commit()
