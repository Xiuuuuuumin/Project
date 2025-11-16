# Project
Robotaxi

## WebSocket 使用指南
### 1. 架構概述
專案 WebSocket Server 支援三種 client：
			Client Type
			認證
			說明
			web
			Yes (Admin / Viewer)
			管理員前端，需傳 token 認證
			flutter
			Yes (User)
			行動端使用者，需傳 token + user_id 認證
			ros
			No
			ROS 機器人端，直接連線即可傳送訊息
所有 client 透過相同 WebSocket endpoint：
```
wss://your-domain.com/ws?client_type=<client_type>

```
### 2. 連線流程
#### 2.1 Web (管理員)
1. 建立 WebSocket 連線：
```
const ws = new WebSocket("wss://your-domain.com/ws?client_type=web");

```
1. 連線成功後送認證訊息：
```
ws.onopen = () => {
    ws.send(JSON.stringify({ token: "YOUR_BEARER_TOKEN" }));
};

```
1. 收到登入成功回覆：
```
{
    "type": "auth",
    "status": "success",
    "message": "Manager 22 connection established."
}

```
1. 傳送訊息：
```
ws.send(JSON.stringify({ msg: "Hello server!" }));

```
#### 2.2 Flutter (一般使用者)
1. 建立 WebSocket 連線：
```
final ws = WebSocket.connect("wss://your-domain.com/ws?client_type=flutter");

```
1. 連線成功後送認證訊息：
```
ws.add(jsonEncode({
  "token": "YOUR_BEARER_TOKEN",
  "user_id": 22,
  "vehicle_name": assign_vehicle
  "order_id": order_id
}));

```
1. 收到登入成功回覆：
```
{
    "type": "auth",
    "status": "success",
    "message": "User 22 connection established."
}

```
1. 傳送訊息：
```
ws.add(jsonEncode({ "msg": "Hello server!" }));

```
#### 2.3 ROS (無需認證)
1. 建立 WebSocket 連線：
```
import websockets
ws = await websockets.connect("wss://your-domain.com/ws?client_type=ros")

```
1. 直接傳送訊息：
```
await ws.send(json.dumps({"type": "odom", "data": {...}}))

```
### 3. 錯誤與斷線處理
			錯誤代碼
			原因
			4001
			JSON 解析錯誤
			4002
			缺少 token
			4003
			缺少 user_id（Flutter）
			4004
			認證逾時
			4005
			User ID 與 token 不符
