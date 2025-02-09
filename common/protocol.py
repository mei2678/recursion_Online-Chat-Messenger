"""
このモジュールは、チャットルームプロトコル(TCRP)およびUDPのエンコード/デコード処理を提供します

【TCPプロトコル (TCRP)】
- パケットはヘッダーとボディから構成される
- ヘッダー(32バイト)の構成
  Byte 0: RoomNameSize (1バイト)
    - ボディ内の最初の何バイトがルーム名かを示す。最大2^8バイト。
  Byte 1: Operation (1バイト)
    - 操作コード (例: 新規作成=1, 参加=2 など)
  Byte 2: State (1バイト)
    - 状態コード(例: 初期化=0, 応答=1, 完了=2)
  Byte 3~31: OperationPayloadSize (29バイト)
    - ボディ内に含まれる Operation Payload のバイト数を29桁の0埋め10新数字として表す。
    
  - ボディの構成
    - 最初のRoomNameSizeバイト: ルーム名(UTF-8エンコード)
    - 次のOperationPayloadSizeバイト: Operation Payload (最大2^29バイト)

【UDPプロトコル】
- パケットはヘッダーとボディから構成される
- ヘッダーの構成
  - Byte 0: RoomNameSize (1バイト)
  - Byte 1: TokenSize (1バイト)
- ボディの構成
  - 最初のRoomNameSizeバイト: ルーム名(UTF-8エンコード)
  - 次のTokenSizeバイト: トークン(UTF-8エンコード)
  - 残り: 実際のメッセージ(UTF-8エンコード)
"""

TCP_HEADER_SIZE = 32
TCP_ROOMNAME_SIZE = 2 ** 8
TCP_PAYLOAD_MAX = 2 ** 29
TCP_PAYLOAD_FIELD_WIDTH = 29

UDP_HEADER_SIZE = 2
UDP_FIELD_MAX = 2 ** 8

def encode_tcp_message(room_name: str, operation: int, state: int, op_payload: bytes) -> bytes:
  """
  TCPメッセージをエンコードする。
  """
  room_name_bytes = room_name.encode("utf-8")
  if len(room_name_bytes) > TCP_PAYLOAD_MAX:  
    raise ValueError(f"Room name is too long: {len(room_name_bytes)} bytes (max: {TCP_PAYLOAD_MAX} bytes)")
  if len(op_payload) > TCP_PAYLOAD_MAX:
    raise ValueError(f"Operation payload is too long: {len(op_payload)} bytes (max: {TCP_PAYLOAD_MAX} bytes)")
  
  # ヘッダーの作成
  # RoomNameSize
  room_name_size_byte = len(room_name_bytes).to_bytes(1, "big")
  # Operation
  operation_byte = operation.to_bytes(1, "big")
  # State
  state_byte = state.to_bytes(1, "big")
  # OperationPayloadSize: op_payloadの長さを固定幅29桁の0埋め10進数字に変換
  op_payload_size_str =f"{len(op_payload):0{TCP_PAYLOAD_FIELD_WIDTH}d}"
  
def decode_tcp_message(data: bytes) -> dict:
  """
  TCPメッセージをデコードする。
  """
  if len(data) < TCP_HEADER_SIZE:
    raise ValueError(f"Data too short to contain TCP header.")
  
  room_name_size = data[0]
  operation = data[1]
  state = data[2]
  op_payload_size_field = data[3:TCP_HEADER_SIZE]
  try:
    op_payload_size = int(op_payload_size_field.decode("utf-8"))
  except ValueError:
    raise ValueError(f"Invalid operation payload size field")
  
  expected_body_length = room_name_size + op_payload_size
  if len(data) < TCP_HEADER_SIZE + expected_body_length:
    raise ValueError(f"Data too short for expected body length")
  
  body = data[TCP_HEADER_SIZE:]
  room_name_bytes = body[:room_name_size]
  op_payload = body[room_name_size:room_name_size + op_payload_size]
  room_name = room_name_bytes.decode("utf-8")
  
  return {
    "room_name": room_name,
    "operation": op_payload,
    "state": state,
    "op_payload": op_payload
  }
  
def decode_udp_message(data: bytes) -> dict:
  """
  UDPメッセージをデコードする。
  """
  if len(data) < UDP_HEADER_SIZE:
    raise ValueError(f"Data too short to contain UDP header")
  room_name_size = data[0]
  token_size = data[1]
  if len(data) < UDP_HEADER_SIZE + room_name_size + token_size:
    raise ValueError(f"Data too short for expected room name and token")
  
  offset = UDP_HEADER_SIZE
  room_name_bytes = data[offset:offset+room_name_size]
  offset += room_name_size
  token_bytes = data[offset:offset+token_size]
  offset += token_size
  message_bytes = data[offset:]
  
  room_name = room_name_bytes.decode("utf-8")
  token = token_bytes.decode("utf-8")
  message = message_bytes.decode("utf-8")
  
  return {
    "room_name": room_name,
    "token": token,
    "message": message
  }
