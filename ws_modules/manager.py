from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from models import Driver, Order, Route, PendingHistory
from enums import OrderStatus
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from geoalchemy2 import WKTElement
from database import get_db, AsyncSessionLocal
import asyncio
from geoalchemy2.shape import from_shape
from shapely.geometry import LineString

class WebSocketManager:
    def __init__(self, server_ws):
        self.server_ws = server_ws
        self._tasks = set() #track background tasks
        self.pending_responses: dict[str, asyncio.Future] = {}  #wait for response
        self.vehicle_user_map: dict[str, set[str]] = {}  # vehicle_name → user_id


    async def start_background_tasks(self):
        task = asyncio.create_task(self.periodic_broadcast())
        self._tasks.add(task)
        task.add_done_callback(lambda t: self._tasks.discard(t))

    async def stop_background_tasks(self):
        for task in list(self._tasks):
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

    async def periodic_broadcast(self):
        while True:
            await asyncio.sleep(10)
            await self.server_ws.broadcast({"client_type": "server", "msg": "ping"})

    async def broadcast_to_ros(self, ros_message: dict):
        """
        *for route api
        封裝發送給 ROS client 的訊息邏輯
        """
        await self.server_ws.broadcast(ros_message, client_type="ros")
        print("已推送給 ROS:", ros_message)

    async def broadcast_to_web(self, message: dict):
        await self.server_ws.broadcast(message, client_type="web")
        print("已推送給 Web:", message)

    async def _cancel_all_unfinished_orders(self):
        """
        當 ROS 斷線時，將所有未完成訂單 (status = 0,1,2...) 更新為已取消
        """
        async with AsyncSessionLocal() as db:  # 自己開 session
            try:
                async with db.begin():  # 開啟交易
                    # 查出未完成訂單 (例如 status=0:待派車, 1:進行中)
                    result = await db.execute(
                        select(Order).where(Order.status.in_([
                            OrderStatus.PENDING.value,    # 0
                            OrderStatus.ASSIGNED.value,   # 1
                            OrderStatus.ACCEPTED.value,   # 2
                            OrderStatus.IN_PROGRESS.value,# 3
                        ]))
                    )
                    orders = result.scalars().all()

                    if not orders:
                        print("目前沒有未完成訂單，無需取消")
                        return
                    
                    # 批次更新狀態
                    for order in orders:
                        order.status = OrderStatus.CANCELLED.value  # 例如 5
                        print(f"🚫 訂單 {order.order_id} 已設為取消")

                # commit 在 async with db.begin() 結束時自動執行
                print("✅ 所有未完成訂單已設為取消")

            except Exception as e:
                print("❌ 取消未完成訂單時發生錯誤：", e)

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
        name = message.get("name")  # e.g. hero0/ hero1
        pose = message.get("pose", {})
        position = pose.get("position", {})
        yaw = pose.get("yaw")

        # 廣播給 Web
        await self.server_ws.broadcast(message, client_type="web")

        if position.get("lat") is not None and position.get("lng") is not None:
            try:
                async with AsyncSessionLocal() as db:      # 自己開 session
                    async with db.begin():                  # 事務開始
                        result = await db.execute(
                            select(Driver).where(Driver.name == name)
                        )
                        driver = result.scalars().first()
                        if driver:
                            driver.current_lat = position["lat"]
                            driver.current_lng = position["lng"]
                            driver.yaw = yaw
                    # commit 由 db.begin() 自動完成
            except SQLAlchemyError as e:
                print("更新 driver 位置時發生資料庫錯誤:", e)
            except Exception as e:
                print("更新 driver 位置時發生錯誤:", e)

        # 廣播給使用者
        for user_id in self.vehicle_user_map.get(name, set()):
            await self.server_ws.broadcast_to_user(user_id, message)

    # -------------------
    # Dispatched/Queued 訊息處理
    # -------------------
    async def handle_ros_dispatched_queued(self, message: dict):
        """
        處理 ROS dispatched/queued 訊息：
        1. 推送給 Web
        2. 更新訂單狀態
        3. 指派 driver
        4. 儲存路線資料
        """
        user_id = message.get("user_id")
        order_id = message.get("order_id")
        assigned_vehicle = message.get("vehicle")
        t = message.get("type")

        if not user_id:
            print("收到 dispatched/queued 訊息，但沒有 user_id，無法轉發")
            return

        # --- 1. 推送給 Web ---
        await self.server_ws.broadcast(message, client_type="web")

        # --- 2. 更新訂單狀態 & 指派 driver & 儲存路線 ---
        async with AsyncSessionLocal() as db:  # 自己開 session
            try:
                async with db.begin():  # 事務開始
                    # 取得訂單
                    result = await db.execute(select(Order).where(Order.order_id == order_id))
                    order = result.scalars().first()

                    if not order:
                        print(f"找不到 order_id={order_id} 的訂單")
                        return

                    # 更新 status
                    if t == "dispatched":
                        order.status = OrderStatus.ASSIGNED.value
                        route_type = OrderStatus.ASSIGNED.value
                    elif t == "queued":
                        order.status = OrderStatus.ACCEPTED.value
                        route_type = OrderStatus.ACCEPTED.value
                    else:
                        print(f"未知的 route type: {t}")
                        return

                    # 指派 driver
                    if assigned_vehicle:
                        driver_result = await db.execute(select(Driver).where(Driver.name == assigned_vehicle))
                        driver = driver_result.scalars().first()
                        if driver:
                            order.driver_id = driver.id
                            print(f"指派 driver {driver.id} 給訂單 {order.order_id}")
                        else:
                            print(f"找不到 driver 對應 {assigned_vehicle}")
                    else:
                        print("沒有 assigned_vehicle，跳過指派 driver")

                    # --- 3. 儲存 route ---
                    # 檢查是否已有該 order 的 route（有的話更新，沒有就新增）
                    existing_route = await db.get(PendingHistory, order_id)
                    if existing_route:
                        existing_route.event_data = message
                        print(f"更新 Pending History: order_id={order_id}")
                    else:
                        new_route = PendingHistory(
                            order_id=order_id,
                            event_data = message
                        )
                        db.add(new_route)
                        print(f"新增 Pending History: order_id={order_id}")

                print(f"訂單已更新 {t} 資料，order_id={order_id}")

            except SQLAlchemyError as e:
                print("處理 dispatched/queued 時發生資料庫錯誤:", e)

    # -------------------
    # Ready 2 trip 訊息處理
    # -------------------
    async def handle_ros_ready_to_trip(self, message: dict):
        user_id = message.get("user_id")
        try:    await self.server_ws.broadcast_to_user(user_id, message)
        except Exception as e:
                print("broadcast_to_user(ready2trip) error:", e)

    # -------------------
    # Update eta 訊息處理
    # -------------------
    async def handle_ros_update_eta(self, message: dict):
        await self.server_ws.broadcast(message, client_type="web")
        name=message.get("vehicle_name")
        for user_id in self.vehicle_user_map.get(name, set()):
            await self.server_ws.broadcast_to_user(user_id, message)

    # -------------------
    # web刷新資料傳送
    # -------------------
    async def send_pending_orders(self):
        """
        將 status = 1/2/3 的 pending history 傳給所有 web 客戶端
        """
        try:
            async with AsyncSessionLocal() as db:
                # 用 relationship join
                result = await db.execute(
                    select(PendingHistory)
                    .join(PendingHistory.order)
                    .where(Order.status.in_([1, 2, 3]))
                )
                records = result.scalars().all()

                for record in records:
                    await self.server_ws.broadcast(record.event_data, client_type="web")
                
                print(f"已推送 {len(records)} 筆 pending history 給 web")
        
        except Exception as e:
            print("推送 pending history 發生錯誤:", e)