### 4. 訊息格式建議
- 通用 JSON 格式：
```
{
    "type": "message_type",
    "msg": "訊息內容",
    "extra": {...}  // 可選
}

```
- ROS 特殊訊息：
```
// odom (更新車輛即時位置)
// ros -> server | server -> flutter & web
{
    "type": "odom",
	"name": "hero0",
    "pose": {"position": {"lat": 24.06695567075799, "lon": 120.55870621577314}, "yaw": 20}
}

// estimate (路線規劃請求api)
// flutter -> server -> ros
{
    "type": "estimate",
    "message_id": message_id,
    "user_id": current_user.id,
    "pick_up": {"lat": req.pickup_lat, "lng": req.pickup_lng},
    "drop_off": {"lat": req.dropoff_lat, "lng": req.dropoff_lng},
}
// ros -> server -> flutter
{
	"type": "estimate"
	"user_id": user_id,
	"message_id": message_id,
	"best_vehicle": best_role,
	"eta_min": round(min(e for e, , _ in eta_list) / 60.0),
 	"eta_max": round(max(e for e, , _ in eta_list) / 60.0),
	 "path": route_best,
}

// dispatch (請求派車)
// flutter -> server -> ros
{
    "type": "dispatch",
	"passengers": order.passengers,
	"accept_pooling": order.accept_pooling,
    "user_id": order.user_id,
	"order_id": order.order_id,
    "pick_up": {
        "lat": order.pickup_lat,
        "lng": order.pickup_lng,
    },
    "drop_off": {
        "lat": order.dropoff_lat,
        "lng": order.dropoff_lng,
    },
}

// dispatched (派車)
// ros -> server -> flutter
{
    "type": "dispatched",
    "user_id":user_id,
	"order_id": order_id,
    "vehicle": best_role,
    "eta_to_pick": round(eta_to_pick),
    "eta_trip": round(eta_trip),
	"total_distance_m": ,
    "path1": [],
    "path2": [],
}

// queued (等車)
// ros -> server -> flutter
{
	"type": "queued",
	"user_id": user_id,
	"order_id": order_id,
	"vehicle": best_role,
	"eta_wait_sec": round(eta_to_pick, 1),
	"path2": route_trip,
	"message": f"目前車輛忙碌，預計約 {eta_to_pick:.1f} 秒後可上車"
}

// update_eta (接乘客的過程)
// ros -> server -> flutter
{
	"type": "update_eta",
	"vehicle_name":role,
	"user_id":user_id,
	"order_id":order_id,
	"eta_remaining":eta_remaining,
	"phase": "pickup"
}

// ready_2_trip (請上車)
// ros -> server -> flutter
{
	"type": "ready_2_trip",
	"vehicle_name": vehicle_name,
	"user_id": user_id
}

// geton (上車)
// flutter -> server -> ros
{
	"type": "geton",
	"vehicle_name": vehicle_name,
	"order_id": order_id
}

// trip (出發)
// ros -> server -> flutter
{
	"type": "trip",
	"vehicle_name": vehicle_name,
	"order_id": order_id
}

// update_eta (載客的過程)
// ros -> server -> flutter
{
	"type": "update_eta",
	"vehicle_name":role,
	"user_id":user_id,
	"order_id":order_id,
	"eta_remaining":eta_remaining,
	"phase": "trip"
}

// arrive (抵達目的地)
// ros -> server -> flutter
{
	"type": "arrive",
	"vehicle_name": vehicle_name,
	"order_id": order_id
}

// getoff (下車)
// flutter -> server -> ros
{
	"type": "getoff",
	"vehicle_name": vehicle_name,
	"order_id": order_id
}

// cancle (取消訂單)
// flutter -> server -> ros
{
	"type": "cancel",
	"order_id": order_id,
	"vehicle_name": vehicle_name
}

```
### 5. 注意事項
1. Web / Flutter 端需在連線後立即送認證訊息，否則伺服器會自動斷線（timeout 5 秒）。
2. Flutter 端 user_id 必須與 token 對應，否則連線會被拒絕。
3. ROS 無需認證，但要確保訊息格式正確。
4. 若要傳訊息給指定使用者，可透過 server 綁定的 user_map[user_id] 對應 WebSocket。


## WebSocket 聊天室

### 🧊 1. **進入聊天室：join**

### 用戶加入特定 order 的聊天房間

（Web 可反覆加入不同房間）

### Client → Server

```json
{
  "type": "chat",
  "action": "join",
  "payload": ""            // flutter: 空字串
}

```

```json
{
  "type": "chat",
  "action": "join",
  "payload": "order_id"    // web: 指定 order_id
}

```

### Server → Client（請求歷史訊息）

```json
{
  "type": "chat",
  "action": "history",
  "payload": null}

```

### Server → Client（回傳歷史訊息）

```json
{
  "type": "chat",
  "action": "history",
  "payload": {
    "order_id": "146f35ebdf7f...",
    "messages": [
      {
        "sender_id": 19,
        "sender_type": "user",
        "content": "hello",
        "timestamp": "2025-11-15T12:00:00Z"
      }
    ]
  }
}

```

---

### 📝 2. **發送訊息：send**

### Client → Server

```json
{
  "type": "chat",
  "action": "send",
  "payload": "請問車在哪？"
}

```

### Server → 所有在房內的 Client（推播）

```json
{
  "type": "chat",
  "action": "message",
  "payload": {
    "order_id": "146f35ebdf7f...",
    "sender_id": 19,
    "sender_type": "user",
    "content": "請問車在哪？",
    "timestamp": "2025-11-15T20:30:12Z"
  }
}

```

---

### 📨 3. **推播新訊息：message**

（Server 主動推播到房內成員）

```json
{
  "type": "chat",
  "action": "message",
  "payload": {
    "order_id": "146f35ebdf7f...",
    "sender_id": 9,
    "sender_type": "driver",
    "content": "我在門口囉。",
    "timestamp": "2025-11-15T20:31:00Z"
  }
}

```

---

### 🚪 4. **離開聊天室：leave**

（Web 切換 order 時也會呼叫）

### Client → Server

```json
{
  "type": "chat",
  "action": "leave"
}

```

### Server → 房內其他 Client

```json
{
  "type": "chat",
  "action": "member_left",
  "payload": "user#19 left the room"
}

```

### Server → 離開者本人

```json
{
  "type": "chat",
  "action": "left"
}

```
