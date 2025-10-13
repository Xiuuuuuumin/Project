from fastapi import APIRouter, Depends, Body
from sqlalchemy.orm import Session
from typing import List
from typing import Optional, Dict

from database import get_db 
from models import Order, User, Driver
from services import get_current_user, admin_viewer_required
from schemas import OrderListRq, OrderRp, PaginatedOrdersRp, OrderHistoryRp, TestRq, PaginatedUsersRp, UserListRq, UserRp, DriverRp


router = APIRouter()

@router.post("/order", response_model=List[OrderHistoryRp], tags=["Admin"])
def get_order_admin(
    payload: TestRq = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # 確認 admin 身分
    admin_viewer_required(current_user, db)

    orders = (
        db.query(Order)
        .order_by(Order.order_id.asc())
        .limit(10)
        .all()
    )

    result = [
        OrderHistoryRp(
            pickup_lat=o.pickup_lat,
            pickup_lng=o.pickup_lng,
            dropoff_lat=o.dropoff_lat,
            dropoff_lng=o.dropoff_lng,
            pickup_name=o.pickup_name,
            dropoff_name=o.dropoff_name,
            date=o.created_at  # 直接用 UTC
        )
        for o in orders
    ]

    return result

#get order table
@router.post(
    "/order/filter", 
    response_model=PaginatedOrdersRp, 
    tags=["Admin"],
    summary="訂單篩選與列表 (Admin)",
    description="""
### 訂單篩選與列表 (Order Filter & List) 🧑‍💻

此端點供系統管理員使用，用於**多條件篩選**和**分頁**查詢所有歷史訂單。

**安全性與權限：**
- 需在 Header 中提供有效的 **JWT Access Token**。
- **僅限**通過 `admin_required` 驗證的**管理員**身份才能訪問。
`Authorization: Bearer <your_token>`

---

**請求參數 (Request Body: OrderListRq):**
所有篩選欄位皆為 **非必填 (Optional)**，若不傳遞則不應用該篩選條件。

| 欄位 | 類型 | 說明 |
| :--- | :--- | :--- |
| `page` | `int` | **分頁頁碼**，預設為 `1`。 |
| `size` | `int` | **每頁筆數**，預設為 `10`。 |
| `status` | `List[int]` | 依據訂單狀態碼進行**多選**篩選 (例如：`[3, 4]` 查詢行程中和已完成的訂單)。 |
| `user_id` | `int` | 依特定用戶 ID 篩選。 |
| `driver_id` | `int` | 依特定司機 ID 篩選。 |
| `start_date` | `datetime` | **起始建立日期** (含)，日期格式需為 UTC 時間。 |
| `end_date` | `datetime` | **結束建立日期** (含)，日期格式需為 UTC 時間。 |
| `pickup_name` | `str` | 依上車地點名稱進行**模糊搜索** (`contains`)。 |
| `dropoff_name` | `str` | 依下車地點名稱進行**模糊搜索** (`contains`)。 |

---

**回應 (Response Model: PaginatedOrdersRp):**
返回一個包含分頁資訊和訂單資料清單的物件。

| 欄位 | 類型 | 說明 |
| :--- | :--- | :--- |
| `total` | `int` | 符合篩選條件的**總訂單數**。 |
| `page` | `int` | 當前頁碼。 |
| `size` | `int` | 每頁筆數。 |
| `data` | `List[OrderRp]` | 包含當前頁所有訂單詳細資訊的清單。 |

**錯誤處理：**
- **401 Unauthorized**: JWT 令牌無效或過期。
- **403 Forbidden**: 用戶身份**非管理員**。
- **422 Unprocessable Entity**: 請求參數格式錯誤 (例如：日期格式不正確)。
"""
)
def list_orders(
    payload: OrderListRq = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # 確認 admin 身分
    admin_viewer_required(current_user, db)

    filters = []

    # 篩選條件
    if payload.status:
        filters.append(Order.status.in_(payload.status))
    if payload.user_id is not None:
        filters.append(Order.user_id == payload.user_id)
    if payload.driver_id is not None:
        filters.append(Order.driver_id == payload.driver_id)

    # 日期篩選，直接用 UTC
    if payload.start_date:
        filters.append(Order.created_at >= payload.start_date)
    if payload.end_date:
        filters.append(Order.created_at <= payload.end_date)

    if payload.pickup_name:
        filters.append(Order.pickup_name.contains(payload.pickup_name))
    if payload.dropoff_name:
        filters.append(Order.dropoff_name.contains(payload.dropoff_name))

    # 分頁
    skip = (payload.page - 1) * payload.size
    total = db.query(Order).filter(*filters).count()

    orders = (
        db.query(Order)
        .filter(*filters)
        .order_by(Order.order_id.asc())
        .offset(skip)
        .limit(payload.size)
        .all()
    )

    # 組成 Response
    return PaginatedOrdersRp(
        total=total,
        page=payload.page,
        size=payload.size,
        data=[
            OrderRp(
                order_id=o.order_id,
                user_id=o.user_id,
                driver_id=o.driver_id,
                pickup_lat=o.pickup_lat,
                pickup_lng=o.pickup_lng,
                dropoff_lat=o.dropoff_lat,
                dropoff_lng=o.dropoff_lng,
                pickup_name=o.pickup_name,
                dropoff_name=o.dropoff_name,
                passengers=o.passengers,
                accept_pooling=o.accept_pooling,
                status=o.status,
                created_at=o.created_at,  # 直接回傳 UTC
                updated_at=o.updated_at,
            )
            for o in orders
        ],
    )

#get user table
@router.post(
    "/user/filter", 
    response_model=PaginatedUsersRp, 
    tags=["Admin"],
    summary="用戶篩選與列表 (Admin)",
    description="""
### 用戶篩選與列表 (User Filter & List) 👥

此端點供系統管理員使用，用於**多條件篩選**、**模糊搜索**和**分頁**查詢所有註冊用戶清單。

**安全性與權限：**
- 需在 Header 中提供有效的 **JWT Access Token**。
- **僅限**通過 `admin_required` 驗證的**管理員 (Admin)** 身份才能訪問。
`Authorization: Bearer <your_token>`

---

**請求參數 (Request Body: UserListRq):**
所有篩選欄位皆為 **非必填 (Optional)**，若不傳遞則不應用該篩選條件。

| 欄位 | 類型 | 篩選方式 | 說明 |
| :--- | :--- | :--- | :--- |
| `page` | `int` | 分頁 | **分頁頁碼**，預設為 `1`。 |
| `size` | `int` | 分頁 | **每頁筆數**，預設為 `10`。 |
| `username` | `str` | 模糊搜索 | 依用戶名稱 (`name`) 進行搜索 (`contains`)。 |
| `email` | `str` | 模糊搜索 | 依 Email 進行搜索 (`contains`)。 |
| `phone` | `str` | 模糊搜索 | 依手機號碼進行搜索 (`contains`)。 |
| `role` | `str` | 精確匹配 | 依用戶角色進行精確篩選 (例如：`user` 或 `admin`)。 |
| `start_date` | `datetime` | 範圍篩選 | 依據帳戶**起始建立日期** (`created_at`) 篩選 (含)。 |
| `end_date` | `datetime` | 範圍篩選 | 依據帳戶**結束建立日期** (`created_at`) 篩選 (含)。 |

---

**回應 (Response Model: PaginatedUsersRp):**
返回一個包含分頁資訊和用戶資料清單的物件。

| 欄位 | 類型 | 說明 |
| :--- | :--- | :--- |
| `total` | `int` | 符合篩選條件的**總用戶數**。 |
| `page` | `int` | 當前頁碼。 |
| `size` | `int` | 每頁筆數。 |
| `data` | `List[UserRp]` | 包含當前頁所有用戶詳細資訊的清單。 |

**錯誤處理：**
- **401 Unauthorized**: JWT 令牌無效或過期。
- **403 Forbidden**: 用戶身份**非管理員**。
"""
)
def list_users(
    payload: UserListRq = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # 只有 admin 可以查詢
    admin_viewer_required(current_user, db)

    filters = []

    if payload.username:
        filters.append(User.name.contains(payload.username))
    if payload.email:
        filters.append(User.email.contains(payload.email))
    if payload.phone:
        filters.append(User.phone.contains(payload.phone))
    if payload.role:
        filters.append(User.role == payload.role)
    if payload.start_date:
        filters.append(User.created_at >= payload.start_date)
    if payload.end_date:
        filters.append(User.created_at <= payload.end_date)

    skip = (payload.page - 1) * payload.size
    total = db.query(User).filter(*filters).count()

    users = (
        db.query(User)
        .filter(*filters)
        .order_by(User.id.asc())
        .offset(skip)
        .limit(payload.size)
        .all()
    )

    return PaginatedUsersRp(
        total=total,
        page=payload.page,
        size=payload.size,
        data=[
            UserRp(
                id=u.id,
                name=u.name,
                email=u.email,
                phone=u.phone,
                role=u.role,
                created_at=u.created_at,
                updated_at=u.updated_at
            )
            for u in users
        ]
    )

#get driver table
@router.post(
    "/driver", 
    response_model=list[DriverRp], 
    tags=["Admin"],
    summary="獲取所有司機列表 (Admin)",
    description="""
### 獲取所有司機列表 (List All Drivers) 

此端點已從 GET **改為 POST**，以方便前端透過 Fetch API 等方式傳送認證 Header。

**它不需要任何請求 Body**（即 Body 可以為空 `{}` 或 `null`）。

**安全性與權限：**
- 需在 Header 中提供有效的 **JWT Access Token**。
- **僅限**通過 `admin_required` 驗證的**管理員 (Admin)** 身份才能訪問。
`Authorization: Bearer <your_token>`

---

**請求 (Request):**
- **路徑參數:** 無。
- **請求主體:** 可選，建議傳遞 `{}` 或 `null`。

**回應 (Response Model: List[DriverRp]):**
- 成功返回 **`DriverRp`** 模型的清單，數據依照司機 ID **升序**排列。

**錯誤處理：**
- **401 Unauthorized**: JWT 令牌無效或過期。
- **403 Forbidden**: 用戶身份**非管理員**。
"""
)
def list_drivers_post(
    # 使用 Body(None) 或 Body(default=None) 讓請求 Body 可以為空
    # 這裡使用 Optional[Dict] 確保即使不傳 Body 也能正常工作
    payload: Optional[Dict] = Body(default=None), 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    回傳所有 Driver 資料（小型資料集，不需要分頁或篩選）
    只有 admin 可以查詢
    """
    # 驗證 admin 權限 (與 GET 版本完全相同)
    admin_viewer_required(current_user, db)

    # 取得所有司機，依照 id 升序 (與 GET 版本完全相同)
    drivers = db.query(Driver).order_by(Driver.id.asc()).all()

    # 回傳 Pydantic model 列表 (與 GET 版本完全相同)
    return [
        DriverRp(
            id=d.id,
            name=d.name,
            status=d.status,
            total_rides=d.total_rides,
            current_lat=d.current_lat,
            current_lng=d.current_lng,
            yaw=d.yaw,
            is_available=d.is_available,
            created_at=d.created_at,
            updated_at=d.updated_at,
        )
        for d in drivers
    ]

