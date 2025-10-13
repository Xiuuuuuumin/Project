from ws_modules.server_ws import WebSocketServer
from ws_modules.manager import WebSocketManager
from database import get_db

server_ws = WebSocketServer()
db_session = next(get_db())
manager = WebSocketManager(server_ws, db_session)
server_ws.manager = manager

def handle_ros_message(message: dict):
    message_id = message.get("message_id")
    if message_id:
        manager.set_ros_response(message_id, message)

server_ws.set_ros_callback(handle_ros_message)