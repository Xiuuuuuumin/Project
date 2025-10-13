from fastapi import APIRouter, Depends, Body
from sqlalchemy.orm import Session
from database import get_db
from models import Driver
from services import get_current_user, admin_viewer_required
from datetime import datetime, timezone
from schemas import DriverRp, DriverCreateRq

router = APIRouter()

@router.post("/create", response_model=DriverRp, tags=["Driver"])
def create_driver(
    payload: DriverCreateRq = Body(...),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    # 確認 admin 身分
    admin_viewer_required(current_user, db)

    new_driver = Driver(
        name=payload.name,
        status=payload.status,
        current_lat=payload.current_lat,
        current_lng=payload.current_lng,
        is_available=payload.is_available,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )

    db.add(new_driver)
    db.commit()
    db.refresh(new_driver)

    return DriverRp(
        id=new_driver.id,
        name=new_driver.name,
        status=new_driver.status,
        total_rides=new_driver.total_rides,
        current_lat=new_driver.current_lat,
        current_lng=new_driver.current_lng,
        is_available=new_driver.is_available,
        created_at=new_driver.created_at,
        updated_at=new_driver.updated_at
    )
