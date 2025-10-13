from sqlalchemy.orm import Session
from models import Driver, Order
from database import get_db
import asyncio

class WebSocketManager:
    def __init__(self, server_ws):
        self.server_ws = server_ws
        self.pending_responses: dict[str, asyncio.Future] = {}

    async def start_background_tasks(self):
        # 可增加多個 background task
        asyncio.create_task(self.periodic_broadcast())

    async def periodic_broadcast(self):
        while True:
            await asyncio.sleep(10)  # 每 10 秒推播
            await self.server_ws.broadcast({"client_type": "server", "msg": "ping"})

    async def broadcast_to_ros(self, ros_message: dict):
        """
        封裝發送給 ROS client 的訊息邏輯
        """
        await self.server_ws.broadcast(ros_message, client_type="ros")
        print("已推送給 ROS:", ros_message)

    async def wait_for_ros_response(self, message_id: str, timeout: int = 10):
        """
        等待 ROS 回覆結果，超時就拋出 asyncio.TimeoutError
        """
        fut = asyncio.get_event_loop().create_future()
        self.pending_responses[message_id] = fut
        try:
            return await asyncio.wait_for(fut, timeout)
        finally:
            self.pending_responses.pop(message_id, None)

    def set_ros_response(self, message_id: str, data: dict):
        """
        ROS 收到回覆後呼叫這個方法，把資料丟給對應的 Future
        """
        fut = self.pending_responses.get(message_id)
        if fut and not fut.done():
            fut.set_result(data)
            print(f"已設定 ROS 回覆: {message_id}")

    # -------------------
    # Odom 訊息處理
    # -------------------
    async def handle_ros_odom(self, message: dict):
        # 先推給 web client
        await self.server_ws.broadcast(message, client_type="web")

        # 如果是 odom 訊息，更新資料庫
        if message.get("type") == "odom":
            name = message.get("name")  # 例如 'ego_vehicle'
            pose = message.get("pose", {})
            position = pose.get("position", {})
            yaw = pose.get("yaw")

            if position.get("lat") is not None and position.get("lng") is not None:
                try:
                    # 即時取得 session
                    db_session = next(get_db())
                    driver = db_session.query(Driver).filter(Driver.name == name).first()
                    if driver:
                        driver.current_lat = position["lat"]
                        driver.current_lng = position["lng"]
                        driver.yaw = yaw
                        db_session.commit()
                except Exception as e:
                    print("更新 driver 位置時發生錯誤:", e)

    # -------------------
    # Dispatch 訊息處理
    # -------------------
    async def handle_ros_dispatched(self, message: dict):
        """
        收到 ROS dispatch 訊息後：
        1. 推送給對應 user_id 的 Flutter client
        2. 將該 user 尚未派車的訂單 status 改成 1，並 assign driver
        """
        user_id = message.get("user_id")
        assigned_vehicle = message.get("assigned_vehicle")

        if not user_id:
            print("收到 dispatched 訊息，但沒有 user_id，無法轉發")
            return

        # --- 推送給 Flutter ---
        ws = self.server_ws.user_map.get(str(user_id))
        if ws:
            try:
                await self.server_ws.send_json(ws, message)
                print(f"已將 dispatched 訊息推送給 user {user_id}")
            except Exception as e:
                print(f"推送給 user {user_id} 失敗:", e)
        else:
            print(f"user {user_id} 尚未連線，無法推送 dispatched 訊息")

        # --- 更新訂單 ---
        try:
            db_session = next(get_db())
            order = db_session.query(Order).filter(
                Order.user_id == int(user_id),
                Order.status == 0  # 待派車
            ).first()

            if order:
                order.status = 1  # 已接單

                # 查找對應 driver 的 id
                driver = db_session.query(Driver).filter(Driver.name == assigned_vehicle).first()
                if driver:
                    order.driver_id = driver.id
                    print(f"指派 driver {driver.id} 給訂單 {order.order_id}")
                else:
                    print(f"找不到 driver 對應 {assigned_vehicle}")

                db_session.commit()
                print(f"user {user_id} 的訂單 {order.order_id} 已更新 status=1")
            else:
                print(f"user {user_id} 沒有待派車的訂單")
        except Exception as e:
            print("更新訂單狀態時發生錯誤:", e)

