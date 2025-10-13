from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session
from passlib.hash import bcrypt
from datetime import datetime, timedelta
from typing import Annotated
from jose import JWTError, jwt
from fastapi.security import OAuth2PasswordBearer
import re
from sqlalchemy.exc import IntegrityError
from database import get_db
from models import User
from schemas import RegisterRq, RegisterRp, LoginRq, LoginRp, AdminCreateUserRq, AdminCreateUserRp
from services import create_access_token, get_current_user, admin_viewer_required
from sqlalchemy.exc import IntegrityError

ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 1 week

router = APIRouter()

# Register
@router.post(
    "/register",
    response_model=RegisterRp,
    summary="User Registration",
    description="""
### 用戶註冊 (User Registration) 📱

此端點用於建立新的用戶帳戶。

**請求 (Request Body: RegisterRq):**
- 傳入手機號碼 (`phone`)、密碼 (`password`) 和名稱 (`name`)。
- **手機號碼格式驗證**：目前限定為**台灣手機號碼格式**（`09XXXXXXXX`，共 10 碼）。

**邏輯與驗證：**
1. 驗證手機號碼格式。
2. 檢查手機號碼是否已註冊。
3. 密碼將被 **Hash** 後儲存。

---

**回應 (Response Model: RegisterRp):**
- 包含註冊結果的 **`status`** (`bool`) 和 **`message`** (`str`)。

| 欄位 | 類型 | 說明 |
| :--- | :--- | :--- |
| `status` | `bool` | 註冊成功為 `True`，失敗為 `False`。 |
| `message` | `str` | 描述註冊結果或錯誤原因。 |

**常見回應情境：**

| 狀態 (status) | HTTP 狀態碼 | Message 內容 | 說明 |
| :--- | :--- | :--- | :--- |
| `True` | **200 OK** | `"Registration successful"` | 成功建立帳戶。 |
| `False` | **200 OK** | `"Invalid phone format"` | 手機號碼格式不符 (`09XXXXXXXX`)。 |
| `False` | **200 OK** | `"Phone number already exists"` | 該號碼已被註冊。 |
| `False` | **500 Internal Server Error** | `"Server error: {...}"` | 伺服器或資料庫錯誤。 |
""",
    tags=["User"]
)
def register(user: RegisterRq, db: Session = Depends(get_db)) -> RegisterRp:
    # Phone format validation (Taiwan mobile: 09XXXXXXXX)
    if not re.fullmatch(r"^09\d{8}$", user.phone):
        return RegisterRp(status=False, message="Invalid phone format")

    # Check if phone already exists
    existing_user = db.query(User).filter(User.phone == user.phone).first()
    if existing_user:
        return RegisterRp(status=False, message="Phone number already exists")

    try:
        hashed_password = bcrypt.hash(user.password)
        new_user = User(
            phone=user.phone,
            password_hash=hashed_password,
            name=user.name
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        return RegisterRp(status=True, message="Registration successful")
    except IntegrityError:
        db.rollback()
        return RegisterRp(status=False, message="Phone number already exists. (database error)")
    except Exception as e:
        db.rollback()
        return RegisterRp(status=False, message=f"Server error: {e}")

# Login
@router.post(
    "/login",
    response_model=LoginRp,
    summary="User Login",
    description="""
### 用戶登入 (User Login) 🔑

此端點用於使用手機號碼和密碼進行身份驗證，成功後會返回一個 **JWT 存取令牌 (Access Token)**。

**適用對象：**
此端點同時適用於 **普通用戶 (User)** 和 **管理員 (Admin)**。

**請求 (Request Body: LoginRq):**
- 傳入手機號碼 (`phone`) 和密碼 (`password`)。
- **注意：** 手機號碼應使用註冊時的格式。

---

**成功回應 (Response Model: LoginRp - Status: True):**
- HTTP 狀態碼：**200 OK**。
- 返回一個包含 JWT 令牌的物件，該令牌應用於後續所有需要身份驗證的 API 請求中。

| 欄位 | 類型 | 說明 |
| :--- | :--- | :--- |
| `status` | `bool` | 登入成功為 **`True`**。 |
| `message` | `str` | `"Login successful"`。 |
| `access_token` | `str` | **JWT 存取令牌**。 |
| `token_type` | `str` | 令牌類型，固定為 **`bearer`**。 |

**錯誤處理 (Response Model: LoginRp - Status: False):**
- HTTP 狀態碼：**200 OK** (此 API 將驗證錯誤包裝在回應主體中)。
- 任何驗證失敗都會返回：
    - `status`: **`False`**
    - `message`: `"Invalid phone or password"` (不區分手機號碼不存在還是密碼錯誤，以提高安全性)。
""",
    tags=["User","Admin"]
)
def login(request: LoginRq, db: Session = Depends(get_db)):
    # Check if user exists
    user = db.query(User).filter(User.phone == request.phone).first()
    if not user or not bcrypt.verify(request.password, user.password_hash):
        return {"status": False, "message": "Invalid phone or password"}

    # Generate token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.phone, "role": user.role},
        expires_delta=access_token_expires
    )

    return {
        "status": True,
        "message": "Login successful",
        "access_token": access_token,
        "token_type": "bearer"
    }

