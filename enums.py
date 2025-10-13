from enum import IntEnum

class OrderStatus(IntEnum):
    PENDING = 0        # 待派車
    ACCEPTED = 1       # 已接單
    ASSIGNED = 2       # 已派車
    IN_PROGRESS = 3    # 行程中
    COMPLETED = 4      # 已完成
    CANCELLED = 5      # 已取消
