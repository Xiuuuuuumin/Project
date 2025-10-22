import asyncio
import websockets
import json
import math
import random
import time

SERVER_URI = "wss://b1b9b48f07b2.ngrok-free.app/ws?client_type=ros"


def generate_route(pick_up, drop_off):
    route = [
        {"lat": pick_up["lat"], "lng": pick_up["lng"]},
        {"lat": (pick_up["lat"] + drop_off["lat"]) / 2, "lng": (pick_up["lng"] + drop_off["lng"]) / 2},
        {"lat": drop_off["lat"], "lng": drop_off["lng"]}
    ]
    return route


# 模擬 odom（車輛狀態）資料
def generate_odom(step):
    # 固定起點
    base_lat = 24.066758109127647
    base_lng = 120.55916552982933

    # 模擬繞圈運動
    radius = 0.0005
    lat = base_lat + radius * math.cos(step / 10)
    lng = base_lng + radius * math.sin(step / 10)
    yaw = (step * 5) % 360  # 模擬旋轉角度

    odom = {
        "type": "odom",
        "name": "hero1",
        "pose": {
            "position": {"lat": lat, "lon": lng},
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

async def handle_server_messages(ws):
    """處理 server 下達的任務（例如 route_preview）"""
    try:
        while True:
            msg = await ws.recv()
            data = json.loads(msg)
            print("收到訊息：", json.dumps(data, indent=4, ensure_ascii=False))

            payload = data.get("payload", data)
            msg_type = payload.get("type")

            # ----- route preview -----
            if msg_type == "estimate":
                message_id = payload.get("message_id")
                user_id = payload.get("user_id")
                pick_up = payload.get("pick_up")
                drop_off = payload.get("drop_off")

                # 生成路線
                path = generate_route(pick_up, drop_off)

                # 回傳路線
                response = {
                    "type": "estimate",
                    'user_id': user_id,
                    "message_id": message_id,
                    'best_vehicle': 'hero0',
                    'eta_min': 0,
                    'eta_max': 2,
                    'path': [{'lat': 24.064777769061333, 'lng': 120.55851330403439}, {'lat': 24.06477272537694, 'lng': 120.55852139431113}, {'lat': 24.064767658548273, 'lng': 120.55852946778198}, {'lat': 24.064762568575343, 'lng': 120.5585375244469}, {'lat': 24.064757455458192, 'lng': 120.55854556310564}, {'lat': 24.064752320298933, 'lng': 120.55855358435834}, {'lat': 24.06474749707599, 'lng': 120.55856082063846}, {'lat': 24.064742440233683, 'lng': 120.55856737034041}, {'lat': 24.06473695248007, 'lng': 120.55857349331603}, {'lat': 24.064731064676117, 'lng': 120.55857915835945}, {'lat': 24.064724807682794, 'lng': 120.55858433306456}, {'lat': 24.06471821566727, 'lng': 120.55858898982663}, {'lat': 24.064711326102977, 'lng': 120.55859310284154}, {'lat': 24.064704175361086, 'lng': 120.55859664930581}, {'lat': 24.06469680311898, 'lng': 120.5585996100171}, {'lat': 24.064689251258137, 'lng': 120.55860196877384}, {'lat': 24.064681558353524, 'lng': 120.55860371237507}, {'lat': 24.064664447758357, 'lng': 120.55860636768384}, {'lat': 24.064664447758357, 'lng': 120.55860636768384}, {'lat': 24.064655924980755, 'lng': 120.55860753450116}, {'lat': 24.06464737466182, 'lng': 120.55860844385516}, {'lat': 24.064638805618607, 'lng': 120.55860909454601}, {'lat': 24.064630224463947, 'lng': 120.55860948477375}, {'lat': 24.06462145926531, 'lng': 120.55860964033525}, {'lat': 24.06461243176321, 'lng': 120.55860975147188}, {'lat': 24.064603403158973, 'lng': 120.55860986260839}, {'lat': 24.064594375656856, 'lng': 120.55860997374496}, {'lat': 24.064585348154726, 'lng': 120.55861008488154}, {'lat': 24.064576319550458, 'lng': 120.55861019601802}, {'lat': 24.064567292048302, 'lng': 120.55861030715454}, {'lat': 24.064558263444013, 'lng': 120.55861041829101}, {'lat': 24.06454923594181, 'lng': 120.55861053002764}, {'lat': 24.064540207337497, 'lng': 120.55861064116408}, {'lat': 24.064531179835306, 'lng': 120.55861075230055}, {'lat': 24.06452215123097, 'lng': 120.55861086343694}, {'lat': 24.064513123728755, 'lng': 120.55861097457338}, {'lat': 24.06450337102854, 'lng': 120.55861109527271}, {'lat': 24.06450337102854, 'lng': 120.55861109527271}, {'lat': 24.064494343526302, 'lng': 120.55861120640913}, {'lat': 24.064485314921928, 'lng': 120.55861131754544}, {'lat': 24.064476287419666, 'lng': 120.55861142868181}, {'lat': 24.06446725881527, 'lng': 120.55861153981813}, {'lat': 24.064458231312987, 'lng': 120.55861165095448}, {'lat': 24.064449202708563, 'lng': 120.55861176209073}, {'lat': 24.06444017520626, 'lng': 120.55861187322705}, {'lat': 24.06443114660183, 'lng': 120.55861198436328}, {'lat': 24.064422119099472, 'lng': 120.55861209609971}, {'lat': 24.064413090495012, 'lng': 120.55861220723592}, {'lat': 24.064404062992658, 'lng': 120.55861231837218}, {'lat': 24.064395034388184, 'lng': 120.55861242950836}, {'lat': 24.06438600688581, 'lng': 120.55861254064456}, {'lat': 24.064376978281313, 'lng': 120.55861265178073}, {'lat': 24.064367950778916, 'lng': 120.55861276291692}, {'lat': 24.06435892327652, 'lng': 120.55861287405308}, {'lat': 24.06434989467198, 'lng': 120.5586129851892}]
                }
                await ws.send(json.dumps(response, ensure_ascii=False))
                print("已回傳路線：", json.dumps(response, indent=4, ensure_ascii=False))

            # ----- dispatch 任務 -----
            elif msg_type == "dispatch":
                user_id = payload.get("user_id")
                pick_up = payload.get("pick_up")
                drop_off = payload.get("drop_off")
                order_id = payload.get("order_id")

                # 生成簡單路線 path2
                path2 = generate_route(pick_up, drop_off)

                dispatched_msg = {
                    "type": "dispatched",
                    "order_id": order_id,
                    "user_id": user_id,
                    "assigned_vehicle": "hero1",
                    "eta_to_pick": random.randint(20, 60),
                    "eta_trip": random.randint(60, 120),
                    "path1": path2,
                    "path2": path2
                }
                await ws.send(json.dumps(dispatched_msg, ensure_ascii=False))
                print("已傳送 dispatched 訊息：", json.dumps(dispatched_msg, indent=4, ensure_ascii=False))

    except websockets.ConnectionClosed:
        print("與伺服器連線中斷")


if __name__ == "__main__":
    asyncio.run(ros_client())
