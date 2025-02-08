import socket
import sys
import logging

# ログ設定
logging.basicConfig(
  level=logging.INFO, # info未満のログは出力しない
  format="%(asctime)s - %(levelname)s - %(message)s"
)
SERVER_ADDRESS = "127.0.0.1"
SERVER_PORT = 9001
# 全てのネットワークインターフェース(LAN, VPN, wi-fi等)からの接続を受け付ける
CLIENT_ADDRESS = "0.0.0.0"
# UDPネットワークソケットを使用
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# ユーザーにユーザー名を入力してもらう
username = input("Enter your name: ")
username_bytes = username.encode("utf-8")
if len(username_bytes) > 255:
  logging.error("Error: Username must be less than 255 bytes", exc_info=True)
  sys.exit(1)

message = input("Enter your message: ")
message_bytes = message.encode("utf-8")

# メッセージフォーマットの作成
# 1バイト目でユーザー名の長さを指定
# 続くバイト: ユーザー名
# 残りのバイト: メッセージ
# 送信するデータはbytes型である必要がある
formatted_message = bytes([len(username_bytes)]) + username_bytes + message_bytes

# ポート番号を０に設定することで、OSが自動的に利用可能なポートを割り当てる
port = 0
sock.bind((CLIENT_ADDRESS, port))
# 自動的に割り当てられたポート番号を取得する
# sock.getsockname()はソケットのローカルアドレス情報をタプル(ホストアドレス,ポート番号)で返す
actual_port = sock.getsockname()[1]
logging.info(f"Using port: {actual_port}")

try:
  logging.info(f"Sending {formatted_message} to {SERVER_ADDRESS}:{SERVER_PORT}")
  
  sent = sock.sendto(formatted_message, (SERVER_ADDRESS, SERVER_PORT))
  logging.info(f"Sent {sent} bytes to {SERVER_ADDRESS}:{SERVER_PORT}")
  
  logging.info(f"Waiting for messages...")
  while True:
    # 最大4096バイトのデータを受信する
    data, server = sock.recvfrom(4096)
    if len(data) < 1:
      logging.error(f"Received empty message from server")
      continue
    username_len = data[0]
    if len(data) < 1 + username_len:
      logging.error("Received invalid message from server: expected at least {1+username_len} bytes, got {len(data)}")
      continue
    username = data[1:1+username_len].decode("utf-8")
    message = data[1+username_len:].decode("utf-8")
    logging.info(f"Received message from {username}: {message}")

except KeyboardInterrupt:
  logging.info("\nCtrl+C pressed. Closing connection...")
  
finally:
  logging.info("closing socket")
  sock.close()
