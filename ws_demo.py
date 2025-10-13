from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import uvicorn
import json

app = FastAPI()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("新連線已建立")

    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                client_type = message.get("client_type", "unknown")
                msg = message.get("msg", "")
                print(f"收到來自 {client_type} 的訊息: {msg}")
            except json.JSONDecodeError:
                print(f"收到非 JSON 格式資料: {data}")

    except WebSocketDisconnect:
        print("客戶端已斷線")

if __name__ == "__main__":
    uvicorn.run("ws_demo:app", host="0.0.0.0", port=8000, reload=True)
