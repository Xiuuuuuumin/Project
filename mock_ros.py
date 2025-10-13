import asyncio
import websockets
import json
import math
import random
import time

SERVER_URI = "wss://9af787e35e73.ngrok-free.app/ws?client_type=ros"


def generate_route(pick_up, drop_off):
    route = [
        {"lat": pick_up["lat"], "lng": pick_up["lon"]},
        {"lat": (pick_up["lat"] + drop_off["lat"]) / 2, "lng": (pick_up["lon"] + drop_off["lon"]) / 2},
        {"lat": drop_off["lat"], "lng": drop_off["lon"]}
    ]
    return route


# 模擬 odom（車輛狀態）資料
def generate_odom(step):
    # 固定起點
    base_lat = 24.066758109127647
    base_lon = 120.55916552982933

    # 模擬繞圈運動
    radius = 0.0005
    lat = base_lat + radius * math.cos(step / 10)
    lon = base_lon + radius * math.sin(step / 10)
    yaw = (step * 5) % 360  # 模擬旋轉角度

    odom = {
        "type": "odom",
        "name": "ego_vehicle",
        "pose": {
            "position": {"lat": lat, "lon": lon},
            "yaw": yaw
        }
    }
    return odom


async def send_odom(ws):
    """持續發送 odom 給 server"""
    step = 0
    while True:
        odom = generate_odom(step)
        await ws.send(json.dumps(odom, ensure_ascii=False))
        #print("已發送 odom：", json.dumps(odom, ensure_ascii=False))
        step += 1
        await asyncio.sleep(1)  # 每秒一次


async def ros_client():
    async with websockets.connect(SERVER_URI) as ws:
        print("已連線到伺服器，等待接收任務...")

        # ✅ 同步執行：接收 server 指令 + 定期送 odom
        recv_task = asyncio.create_task(handle_server_messages(ws))
        odom_task = asyncio.create_task(send_odom(ws))

        done, pending = await asyncio.wait(
            [recv_task, odom_task],
            return_when=asyncio.FIRST_COMPLETED
        )

        # 若任一結束，關閉另一個
        for task in pending:
            task.cancel()


async def handle_server_messages(ws):
    """處理 server 下達的任務（例如 route_preview）"""
    try:
        while True:
            msg = await ws.recv()
            data = json.loads(msg)
            print("收到訊息：", json.dumps(data, indent=4, ensure_ascii=False))

            payload = data.get("payload", data)
            if payload.get("type") == "route_preview":
                message_id = payload.get("message_id")
                user_id = payload.get("user_id")
                pick_up = payload.get("pick_up")
                drop_off = payload.get("drop_off")

                # 生成路線
                path = generate_route(pick_up, drop_off)

                # 回傳路線
                response = {
                    "type": "route_preview_result",
                    "message_id": message_id,
                    "user_id": user_id,
                    "path": path
                }
                await ws.send(json.dumps(response, ensure_ascii=False))
                print("已回傳路線：", json.dumps(response, indent=4, ensure_ascii=False))

    except websockets.ConnectionClosed:
        print("與伺服器連線中斷")


if __name__ == "__main__":
    asyncio.run(ros_client())
