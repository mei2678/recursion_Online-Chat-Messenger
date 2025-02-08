import socket
from datetime import datetime, timedelta
import logging

# ログ設定
logging.basicConfig(
  level=logging.INFO, # info未満のログは出力しない
  format="%(asctime)s - %(levelname)s - %(message)s"
)

TIMEOUT_SECONDS = 60
MAX_FAILED_ATTEMPTS = 3

# クライアント情報を保持するメモリ
clients = {}

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
SERVER_ADDRESS = "0.0.0.0"
SERVER_PORT = 9001
logging.info(f"Starting up on {SERVER_ADDRESS}:{SERVER_PORT}")

sock.bind((SERVER_ADDRESS, SERVER_PORT))

def cleanup_inactive_clients():
  """
  MAX_FAILED_ATTEMPTSで指定した数だけ失敗するか、TIMEOUT_SECONDSで指定した秒数の間メッセージを受信していないクライアントをclientsメモリから削除する。
  """
  current_time = datetime.now()
  inactive_clients = []
  
  for address, client_info in clients.items():
    if (current_time - client_info["last_active"] > timedelta(seconds=TIMEOUT_SECONDS) or client_info["failed_attempts"] >= MAX_FAILED_ATTEMPTS):
      inactive_clients.append(address)
      
  for address in inactive_clients:
    del clients[address]
    logging.info(f"deleted client: {address}")
      
def relay_message(data, sender_address):
  """
  送信者以外のクライアント全員にメッセージを転送する。
  """
  for client_address in list(clients.keys()):
    # 送信者以外のクライアント全員にメッセージを転送する
    if client_address != sender_address:
      try:
        sent = sock.sendto(data, client_address)
        clients[client_address]["failed_attempts"] = 0
      except Exception as e:
        clients[client_address]["failed_attempts"] += 1
        logging.error(f"Failed to send message to {client_address}: {e}", exc_info=True)
while True:
  logging.info("\nWaiting to receive message")
  try:
    # 一度の通信で最大4096バイトのデータを受信する
    data, address = sock.recvfrom(4096)
    current_time = datetime.now()
    
    if address not in clients:
      clients[address] = {
        "last_active": current_time,
        "failed_attempts": 0
      }
    else:
      clients[address]["last_active"] = current_time
  
    if len(data) > 1:
      # メッセージの最初の1バイトからユーザー名の長さを取得する
      username_len = int.from_bytes(data[:1], byteorder='big')
      if len(data) < 1 + username_len:
        raise Exception(f"Invalid data length from {address}: expected at least {1+username_len} bytes, got {len(data)}")
      # 取得したユーザー名バイト数からユーザー名を取得する
      username = data[1:username_len+1].decode("utf-8")
      logging.info(f"Received {len(data)} bytes from {username}")
      logging.info(f"data: {data}")
      
      cleanup_inactive_clients()
      
      relay_message(data, address)
    else:
      raise Exception("Received empty message from {address}")
  
  except Exception as e:
    logging.error(f"Error: {e}", exc_info=True)


