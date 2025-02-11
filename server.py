import socket
import threading
import logging
import uuid
from common import protocol

SERVER_ADDRESS = "0.0.0.0"
# チャットルーム作成、参加用のTCPポート
TCP_SERVER_PORT = 9000  
# メッセージ交換用のUDPポート
UDP_SERVER_PORT = 9001

logging.basicConfig(
  level=logging.INFO,
  format="%(asctime)s - %(levelname)s - %(message)s"
)

class ChatRoomManager:
  """
  各チャットルームの状態を管理する簡易的なマネージャーです。
  各チャットルームはroom_nameをキーとして保持し、
  ホスト(作成者)と参加者の情報(IP, ユーザー名, 発行済みトークン)を管理します。
  """
  def __init__(self):
    self.lock =  threading.Lock()
    self.chat_rooms = {}
    
    
  def create_chat_room(self, room_name: str, host_ip: str, host_username: str, host_udp_port: int) -> str:
    with self.lock:
      if room_name in self.chat_rooms:
        logging.warning(f"Chat room already exists: {room_name}")
        return None
    
    token = uuid.uuid4().hex
    self.chat_rooms[room_name] = {
      "host": {"ip": host_ip, "username": host_username, "token": token, "port": host_udp_port},
      "participants": {}
    }
    logging.info(f"Created Chat room {room_name} with host token: {token} and UDP port: {host_udp_port}")
    return token
  
  
  def join_chat_room(self, room_name: str, participant_ip: str, participant_username: str) -> str:
    with self.lock:
      if room_name not in self.chat_rooms:
        logging.error(f"Chat room not found: {room_name}")
        return None
      
      token = uuid.uuid4().hex
      self.chat_rooms[room_name]["participants"][participant_ip] = {
        "user_name": participant_username,
        "token": token
      }
      logging.info(f"participant {participant_username} joined chat room {room_name} with token: {token}")
      return token
    
    
  def get_chat_room(self, room_name: str):
    with self.lock:
      return self.chat_rooms.get(room_name)
    
    
  def remove_chat_room(self, room_name: str):
    with self.lock:
      if room_name in self.chat_rooms:
        del self.chat_rooms[room_name]
        logging.info(f"Removed chat room {room_name}")
      else:
        logging.error(f"Chat room not found: {room_name}")


def handle_tcp_connection(conn: socket.socket, addr):
  """
  TCP接続ごとに呼び出されるハンドラ。
  クライアントから受信したTCRPに沿ってメッセージをデコードし、
  操作コードに応じてチャットルームの作成または参加を処理し、
  結果としてトークンを返します。
  """
  try:
    with conn:
      data = conn.recv(4096)
      if not data:
        logging.error(f"No data received from TCP connection {addr}")
        return
      
      # TCPメッセージのデコード
      message = protocol.decode_tcp_message(data)
      room_name = message.get("room_name")
      operation = message.get("operation")
      state = message.get("state")
      op_payload = message.get("op_payload")
      
      op_payload_decoded = op_payload.decode("utf-8")
      parts = op_payload_decoded.split(",")
      username = parts[0]
      if len(parts) > 1:
        try:
          host_udp_port = int(parts[1])
        except ValueError:
          host_udp_port = None
      else:
        host_udp_port = None
      
      logging.info(f"TCP request from {addr} room name: {room_name}, operation: {operation}, state: {state}, username: {username}, host_udp_port: {host_udp_port}")
      
      if operation == 1:
        if host_udp_port is None:
          logging.error(f"UDP port not provided by host in creation request")
          response_payload = "ERROR: UDP port not provided".encode("utf-8")
        else:
          token = chat_room_manager.create_chat_room(room_name, addr[0], username, host_udp_port)
          if token is None:
            response_payload = "ERROR: chat room is already exist. {room_name}"
          else:
            response_payload = token.encode("utf-8")
      elif operation == 2:
        # チャットルーム参加要求
        token = chat_room_manager.join_chat_room(room_name, addr[0], username)
        if token is None:
          response_payload = "ERROR: chat room not found. {room_name}"
        else:
          response_payload = token.encode("utf-8")
      else:
        response_payload = "ERROR: unknown operation".encode("utf-8")
        
      # stateは2(完了)に設定してresponseを生成
      response = protocol.encode_tcp_message(room_name, operation, 2, response_payload)
      conn.sendall(response)
      logging.info(f"Sent TCP response to {addr}")
  except Exception as e:
    logging.exception(f"Exception handling TCP connection from {addr}")
   
    