@router.post(
    "/create",
    response_model=AdminCreateUserRp,
    summary="Admin Create New User",
    description="""
### 管理員新增使用者 (Admin Create User) 🔑

此端點允許具備 **Admin** 角色的用戶新增新的使用者帳戶，並指定其角色 (admin, viewer)。

**權限：**
- 只有 **Admin** 角色可以呼叫此 API。

**請求 (Request Body: AdminCreateUserRq):**
- 傳入手機號碼 (`phone`)、密碼 (`password`)、名稱 (`name`) 和角色 (`role`)。
- **手機號碼格式**:數字(0~...)
- **角色驗證**：限定為 `admin`, `viewer` 之一。

**邏輯與驗證：**
1. 確認呼叫者身分是 Admin。
2. 檢查手機號碼是否已註冊。
3. 驗證提供的角色是否有效。
4. 密碼將被 **Hash** 後儲存。

---

**回應 (Response Model: AdminCreateUserRp):**
- 包含操作結果的 **`status`** (`bool`)、**`message`** (`str`) 和 **`user_id`** (`int` 或 `null`)。

**常見回應情境：**

| 狀態 (status) | HTTP 狀態碼 | Message 內容 | 說明 |
| :--- | :--- | :--- | :--- |
| `True` | **200 OK** | `"User created successfully"` | 成功建立帳戶。 |
| `False` | **200 OK** | `"Invalid role specified"` | 角色必須是 admin或viewer。 |
| `False` | **200 OK** | `"Phone number already exists"` | 該號碼已被註冊。 |
| `False` | **500 Internal Server Error** | `"Server error: {...}"` | 伺服器或資料庫錯誤。 |
| N/A | **403 Forbidden** | N/A | 呼叫者非 Admin 角色。 |
""",
    tags=["Admin"]
)
def create_admin_viewer(
    payload: AdminCreateUserRq = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> AdminCreateUserRp:
    # 1. 確認 admin 身分 (此函式會在非 Admin 時拋出 403)
    admin_viewer_required(current_user, db)

    # 有效的角色清單
    valid_roles = {"admin", "viewer"}

    # 3. 角色驗證
    if payload.role not in valid_roles:
        return AdminCreateUserRp(status=False, message="Invalid role specified. Must be one of: admin, viewer")

    # 4. 檢查手機號碼是否已存在
    existing_user = db.query(User).filter(User.phone == payload.phone).first()
    if existing_user:
        return AdminCreateUserRp(status=False, message="Phone number already exists")

    try:
        # 5. Hash 密碼
        hashed_password = bcrypt.hash(payload.password)
        
        # 建立新的 User 實例 (注意：您的 User 模型中需要有 name 欄位，已假設存在)
        new_user = User(
            phone=payload.phone,
            password_hash=hashed_password,
            name=payload.name,
            role=payload.role,  # 設定指定的角色
        )
    
        # 6. 儲存到資料庫
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        
        return AdminCreateUserRp(
            status=True, 
            message="User created successfully",
            user_id=new_user.id
        )
        
    except IntegrityError:
        db.rollback()
        # 即使前面檢查過，仍處理潛在的資料庫唯一性錯誤
        return AdminCreateUserRp(status=False, message="Phone number already exists (database integrity error)")
    except Exception as e:
        db.rollback()
        return AdminCreateUserRp(status=False, message=f"Server error: {e}")

