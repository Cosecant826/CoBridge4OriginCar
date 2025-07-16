import websocket  
import json  
import struct  
import time  
  
def create_twist_cdr_data():  
    """手动构造 geometry_msgs/Twist 的 CDR 格式数据"""  
    # Twist 消息结构：  
    # Vector3 linear (3 个 float64)  
    # Vector3 angular (3 个 float64)  
      
    # 设置速度值  
    linear_x = 0.5   # 前进速度  
    linear_y = 0.0  
    linear_z = 0.0  
    angular_x = 0.0  
    angular_y = 0.0  
    angular_z = 0.1  # 转向速度  
      
    # CDR 格式：小端序，8字节对齐的 float64  
    cdr_data = bytearray()  
      
    # CDR 头部 (4 bytes): 0x00, 0x01, 0x00, 0x00 (小端序)  
    cdr_data.extend([0x00, 0x01, 0x00, 0x00])  
      
    # Linear velocity (3 个 float64)  
    cdr_data.extend(struct.pack('<d', linear_x))  
    cdr_data.extend(struct.pack('<d', linear_y))  
    cdr_data.extend(struct.pack('<d', linear_z))  
      
    # Angular velocity (3 个 float64)  
    cdr_data.extend(struct.pack('<d', angular_x))  
    cdr_data.extend(struct.pack('<d', angular_y))  
    cdr_data.extend(struct.pack('<d', angular_z))  
      
    return cdr_data  
  
def publish_cmd_vel():  
    # 连接到设备端的 cobridge 服务器  
    uri = "ws://192.168.189.170:21274"  
      
    # 创建 WebSocket 连接  
    ws = websocket.WebSocket()  
    try:  
        ws.connect(uri, subprotocols=["coBridge.websocket.v1"])  
        print("Connected to cobridge server")  
          
        # 等待服务器发送登录提示  
        response = ws.recv()  
        print(f"Server response: {response}")  
          
        # 登录  
        login_msg = {  
            "op": "login",  
            "username": "robot_controller",  
            "userId": "controller-001"  
        }  
        ws.send(json.dumps(login_msg))  
          
        # 接收登录响应  
        response = ws.recv()  
        print(f"Login response: {response}")  
          
        # 广告 cmd_vel 话题  
        advertisement = {  
            "op": "advertise",  
            "channels": [{  
                "id": 1,  
                "topic": "/cmd_vel",  
                "encoding": "cdr",  
                "schemaName": "geometry_msgs/msg/Twist"  
            }]  
        }  
        ws.send(json.dumps(advertisement))  
        print("Advertised /cmd_vel topic")  
          
        # 等待话题被服务器确认  
        time.sleep(1)  
          
        # 创建 CDR 格式的 Twist 消息  
        twist_cdr = create_twist_cdr_data()  
          
        # 构造二进制消息  
        channel_id = 1  
        payload = bytearray()  
        payload.append(1)  # MESSAGE_DATA opcode  
        payload.extend(struct.pack('<I', channel_id))  # channel_id (小端序 uint32)  
        payload.extend(twist_cdr)  
          
        # 发布消息  
        ws.send_binary(payload)  
        print("Published Twist message to /cmd_vel")  
          
        # 可以持续发布消息  
        for i in range(5):  
            time.sleep(1)  
            ws.send_binary(payload)  
            print(f"Published message {i+2}")  
              
    except Exception as e:  
        print(f"Error: {e}")  
    finally:  
        ws.close()  
        print("Connection closed")  
  
if __name__ == "__main__":  
    # 安装依赖: pip install websocket-client  
    publish_cmd_vel()