def tcp_server():
  """
  TCPサーバーを起動し、クライアントからの接続を待機します。
  各接続は、handle_tcp_connectionで処理され、スレッドで並行実行されます。
  """
  tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
  tcp_sock.bind((SERVER_ADDRESS, TCP_SERVER_PORT))
  tcp_sock.listen(5)
  logging.info(f"TCP server listening on {SERVER_ADDRESS}: {TCP_SERVER_PORT}")
  while True:
    conn, addr = tcp_sock.accept()
    logging.info(f"Accepted TCP connection from {addr}")
    threading.Thread(target=handle_tcp_connection, args=(conn, addr), daemon=True).start()
    
    
def handle_udp_message(data: bytes, addr, udp_sock: socket.socket):
  """
  UDPで受信したメッセージを処理します。
  メッセージはprotocol.decode_udp_messageによりデコードし、対象チャットルーム内の参加者へリレーします。
  リレー前にトークンの妥当性をチェックします。
  """
  try:
    message = protocol.decode_udp_message(data)
    room_name = message.get("room_name")
    token = message.get("token")
    chat_text = message.get("message")
    logging.info(f"UDP message from {addr} in room {room_name} with token {token}")
    
    chat_room = chat_room_manager.get_chat_room(room_name)
    if not chat_room:
      logging.error(f"Chat room {room_name} not found for UDP message from {addr}")
      return
    
    valid = False
    # ホストの場合のトークン確認
    host_info = chat_room["host"]
    host_addr = (host_info["ip"], host_info["port"])
    if host_addr == addr and host_info["token"] == token:
      valid = True
    # 参加者の場合のトークン確認
    else:
      participant = chat_room["participants"].get(addr[0])
      if participant and participant["token"] == token:
        valid = True
      if not valid:
        logging.error(f"Invalid token from {addr} for chat room {room_name}")
        return
      
    # リレー処理(チャットルームの全ての参加者へ送信、ホスト含む)
    relay_data = chat_text.encode("utf-8")
    host_addr = (chat_room["host"]["ip"], chat_room["host"]["port"])
    if host_addr != addr:
      udp_sock.sendto(relay_data, host_addr)
    for part_ip, part_info in chat_room["participants"].items():
      part_addr = (part_ip, UDP_SERVER_PORT)
      if part_addr != addr:
        udp_sock.sendto(relay_data, part_addr)
    logging.info(f"Relayed UDP message in room {room_name}")
  except Exception as e:
    logging.exception(f"Exception handling UDP message from {addr}")
    
       
def udp_server():
  """
  UDPサーバーを起動し、チャットメッセージの受信とリレーを行います。
  """
  udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
  udp_sock.bind((SERVER_ADDRESS, UDP_SERVER_PORT))
  logging.info(f"UDP server listening on {SERVER_ADDRESS}: {UDP_SERVER_PORT}")
  while True:
    try:
      data, addr = udp_sock.recvfrom(65535)
      threading.Thread(target=handle_udp_message, args=(data, addr, udp_sock), daemon=True).start()
    except Exception as e:
      logging.exception(f"UDP server error")
      
      
if __name__ == "__main__":
  chat_room_manager = ChatRoomManager()
  # TCPサーバーとUDPサーバーを別スレッドで起動
  tcp_thread = threading.Thread(target=tcp_server, daemon=True)
  udp_thread = threading.Thread(target=udp_server, daemon=True)
  tcp_thread.start()
  udp_thread.start()
  logging.info(f"Server started. Press Ctrl+C to exit.")
  try:
    while True:
      threading.Event().wait(1)
  except KeyboardInterrupt:
    logging.info(f"Server shutting down.")
