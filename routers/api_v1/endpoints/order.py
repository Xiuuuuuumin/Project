from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from uuid import uuid4
from database import get_db
from models import Order, User
from schemas import OrderCreate, OrderCreateRp, OrderUpdate, OrderHistoryRp
from services import get_current_user, admin_viewer_required
from enums import OrderStatus
from typing import List
from ws_modules.global_ws import manager
import asyncio
import datetime

from pytz import timezone
from datetime import timezone as dt_timezone

router = APIRouter()

#create new order
@router.post(
    "",
    response_model=OrderCreateRp,
    tags=["Order"],
    summary="Create new order",
    description="""
### 建立新訂單

此端點用於客戶建立一個新的乘車訂單。

**安全性：**
需在 Header 中提供有效的 **JWT Access Token**。
`Authorization: Bearer <your_token>`

**請求參數 (`OrderCreate` 範例):**
| 欄位 | 類型 | 必填 | 說明 |
| :--- | :--- | :--- | :--- |
| `pickup_lat` | `float` | 是 | 上車地點緯度 |
| `pickup_lng` | `float` | 是 | 上車地點經度 |
| `dropoff_lat` | `float` | 是 | 下車地點緯度 |
| `dropoff_lng` | `float` | 是 | 下車地點經度 |
| `pickup_name` | `str` | 否 | 上車地點名稱 |
| `dropoff_name` | `str` | 否 | 下車地點名稱 |

**回應欄位 (`OrderCreateRp`):**
- **order\_id** (str): 系統生成的訂單 ID。
- **status** (int): 訂單狀態碼 (初始為 0)。
- **message** (str): 執行結果描述。

**訂單狀態碼定義：**
| 狀態碼 | 意義 | 描述 |
| :--- | :--- | :--- |
| **0** | **PENDING** | **待派車** |
| 1 | ACCEPTED | 已接單 |
| 2 | ASSIGNED | 已派車 |
| 3 | IN\_PROGRESS | 行程中 |
| 4 | COMPLETED | 已完成 |
| 5 | CANCELLED | 已取消 |

**錯誤處理：**
- **401 Unauthorized**: JWT 令牌無效或過期。
- **400 Bad Request**: 用戶 ID 不存在 (ForeignKey 錯誤)。
"""
)
async def create_order(
    order_in: OrderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order_id = uuid4().hex
    order = Order(
        order_id=order_id,
        user_id=current_user.id,  # id from jwt token
        pickup_lat=order_in.pickup_lat,
        pickup_lng=order_in.pickup_lng,
        dropoff_lat=order_in.dropoff_lat,
        dropoff_lng=order_in.dropoff_lng,
        pickup_name=order_in.pickup_name,
        dropoff_name=order_in.dropoff_name,
        status=OrderStatus.PENDING.value,
    )

    try:
        db.add(order)
        db.commit()
        db.refresh(order)
    except IntegrityError as e:
        db.rollback()
        if "foreign key" in str(e.orig).lower():
            raise HTTPException(status_code=400, detail="User ID or Driver ID not exist.")
        else:
            raise HTTPException(status_code=500, detail="Database error.")
        
    ros_message = {
        "type": "dispatch",
        "user_id": order.user_id,
        "pick_up": {
            "lat": order.pickup_lat,
            "lng": order.pickup_lng,
        },
        "drop_off": {
            "lat": order.dropoff_lat,
            "lng": order.dropoff_lng,
        },
    }

    asyncio.create_task(manager.broadcast_to_ros(ros_message))

    return OrderCreateRp(
        order_id=order.order_id,
        status=order.status,
        message="Order created successfully"
    )

#update order status
@router.put(
    "/{order_id}",
    response_model=OrderCreateRp,
    tags=["Order"],
    summary="Update order status",
    description="""
    Update an existing order's status by numeric code.

    *Status Codes:*
    - 0 = PENDING
    - 1 = ASSIGNED
    - 2 = ACCEPTED
    - 3 = IN_PROGRESS
    - 4 = COMPLETED
    - 5 = CANCELLED

    *Response Fields:*
    - order_id
    - status

    Bearer JWT access token required in the `Authorization` header:

    ```
    Authorization: Bearer <your_token>
    ```
    """
)
def update_order(
    order_id: str,
    order_in: OrderUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # 1. 找訂單
    order = db.query(Order).filter(Order.order_id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # 2. 權限檢查：admin 可修改任何訂單，普通使用者只能改自己的
    try:
        admin_viewer_required(current_user, db)
    except HTTPException:
        # 不是 admin，就要檢查是否是訂單本人
        if order.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized to update this order")

    # 3. 更新狀態與時間
    order.status = order_in.status
    order.updated_at = datetime.datetime.now(datetime.timezone.utc)
    db.commit()
    db.refresh(order)

    # 4. 回傳結果
    return OrderCreateRp(order_id=order.order_id, status=order.status)

#get order history
@router.get(
    "/history",
    response_model=List[OrderHistoryRp],
    tags=["Order"],
    summary="Get user order history",
    description="""
### 取得用戶訂單歷史 (Order History)

此端點用於已驗證的用戶，**依時間倒序** (`created_at.desc()`) 取得所有已建立的訂單紀錄清單。

**安全性：**
需在 Header 中提供有效的 **JWT Access Token**。系統僅返回該 **JWT 所屬用戶**的歷史訂單。
`Authorization: Bearer <your_token>`

---

**回應 (Response Model):**
- 成功返回 **`List[OrderHistoryRp]`** 清單模型。
- 每個清單項目包含訂單的座標、地點名稱、乘客數、是否接受共乘 (`accept_pooling`)，以及訂單建立日期 (`date`)。

**錯誤處理：**
- **401 Unauthorized**: JWT 令牌無效或過期。
- **200 OK**: 如果該用戶沒有任何歷史訂單，則返回一個 **空清單 `[]`**。
"""
)
def get_order_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    orders = (
        db.query(Order)
        .filter(Order.user_id == current_user.id)
        .order_by(Order.created_at.desc())
        .all()
    )

    return [
        OrderHistoryRp(
            pickup_lat=o.pickup_lat,
            pickup_lng=o.pickup_lng,
            dropoff_lat=o.dropoff_lat,
            dropoff_lng=o.dropoff_lng,
            pickup_name=o.pickup_name,
            dropoff_name=o.dropoff_name,
            passengers=o.passengers,
            accept_pooling=o.accept_pooling,
            date=o.created_at
        )
        for o in orders
    ]

#Get Single Order
@router.get(
    "/{order_id}", 
    response_model=OrderCreateRp, 
    tags=["Order"],
    summary="Get Single Order",
    description="""
### 取得單一訂單資訊

此端點允許已驗證的用戶，根據其 **訂單 ID** 取得該筆訂單的詳細資訊。

**安全性：**
需在 Header 中提供有效的 **JWT Access Token**。用戶只能查詢**自己**所建立的訂單。
`Authorization: Bearer <your_token>`

**路徑參數 (Path Parameter):**
- **order\_id** (str): 欲查詢的訂單的唯一 ID。

---

**成功回應 (Response Model: OrderCreateRp):**
- 成功返回 **`OrderCreateRp`** 模型 (包含訂單 ID 和當前狀態)。
- **Status 狀態碼定義** 請參考 `Create New Order` 端點的文件說明。

**錯誤處理：**
- **401 Unauthorized**: JWT 令牌無效或過期。
- **403 Forbidden**: 嘗試查詢**非本人**的訂單。
- **404 Not Found**: 該 `order_id` 不存在。
""" # 請在此處插入 description 內容
)
def get_order(
    order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    order = db.query(Order).filter(Order.order_id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to view this order")
    return OrderCreateRp(order_id=order.order_id, status=order.status, message="Success")

#Delete Order
@router.delete("/{order_id}", response_model=dict, tags=["Order"])
def delete_order(
    order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # 檢查是否為 admin
    admin_viewer_required(current_user, db)
    
    order = db.query(Order).filter(Order.order_id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    db.delete(order)
    db.commit()
    return {"message": "Order deleted successfully", "order_id": order_id}

