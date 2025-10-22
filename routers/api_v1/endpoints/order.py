from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select, and_
from uuid import uuid4
from database import get_db
from models import Order, User
from schemas import OrderCreate, OrderCreateRp, OrderUpdate, OrderHistoryRp
from services import get_current_user, admin_viewer_required
from enums import OrderStatus
from typing import List
from ws_modules.global_ws import manager
import asyncio
from datetime import datetime, timezone as dt_timezone

router = APIRouter()

#create new order
@router.post(
    "",
    #response_model=OrderCreateRp,
    tags=["Order"],
    summary="Create new order",
    description="""
### 建立新訂單

此端點用於客戶建立一個新的乘車訂單，並將該客戶所有待派車的訂單標為已取消。

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
- **order_id** (str): 系統生成的訂單 ID。
- **status** (int): 訂單狀態碼 (初始為 0)。
- **message** (str): 執行結果描述。

**訂單狀態碼定義：**
| 狀態碼 | 意義 | 描述 |
| :--- | :--- | :--- |
| **0** | **PENDING** | **待派車** |
| 1 | ACCEPTED | 已接單 |
| 2 | ASSIGNED | 已派車 |
| 3 | IN_PROGRESS | 行程中 |
| 4 | COMPLETED | 已完成 |
| 5 | CANCELLED | 已取消 |

**錯誤處理：**
- **401 Unauthorized**: JWT 令牌無效或過期。
- **400 Bad Request**: 用戶 ID 不存在 (ForeignKey 錯誤)。
"""
)
async def create_order(
    order_in: OrderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # 取消 user 的待派車訂單
    try:
        result = await db.execute(
            select(Order).where(
                and_(
                    Order.user_id == current_user.id,
                    Order.status == OrderStatus.PENDING.value
                )
            )
        )
        pending_orders = result.scalars().all()
        
        for o in pending_orders:
            o.status = OrderStatus.CANCELLED.value

        if pending_orders:
            await db.commit()
            print(f"已將 user {current_user.id} 的 {len(pending_orders)} 個待派車訂單標記為取消")
    except Exception as e:
        await db.rollback()
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail="Failed to cancel old pending orders")

    order_id = uuid4().hex
    order = Order(
        order_id=order_id,
        user_id=current_user.id,
        pickup_lat=order_in.pickup_lat,
        pickup_lng=order_in.pickup_lng,
        dropoff_lat=order_in.dropoff_lat,
        dropoff_lng=order_in.dropoff_lng,
        pickup_name=order_in.pickup_name,
        dropoff_name=order_in.dropoff_name,
        passengers=order_in.passengers,
        accept_pooling=order_in.accept_pooling,
        status=OrderStatus.PENDING.value,
    )
    
    try:
        db.add(order)
        await db.commit()
        await db.refresh(order)
    except IntegrityError as e:
        await db.rollback()
        if "foreign key" in str(e.orig).lower():
            raise HTTPException(status_code=400, detail="User ID or Driver ID not exist.")
        else:
            raise HTTPException(status_code=500, detail="Database error.")
    
    ros_message = {
        "type": "dispatch",
        "order_id": order.order_id,
        "passengers": order.passengers,
        "accept_pooling": order.accept_pooling,
        "user_id": order.user_id,
        "pick_up": {"lat": order.pickup_lat, "lng": order.pickup_lng},
        "drop_off": {"lat": order.dropoff_lat, "lng": order.dropoff_lng},
    }

    web_message = {
        "type": "get_new_order"
    }

    asyncio.create_task(manager.broadcast_to_ros(ros_message))
    asyncio.create_task(manager.broadcast_to_web(web_message))

    try:
        ros_response = await manager.wait_for_ros_response(order_id, timeout=10)
    except asyncio.TimeoutError:
        return {"status": "failed", "msg": "ROS dispatch timeout"}
    
    return ros_response
    #OrderCreateRp dumped

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
async def update_order(
    order_id: str,
    order_in: OrderUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # 找訂單 (ORM select)
    result = await db.execute(select(Order).where(Order.order_id == order_id))
    order = result.scalars().first()  # 使用 first() 或 scalar_one_or_none() 都可以
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # 權限檢查
    try:
        await admin_viewer_required(current_user, db)
    except HTTPException:
        if order.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized to update this order")

    # 更新欄位
    order.status = order_in.status
    order.updated_at = datetime.now(dt_timezone.utc)

    try:
        await db.commit()
        await db.refresh(order)
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update order: {e}")

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
async def get_order_history(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(Order).where(Order.user_id == current_user.id).order_by(Order.created_at.desc())
    )
    orders = result.scalars().all()

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
- **order_id** (str): 欲查詢的訂單的唯一 ID。

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
async def get_order(
    order_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # ORM select
    result = await db.execute(select(Order).where(Order.order_id == order_id))
    order = result.scalars().first()  # 拿到單一 ORM 物件
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # 權限檢查
    if current_user.role not in ["admin", "viewer"] and order.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to update this order")

    return OrderCreateRp(order_id=order.order_id, status=order.status, message="Success")

#Delete Order
@router.delete("/{order_id}", response_model=dict, tags=["Order"])
async def delete_order(
    order_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    await admin_viewer_required(current_user, db)

    result = await db.execute(select(Order).where(Order.order_id == order_id))
    order = result.scalars().first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    await db.delete(order)
    await db.commit()
    return {"message": "Order deleted successfully", "order_id": order_id}

