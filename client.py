import logging
import sys
import socket
from common import protocol
import threading

logging.basicConfig(
  level=logging.INFO,
  format="%(asctime)s - %(levelname)s - %(message)s"
)

TCP_SERVER_ADDRESS = "127.0.0.1"
TCP_SERVER_PORT = 9000
UDP_SERVER_ADDRESS = "127.0.0.1"
UDP_SERVER_PORT = 9001

def tcp_client_request(room_name: str, operation: str, username: str, udp_port: int = None) -> str:
  """
  TCP接続を通して、チャットルームの作成または参加リクエストを送信し、
  サーバーから返ってくるトークンを取得する関数。
  """
  try:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as tcp_sock:
      tcp_sock.connect((TCP_SERVER_ADDRESS, TCP_SERVER_PORT))
      state = 0
      
      operation = int(operation)
      if operation == 1:
        if udp_port is None:
          logging.error("UDP port is required for creating a chat room")
          sys.exit(1)
        payload_str = f"{username},{udp_port}"
      else:
        payload_str = username
      
      op_payload = payload_str.encode("utf-8")
      request_message = protocol.encode_tcp_message(room_name, operation, state, op_payload)
      tcp_sock.sendall(request_message)
      logging.info(f"TCP request sent: {room_name} {operation} {username}")
      
      response_data = tcp_sock.recv(4096)
      if not response_data:
        logging.error(f"No response received from server.")
        sys.exit(1)
      response = protocol.decode_tcp_message(response_data)
      token = response.get("op_payload").decode("utf-8")
      logging.info(f"Received token: {token}")
      return token
  except Exception as e:
    logging.exception(f"TCP client error: {e}")
    sys.exit(1)

def udp_receive_loop(udp_sock: socket.socket):
  """
  UDPソケットでの受信ループです。
  サーバーから送られてくるチャットメッセージを受信し、デコードして表示します。
  """
  while True:
    try:
      data, addr = udp_sock.recv(4096)
      message_info = protocol.decode_udp_message(data)
      room_name = message_info.get("room_name")
      chat_message = message_info.get("message")
      logging.info(f"Received message from {room_name}: {chat_message}")
    except Exception as e:
      logging.exception("UDP server error")
      break
    
def udp_send_message(udp_sock: socket.socket, room_name: str, token: str, message: str):
  """
  ユーザーが送信したメッセージをUDP経由でサーバーに送信します。
  """
  try:
    udp_message = protocol.encode_udp_message(room_name, token, message)
    udp_sock.sendto(udp_message, (UDP_SERVER_ADDRESS, UDP_SERVER_PORT))
  except Exception as e:
    logging.exception(f"UDP send error: {e}")
    
      
def main():
  username = input("Enter your name: ").strip()
  if not username:
    print("User name cannot be empty.")
    sys.exit()
    
  room_name = input("Enter chat room name: ").strip()
  if not room_name:
    print("Chat room name cannot be empty.")
    
  op_input = input("Input 1 to create a chat room or 2 to join an existing room: ").strip()
  if op_input not in ("1", "2"):
    print("Invalid operation selection.")
    sys.exit()
    
  operation = int(op_input)
  
  udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
  with udp_sock:
    # ローカルマシン上の全てのネットワークインターフェースにバインド(ホストに空文字を指定)
    # OSで自動的に利用可能なポートを割り当てる(ポートに0を指定)
    udp_sock.bind(("", 0))
    local_udp_port = udp_sock.getsockname()[1]
    logging.info(f"Local UDP port: {local_udp_port}")
    
    if operation == 1:
      token = tcp_client_request(room_name, operation, username, local_udp_port)
    else:
      token = tcp_client_request(room_name, operation, username)
      
    udp_thread = threading.Thread(target=udp_receive_loop, args=(udp_sock,), daemon=True)
    udp_thread.start()
    
    print(f"You have joined the chat room. Start typing your messages!")
    
    try:
      while True:
        message = input()
        if message.lower() in {"exit", "quit"}:
          print("Exiting chat")
          break
        udp_send_message(udp_sock, room_name, token, message)
    except KeyboardInterrupt:
      print(f"\nkeyboardInterrupt detected. Exiting chat.")
    
if __name__ == "__main__":
  main()
