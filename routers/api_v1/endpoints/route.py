from fastapi import APIRouter, Depends, HTTPException, Request
from models import User
from services import get_current_user
from ws_modules.global_ws import manager
from schemas import RoutePreviewRq
import asyncio, uuid

router = APIRouter()

@router.post(
    "/preview",
    tags=["Route"],
    summary="預覽路線",
    description="""
### 預覽路線 (Route Preview) 🗺️

此端點用於計算並預覽指定起點和終點之間的最佳行駛路線。

**流程說明：**
1. **客戶端 (Client)** 傳入起點、終點座標以及一個唯一的 `message_id`。
2. **Server** 驗證用戶身份並將請求轉發給 **ROS 系統** 進行路徑規劃。
3. **Server** 等待 ROS 計算結果。
4. **ROS 系統** 計算完成後，Server 直接將 ROS 返回的 JSON 資料回傳給客戶端。

**安全性：**
需在 Header 中提供有效的 **JWT Access Token**。
`Authorization: Bearer <your_token>`

---

**請求參數 (Request Body: RoutePreviewRq):**

| 欄位 | 類型 | 必填 | 說明 |
| :--- | :--- | :--- | :--- |
| `message_id` | `str` | 是 | **唯一請求 ID**，用於 Server 識別並匹配 ROS 的回傳結果。 |
| `pickup_lat` | `float` | 是 | 上車地點緯度。 |
| `pickup_lng` | `float` | 是 | 上車地點經度。 |
| `dropoff_lat` | `float` | 是 | 下車地點緯度。 |
| `dropoff_lng` | `float` | 是 | 下車地點經度。 |

**回應 (Response):**
- **類型：** 直接返回 ROS 系統計算結果的 **JSON 格式**。
- **結構：** 結構由 ROS 系統定義，通常包含路線、距離、預計時間等資訊。

**錯誤處理與特殊狀態碼：**

| HTTP 狀態碼 | 情境 | 說明 |
| :--- | :--- | :--- |
| **401 Unauthorized** | JWT 令牌無效或過期。 | |
| **504 Gateway Timeout** | Server 等待 **ROS 系統回傳結果超時** (超過 10 秒)。 | 表示 ROS 系統計算時間過長。 |
| **500 Internal Server Error** | Server 與 ROS 通訊失敗或處理結果時發生未預期錯誤。 | |
"""
)
async def preview_route(
    req: RoutePreviewRq,
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """ print("request headers:", request.headers)
    print("current_user:", current_user) """

    # Step 1. 使用前端傳入的 message_id
    message_id = req.message_id

    # Step 2. 準備要送給 ROS 的封包
    ros_message = {
        "type": "estimate",
        "message_id": message_id,
        "user_id": current_user.id,
        "pick_up": {"lat": req.pickup_lat, "lng": req.pickup_lng},
        "drop_off": {"lat": req.dropoff_lat, "lng": req.dropoff_lng},
    }

    try:
        # Step 3. 傳送給 ROS
        await manager.broadcast_to_ros(ros_message)

        # Step 4. 等待 ROS 回傳結果
        try:
            response = await manager.wait_for_ros_response(message_id, timeout=10)
            print("收到 ros 的訊息:", response)
        except asyncio.TimeoutError:
            raise HTTPException(status_code=504, detail="ROS response timeout")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error waiting for ROS response: {e}")

        # Step 5. 直接回傳 ROS JSON
        return response

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Route preview failed: {e}")
