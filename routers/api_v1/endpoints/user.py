from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from database import get_db
from models import User
from schemas import UserProfile, UpdateRq, UpdateRp, PasswordUpdate, PasswordUpdateRp
from services import get_current_user, admin_viewer_required
from passlib.hash import bcrypt

router = APIRouter()

# ----------------------------
# Get Current User Info
# ----------------------------
@router.get(
    "/me",
    response_model=UserProfile,
    tags=["User"],
    summary="Get Current User Info",
    description="""
    Retrieve the currently authenticated user's information.

    **Response Fields:**
    - `id`: User ID
    - `phone`: User phone number
    - `name`: User name

    Requires a valid Bearer JWT access token in the `Authorization` header:

    ```
    Authorization: Bearer <your_token>
    ```
    """
)
def read_current_user(current_user: User = Depends(get_current_user)):
    return current_user

# ----------------------------
# Update Current User Info
# ----------------------------
@router.put(
    "/me",
    response_model=UpdateRp,
    tags=["User"],
    summary="Update Current User Info",
    description="""
    Update the authenticated user's name.

    **Request Body Example:**
    ```json
    {
        "name": "New Name"
    }
    ```

    Requires a valid Bearer JWT access token in the `Authorization` header.
    """
)
def update_current_user(
    profile_update: UpdateRq,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        current_user.name = profile_update.name
        db.commit()
        return {"status": True}
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": False, "message": "Failed to update user name"}
        )

# ----------------------------
# Update Password
# ----------------------------
@router.put(
    "/me/password",
    response_model=PasswordUpdateRp,
    tags=["User"],
    summary="Update Current User Password",
    description="""
    Update the authenticated user's password.

    **Request Body Example:**
    ```json
    {
        "old_password": "current_password",
        "new_password": "new_secure_password"
    }
    ```

    Requires a valid Bearer JWT access token in the `Authorization` header.
    """
)
def update_password(
    password_update: PasswordUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Verify old password
    if not bcrypt.verify(password_update.old_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": False, "message": "Old password is incorrect"}
        )

    # Update with new password
    current_user.password_hash = bcrypt.hash(password_update.new_password)
    db.add(current_user)
    db.commit()
    db.refresh(current_user)

    return {"status": True, "message": "Password updated successfully"}


# ----------------------------
# Delete User by ID (Admin Only)
# ----------------------------
@router.delete(
    "/{user_id}",
    tags=["User"],
    summary="Delete User by ID",
    description="""
### 刪除指定用戶 (Delete User by ID) 🗑️

此端點用於根據用戶的 **ID** 永久刪除該用戶帳戶及其相關資料。

**安全性與權限：**
- 需在 Header 中提供有效的 **JWT Access Token**。
- **僅限**通過 `admin_required` 驗證的**管理員 (Admin)** 身份才能執行此操作。
`Authorization: Bearer <your_token>`

---

**路徑參數 (Path Parameter):**
- **user\_id** (int): 欲刪除的用戶的唯一 ID。

**成功回應 (Success Response):**
- **HTTP 狀態碼：200 OK**
- 回應主體：`{"status": true, "message": "User {user_id} deleted successfully"}`

**錯誤處理：**

| HTTP 狀態碼 | 情境 | 說明 |
| :--- | :--- | :--- |
| **401 Unauthorized** | JWT 令牌無效或過期。 | |
| **403 Forbidden** | 用戶身份**非管理員**。 | |
| **404 Not Found** | 該 `user_id` 在資料庫中**不存在**。 | |
| **500 Internal Server Error** | 刪除操作失敗（資料庫鎖定或內部錯誤）。 | |
"""
)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # 確認權限
    admin_viewer_required(current_user, db)

    # 查找使用者
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with id {user_id} not found"
        )

    # 刪除使用者
    try:
        db.delete(user)
        db.commit()
        return {"status": True, "message": f"User {user_id} deleted successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": False, "message": "Failed to delete user"}
        )

