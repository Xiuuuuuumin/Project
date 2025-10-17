from sqlalchemy.orm import Session
from models import Driver, Order, Route
from enums import OrderStatus
from geoalchemy2 import WKTElement
from database import get_db
import asyncio

class WebSocketManager:
    def __init__(self, server_ws):
        self.server_ws = server_ws
        self._tasks = set() #track background tasks
        self.pending_responses: dict[str, asyncio.Future] = {}  #wait for response
        self.vehicle_user_map: dict[str, set[str]] = {}  # vehicle_name → user_id


    async def start_background_tasks(self):
        task = asyncio.create_task(self.periodic_broadcast())
        self._tasks.add(task)

        # 自動移除完成的 task
        task.add_done_callback(lambda t: self._tasks.discard(t))

    async def stop_background_tasks(self):
        for task in list(self._tasks):
            task.cancel()
        # 等待所有 task 完全取消
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

    async def periodic_broadcast(self):
        while True:
            await asyncio.sleep(10)  # 每 10 秒推播
            await self.server_ws.broadcast({"client_type": "server", "msg": "ping"})

    async def broadcast_to_ros(self, ros_message: dict):
        """
        *for route api
        封裝發送給 ROS client 的訊息邏輯
        """
        await self.server_ws.broadcast(ros_message, client_type="ros")
        print("已推送給 ROS:", ros_message)

    """ async def broadcast_to_user(self, user_id: str, message: dict):
        websocket = self.server_ws.user_map.get(str(user_id))
        if websocket:
            # 檢查連線狀態
            if websocket.client_state.name != "CONNECTED":
                print(f"user {user_id} offline, remove from map")
                self.server_ws.user_map.pop(str(user_id), None)
                return

            try:
                await self.server_ws.send_json(websocket, message)
                print(f"Msg send to {user_id}: {message}")
            except Exception as e:
                print(f"handle_ros_odom error: {e}, remove user {user_id} connection")
                self.server_ws.user_map.pop(str(user_id), None)
        else:
            print(f"Failed to send, user {user_id} offline.") """

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

        await self.server_ws.broadcast(message, client_type="web")

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

        # 發送
        for user_id in self.vehicle_user_map.get(name, set()):
            await self.server_ws.broadcast_to_user(user_id, message)

    # -------------------
    # Dispatch 訊息處理
    # -------------------
    async def handle_ros_dispatched_queued(self, message: dict):
        """
        處理 ROS dispatched/queued 訊息：
        1. 推送給 Web
        2. 更新訂單狀態
        3. 存 routes table（path1 / path2 都存，存在則更新）
        """
        user_id = message.get("user_id")
        order_id = message.get("order_id")
        assigned_vehicle = message.get("assigned_vehicle")
        t = message.get("type")

        if not user_id:
            print("收到 dispatched/queued 訊息，但沒有 user_id，無法轉發")
            return

        # --- 1. 推送給 Web ---
        await self.server_ws.broadcast(message, client_type="web")

        db_session = next(get_db())
        """ try:
            # --- 2. 更新訂單狀態 ---
            order = db_session.query(Order).filter(Order.order_id == order_id).first()
            if order:
                if t == "dispatched":
                    order.status = OrderStatus.ASSIGNED.value
                elif t == "queued":
                    order.status = OrderStatus.ACCEPTED.value

                if assigned_vehicle:
                    driver = db_session.query(Driver).filter(Driver.name == assigned_vehicle).first()
                    if driver:
                        order.driver_id = driver.id
                        print(f"指派 driver {driver.id} 給訂單 {order.order_id}")
                    else:
                        print(f"找不到 driver 對應 {assigned_vehicle}")
                else:
                    print("沒有 assigned_vehicle，跳過指派 driver")
            else:
                print(f"找不到 order_id={order_id} 的訂單")

            # --- 3. 處理 routes ---
            route_data = {}
            for path_key in ["path1", "path2"]:
                path_list = message.get(path_key, [])
                if path_list:
                    points_str = ", ".join(f"{pt['lng']} {pt['lat']}" for pt in path_list)
                    linestring = f"SRID=4326;LINESTRING({points_str})"
                    route_data[path_key] = linestring
                else:
                    route_data[path_key] = None

            # 使用原生 SQL：若 order_id 已存在則更新
            sql = 
            INSERT INTO routes (order_id, user_id, vehicle_name, type, eta_to_pick, eta_trip, total_distance_m, path1, path2)
            VALUES (:order_id, :user_id, :vehicle_name, :type, :eta_to_pick, :eta_trip, :total_distance_m, 
                    ST_GeomFromEWKT(:path1), ST_GeomFromEWKT(:path2))
            ON CONFLICT (order_id) DO UPDATE SET
                user_id = EXCLUDED.user_id,
                vehicle_name = EXCLUDED.vehicle_name,
                type = EXCLUDED.type,
                eta_to_pick = EXCLUDED.eta_to_pick,
                eta_trip = EXCLUDED.eta_trip,
                total_distance_m = EXCLUDED.total_distance_m,
                path1 = EXCLUDED.path1,
                path2 = EXCLUDED.path2;
            

            db_session.execute(sql, {
                "order_id": order_id,
                "user_id": user_id,
                "vehicle_name": assigned_vehicle,
                "type": OrderStatus.ASSIGNED.value if t == "dispatched" else OrderStatus.ACCEPTED.value,
                "eta_to_pick": message.get("eta_to_pick"),
                "eta_trip": message.get("eta_trip"),
                "total_distance_m": message.get("total_distance_m"),
                "path1": route_data["path1"],
                "path2": route_data["path2"],
            })

            db_session.commit()
            print(f"訂單更新 & route table 已新增/更新 {t} 資料，order_id={order_id}")

        except Exception as e:
            db_session.rollback()
            print("處理 dispatched/queued 時發生錯誤:", e) """



    # -------------------
    # Ready to trip 訊息處理
    # -------------------
    async def handle_ros_ready_to_trip(self, message: dict):
        user_id = message.get("user_id")
        try:    await self.server_ws.broadcast_to_user(user_id, message)
        except Exception as e:
                print("broadcast_to_user(ready2trip) error:", e)


