from pydantic import BaseModel, EmailStr, Field, ConfigDict
from enum import Enum
from typing import Optional, List
from datetime import datetime

# ---------------------
# Register
# ---------------------
class RegisterRq(BaseModel):
    phone: str
    password: str
    name: str

class RegisterRp(BaseModel):
    status: bool
    message: str


# ---------------------
# Login
# ---------------------
class LoginRq(BaseModel):
    phone: str
    password: str

class LoginRp(BaseModel):
    status: bool
    message: str
    access_token: str | None = None
    token_type: str | None = None

    model_config = ConfigDict(
        from_attributes=True # <-- 新寫法
    )

# 請求模型 (Request Model) - Admin 新增使用者
class AdminCreateUserRq(BaseModel):
    phone: str = Field(..., description="手機號碼 (e.g., 0912345678)")
    password: str = Field(..., description="密碼")
    name: str = Field(..., description="用戶名稱")
    role: str = Field(..., description="用戶角色 (admin, viewer, user)")

# 回應模型 (Response Model) - Admin 新增使用者
class AdminCreateUserRp(BaseModel):
    status: bool = Field(..., description="操作成功為 True，失敗為 False")
    message: str = Field(..., description="操作結果訊息")
    user_id: Optional[int] = Field(None, description="新建立的用戶 ID (成功時)")


# ---------------------
# Get User Profile
# ---------------------
class UserProfile(BaseModel):
    id: int
    phone: str
    name: str

    model_config = ConfigDict(
        from_attributes=True # <-- 新寫法
    )

# ---------------------
# Update Profile
# ---------------------
class UpdateRq(BaseModel):
    name: str

class UpdateRp(BaseModel):
    status: bool


# ---------------------
# Update Password
# ---------------------
class PasswordUpdate(BaseModel):
    old_password: str
    new_password: str

class PasswordUpdateRp(BaseModel):
    status: bool
    message: str

# ---------------------
# Create Order
# ---------------------
class OrderCreate(BaseModel):
    pickup_lat: float
    pickup_lng: float
    pickup_name: str | None = None   # 上車地點名稱（可選）
    dropoff_lat: float
    dropoff_lng: float
    dropoff_name: str | None = None  # 下車地點名稱（可選）
    passengers: int = 1               # 新增，預設 1
    accept_pooling: bool = False      # 新增，預設不接受共乘

class OrderCreateRp(BaseModel):
    order_id: str
    status: int
    message: str

# ---------------------
# Order Update
# ---------------------
class OrderUpdate(BaseModel):
    status: int = Field(..., ge=0, le=5, description="訂單狀態代碼 (0~5)")

class OrderCreateRp(BaseModel):
    order_id: str
    status: int

    model_config = ConfigDict(
        from_attributes=True # <-- 新寫法
    )

# ---------------------
# Get Order
# ---------------------
class OrderRp(BaseModel):
    order_id: str
    user_id: int
    driver_id: Optional[int]
    pickup_lat: float
    pickup_lng: float
    dropoff_lat: float
    dropoff_lng: float
    pickup_name: str | None = None
    dropoff_name: str | None = None
    passengers: int                   
    accept_pooling: bool              
    status: int
    created_at: datetime
    updated_at: datetime

class OrdersListRp(BaseModel):
    page: int
    limit: int
    total: int
    orders: List[OrderRp]

# ---------------------
# Test
# ---------------------
class TestRq(BaseModel):
    message: str

class TestRp(BaseModel):
    status: str

# ---------------------
# Admin get Order
# ---------------------
class OrderHistoryRp(BaseModel):
    pickup_lat: float
    pickup_lng: float
    dropoff_lat: float
    dropoff_lng: float
    pickup_name: str | None = None
    dropoff_name: str | None = None
    passengers: int
    accept_pooling: bool
    date: datetime   # 對應 created_at

class OrderListRq(BaseModel):
    page: int = 1          # 第幾頁
    size: int = 10         # 每頁筆數
    status: Optional[List[int]] = None
    user_id: int | None = None
    driver_id: int | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    pickup_name: str | None = None
    dropoff_name: str | None = None
    passengers: int | None = None
    accept_pooling: bool | None = None

""" class OrderRp(BaseModel):
    order_id: str
    user_id: int
    pickup_lat: float
    pickup_lng: float
    dropoff_lat: float
    dropoff_lng: float
    pickup_name: str | None = None
    dropoff_name: str | None = None
    status: int
    created_at: datetime """

class PaginatedOrdersRp(BaseModel):
    total: int
    page: int
    size: int
    data: List[OrderRp]

# ---------------------
# Admin get User
# ---------------------
class UserListRq(BaseModel):
    username: Optional[str] = None   # 對應 name
    email: Optional[str] = None
    phone: Optional[str] = None
    role: Optional[str] = None
    start_date: Optional[datetime] = None  # 篩選 created_at
    end_date: Optional[datetime] = None
    page: int = 1
    size: int = 10

class UserRp(BaseModel):
    id: int
    name: Optional[str]
    email: Optional[str]
    phone: str
    role: str
    created_at: datetime
    updated_at: Optional[datetime]

class PaginatedUsersRp(BaseModel):
    total: int
    page: int
    size: int
    data: List[UserRp]

# ---------------------
# Admin get Driver
# ---------------------
class DriverRp(BaseModel):
    id: int
    name: str
    status: int
    total_rides: int
    current_lat: Optional[float] = None
    current_lng: Optional[float] = None
    yaw: Optional[float] = None
    is_available: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True # <-- 新寫法
    )

# ---------------------
# Admin create Driver
# ---------------------
class DriverCreateRq(BaseModel):
    name: str
    status: Optional[int] = 0           # 預設 DriverStatus.PENDING
    current_lat: Optional[float] = None
    current_lng: Optional[float] = None
    is_available: Optional[bool] = False

class DriverRp(BaseModel):
    id: int
    name: str
    status: int
    total_rides: int
    current_lat: Optional[float]
    current_lng: Optional[float]
    is_available: bool
    created_at: datetime
    updated_at: datetime

# ---------------------
# Admin create Driver
# ---------------------
class RoutePreviewRq(BaseModel):
    pickup_lat: float
    pickup_lng: float
    dropoff_lat: float
    dropoff_lng: float
    message_id: str

class RoutePoint(BaseModel):
    lat: float
    lng: float

class RoutePreviewRp(BaseModel):
    route: List[RoutePoint]
    message: str

