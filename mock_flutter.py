import asyncio
import websockets
import json

async def websocket_client():
    uri = "wss://4f02b8beafae.ngrok-free.app/ws?client_type=flutter"  # 改成你的 server URL
    try:
        async with websockets.connect(uri) as ws:
            print("WebSocket 已連線")

            # 發送初始訊息
            init_message = {
                "client_type": "flutter",
                "msg": "hello from flutter"
            }
            await ws.send(json.dumps(init_message))
            print(f"已傳送: {init_message}")

            # 持續接收 server 訊息並印出
            async def receive():
                try:
                    while True:
                        message = await ws.recv()
                        try:
                            data = json.loads(message)
                            print(f"收到 server 訊息: {data}")
                        except json.JSONDecodeError:
                            print(f"收到非 JSON 訊息: {message}")
                except websockets.ConnectionClosed:
                    print("WebSocket 已斷線 (receive)")

            # 可選：持續發送心跳或自動訊息
            async def heartbeat():
                try:
                    while True:
                        await asyncio.sleep(10)
                        ping_msg = {"client_type": "flutter", "msg": "ping"}
                        await ws.send(json.dumps(ping_msg))
                        print(f"發送心跳: {ping_msg}")
                except websockets.ConnectionClosed:
                    print("WebSocket 已斷線 (heartbeat)")

            # 同時運行接收和心跳
            await asyncio.gather(receive(), heartbeat())

    except Exception as e:
        print("WebSocket 連線失敗:", e)

# 執行
asyncio.run(websocket_client())
