from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, SmallInteger, Numeric, TIMESTAMP, Float, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from geoalchemy2 import Geometry
from sqlalchemy.sql import func
from database import Base
from enums import OrderStatus, DriverStatus

class User(Base):
    __tablename__ = "users"

    orders = relationship("Order", back_populates="user")
    id = Column(Integer, primary_key=True, index=True)
    phone = Column(String(20), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=True)
    password_hash = Column(String(255), nullable=False)

    # Profile fields
    avatar_url = Column(String(255), nullable=True)
    name = Column(String(50), unique=True, index=True, nullable=False)

    # Role (user / admin / viewer)
    role = Column(String(20), default="user", nullable=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class Order(Base):
    __tablename__ = "orders"

    order_id = Column(String(32), primary_key=True)
    #user_id = Column(Integer, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user = relationship("User", back_populates="orders")
    #driver_id = Column(Integer, nullable=True)
    driver_id = Column(Integer, ForeignKey("drivers.id"), nullable=True)
    driver = relationship("Driver", back_populates="orders")

    pickup_lat = Column(Float, nullable=False)
    pickup_lng = Column(Float, nullable=False)
    pickup_name = Column(String(100), nullable=True)   # 上車地點名稱

    dropoff_lat = Column(Float, nullable=False)
    dropoff_lng = Column(Float, nullable=False)
    dropoff_name = Column(String(100), nullable=True)  # 下車地點名稱

    status = Column(SmallInteger, default=OrderStatus.PENDING.value, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False)
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)

    passengers = Column(Integer, nullable=False, default=1)  # 預設 1 個乘客
    accept_pooling = Column(Boolean, nullable=False, default=False)  # 預設不接受共乘

class Driver(Base):
    __tablename__ = "drivers"

    orders = relationship("Order", back_populates="driver")
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False)

    status = Column(SmallInteger, default=DriverStatus.PENDING, nullable=False)
    total_rides = Column(Integer, default=0)

    current_lat = Column(Float, nullable=True)
    current_lng = Column(Float, nullable=True)
    yaw = Column(Float, nullable=True)
    is_available = Column(Boolean, default=False)

    created_at = Column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

class Route(Base):
    __tablename__ = "routes"

    order_id = Column(String(32), primary_key=True, nullable=False, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    vehicle_name = Column(String(50), nullable=True)
    type = Column(SmallInteger, nullable=False)
    eta_to_pick = Column(Float, nullable=True)
    eta_trip = Column(Float, nullable=True)
    total_distance_m = Column(Float, nullable=True)
    path1 = Column(Geometry(geometry_type="LINESTRING", srid=4326), nullable=True)  # 整條路線
    path2 = Column(Geometry(geometry_type="LINESTRING", srid=4326), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(),
                        onupdate=func.now(), nullable=False)
