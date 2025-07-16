#!/usr/bin/python3    
# -*- coding: utf-8 -*-    
    
import websocket    
import json    
import struct    
import time    
import cv2    
import keyboard    
from threading import Thread    
import os    
import subprocess    
import sys    
import signal    
import atexit    
import platform    
import yaml    
    
Host = "192.168.189.170"    
Port = 21274    
Map_path = "map.png"    
Linear = 0.25    
Angular = 3.14    
Dert = 0.3    
    
class CoBridge2OriginCar:    
    def __init__(self, host="192.168.189.170", port=21274, map_path="map.png", linear=0.5, angular=1.57, dert=0.1):    
        self.host = host    
        self.port = port    
        self.image_path = map_path    
        self.linear = linear    
        self.angular = angular    
        self.dert = dert    
        self.argv = sys.argv    
        self.system_str = platform.system()    
        self.isStartTelemetry = False    
        self.isOverTelemetry = False    
        self.signFlag = False    
        self.ws = None    
        self.connected = False  
        # 添加话题映射表和延迟订阅支持  
        self.topic_to_channel_id = {}  
        self.pending_subscriptions = {}  
        self.signMsg = {'data': 0}  
        self.init()    
    
    def create_twist_cdr_data(self, linear_x=0.0, angular_z=0.0):    
        """创建 geometry_msgs/Twist 的 CDR 格式数据"""    
        cdr_data = bytearray()    
        # CDR 头部    
        cdr_data.extend([0x00, 0x01, 0x00, 0x00])    
        # Linear velocity (3 个 float64)    
        cdr_data.extend(struct.pack('<d', linear_x))    
        cdr_data.extend(struct.pack('<d', 0.0))    
        cdr_data.extend(struct.pack('<d', 0.0))    
        # Angular velocity (3 个 float64)    
        cdr_data.extend(struct.pack('<d', 0.0))    
        cdr_data.extend(struct.pack('<d', 0.0))    
        cdr_data.extend(struct.pack('<d', angular_z))    
        return cdr_data    
    
    def create_occupancy_grid_cdr_data(self, map_data):    
        """创建 nav_msgs/OccupancyGrid 的 CDR 格式数据"""    
        cdr_data = bytearray()    
        # CDR 头部    
        cdr_data.extend([0x00, 0x01, 0x00, 0x00])    
            
        # Header    
        # stamp (builtin_interfaces/Time)    
        cdr_data.extend(struct.pack('<i', map_data['header']['stamp']['sec']))    
        cdr_data.extend(struct.pack('<I', map_data['header']['stamp']['nanosec']))    
        # frame_id (string)    
        frame_id = map_data['header']['frame_id'].encode('utf-8')    
        cdr_data.extend(struct.pack('<I', len(frame_id)))    
        cdr_data.extend(frame_id)    
            
        # MapMetaData info    
        # map_load_time    
        cdr_data.extend(struct.pack('<i', map_data['info']['map_load_time']['sec']))    
        cdr_data.extend(struct.pack('<I', map_data['info']['map_load_time']['nanosec']))    
        # resolution    
        cdr_data.extend(struct.pack('<f', map_data['info']['resolution']))    
        # width, height    
        cdr_data.extend(struct.pack('<I', map_data['info']['width']))    
        cdr_data.extend(struct.pack('<I', map_data['info']['height']))    
        # origin (geometry_msgs/Pose)    
        # position    
        cdr_data.extend(struct.pack('<d', map_data['info']['origin']['position']['x']))    
        cdr_data.extend(struct.pack('<d', map_data['info']['origin']['position']['y']))    
        cdr_data.extend(struct.pack('<d', map_data['info']['origin']['position']['z']))    
        # orientation    
        cdr_data.extend(struct.pack('<d', map_data['info']['origin']['orientation']['x']))    
        cdr_data.extend(struct.pack('<d', map_data['info']['origin']['orientation']['y']))    
        cdr_data.extend(struct.pack('<d', map_data['info']['origin']['orientation']['z']))    
        cdr_data.extend(struct.pack('<d', map_data['info']['origin']['orientation']['w']))    
            
        # data array    
        data_array = map_data['data']    
        cdr_data.extend(struct.pack('<I', len(data_array)))    
        for value in data_array:    
            cdr_data.extend(struct.pack('<b', value))    
            
        return cdr_data    
    
    def create_int32_cdr_data(self, value):    
        """创建 std_msgs/Int32 的 CDR 格式数据"""    
        cdr_data = bytearray()    
        # CDR 头部    
        cdr_data.extend([0x00, 0x01, 0x00, 0x00])    
        # int32 data    
        cdr_data.extend(struct.pack('<i', value))    
        return cdr_data    
    
    def publish_message(self, channel_id, cdr_data):    
        """发布二进制消息到指定通道"""    
        if not self.connected or not self.ws:    
            return    
            
        payload = bytearray()    
        payload.append(1)  # MESSAGE_DATA opcode    
        payload.extend(struct.pack('<I', channel_id))    
        payload.extend(cdr_data)    
            
        try:    
            self.ws.send(payload, websocket.ABNF.OPCODE_BINARY)  
        except Exception as e:    
            print(f"发布消息失败: {e}")  
  
    def handle_text_message(self, message):  
        """处理文本消息，包括服务器广告"""  
        try:  
            msg = json.loads(message)  
            op = msg.get("op")  
              
            if op == "advertise":  
                # 处理服务器广告的话题  
                channels = msg.get("channels", [])  
                # print(f"服务器广告了 {len(channels)} 个话题:")  
                for channel in channels:  
                    topic_name = channel.get("topic")  
                    channel_id = channel.get("id")  
                    schema_name = channel.get("schemaName", "")  
                    # print(f"  - {topic_name} (ID: {channel_id}, 类型: {schema_name})")  
                    if topic_name and channel_id is not None:  
                        self.topic_to_channel_id[topic_name] = channel_id  
                          
                        # 检查是否有待订阅的话题  
            #             if topic_name in self.pending_subscriptions:  
            #                 print(f"检测到待订阅话题 {topic_name}，准备订阅...")  
              
            # elif op == "serverInfo":  
            #     print(f"服务器信息: {message}")  
                  
        except json.JSONDecodeError:  
            pass  # 忽略非 JSON 消息  
  
    def handle_binary_message(self, message):  
        """处理二进制消息，包括订阅的话题数据"""  
        if len(message) < 5:  
            return  
            
        opcode = message[0]  
        if opcode == 1:  # MESSAGE_DATA  
            subscription_id = struct.unpack('<I', message[1:5])[0]  
            
            # 根据 subscription_id 路由到相应的回调  
            if subscription_id == 1:  # /sign4return 的 subscription_id  
                # 跳过 opcode(1) + subscription_id(4) + timestamp(8) = 13 字节  
                if len(message) >= 13:  
                    payload = message[13:]  # 从第13字节开始是实际的CDR数据  
                    
                    # 检查CDR头部并跳过 (通常是4字节)  
                    if len(payload) >= 8:  # CDR头部4字节 + int32数据4字节  
                        # 跳过CDR头部，直接读取int32数据  
                        value = struct.unpack('<i', payload[4:8])[0]  
                        msg = {'data': value}  
                        print(f"解析到的值: {value}")  # 调试输出  
                        self.sign_sub_callback(msg)  
  
    def monitor_topics(self):  
        """监控话题出现并自动订阅"""  
        while True:  
            time.sleep(1)  # 每秒检查一次  
              
            for topic_name, sub_info in list(self.pending_subscriptions.items()):  
                if topic_name in self.topic_to_channel_id:  
                    channel_id = self.topic_to_channel_id[topic_name]  
                      
                    # 创建订阅  
                    subscribe_msg = {  
                        "op": "subscribe",  
                        "subscriptions": [  
                            {  
                                "id": sub_info["subscription_id"],  
                                "channelId": channel_id  
                            }  
                        ]  
                    }  
                      
                    try:  
                        self.ws.send(json.dumps(subscribe_msg))  
                        # print(f"成功订阅话题 {topic_name} (channel ID: {channel_id})")  
                          
                        # 从待订阅列表中移除  
                        del self.pending_subscriptions[topic_name]  
                          
                    except Exception as e:  
                        print(f"订阅话题 {topic_name} 失败: {e}")  
    
    def init(self):    
        self.init_cfg()    
        self.init_arg()    
        self.init_keymap()    
        self.check_host()    
        self.init_cobridge_interface()    
        self.init_topic()    
        self.open_costudio()    
        self.init_keyboard()    
        self.keep()    
    
    def init_cfg(self):    
        try:    
            with open('config.yaml', 'r', encoding='utf-8') as f:    
                cfgDict = yaml.load(f.read(), Loader=yaml.FullLoader)    
            self.host = cfgDict['ip']    
            self.port = int(cfgDict['port'])    
            self.image_path = cfgDict['map_path']    
            self.linear = float(cfgDict['linear'])    
            self.angular = float(cfgDict['angular'])    
            self.dert = float(cfgDict['dert'])  
            self.username = cfgDict.get('username', 'cobridge_user')  
            self.userId = cfgDict.get('userId', 'zephyr_client')  
        except Exception as e:    
            print("config.yaml文件不存在或格式有误,请检查!")
            # 设置默认值
            self.username = 'cobridge_user'
            self.userId = 'zephyr_client'    
    
    def init_arg(self):    
        if len(self.argv) == 1:    
            print("默认ip:{}.\n默认端口号:{}.".format(self.host, self.port))    
        elif len(self.argv) == 2:    
            self.host = self.argv[1]    
            print("ip:{}.\n默认端口号:{}.".format(self.host, self.port))    
        elif len(self.argv) == 3:    
            self.host = self.argv[1]    
            self.port = int(self.argv[2])    
            print("ip:{}.\n端口号:{}.".format(self.host, self.port))    
        else:    
            print("************************")    
            print("***** 传入参数错误 *****")    
            print("************************")    
            self.exit_wait()    
    
    def init_keymap(self):    
        self.key_mapping = {    
            'up': {'linear': self.linear, 'angular': 0.0},    
            'down': {'linear': -self.linear, 'angular': 0.0},    
            'left': {'linear': 0.0, 'angular': self.angular},    
            'right': {'linear': 0.0, 'angular': -self.angular},    
            'up_left': {'linear': self.linear, 'angular': self.angular},    
            'up_right': {'linear': self.linear, 'angular': -self.angular},    
            'down_left': {'linear': -self.linear, 'angular': self.angular},    
            'down_right': {'linear': -self.linear, 'angular': -self.angular},    
            'stop': {'linear': 0.0, 'angular': 0.0}    
        }    
    
    def check_host(self):    
        if self.system_str == 'Windows':    
            ret = os.system("ping -n 1 -w 1 {}".format(self.host))    
        elif self.system_str == 'Linux':    
            ret = os.system("ping -c 1 -w 1 {}".format(self.host))    
            
        spa = ' ' * (13 - len(self.host))    
        print('\n\n')    
        if ret:    
            print("************************")    
            print("*** ip:{}{} ***".format(self.host, spa))    
            print("*** 无法访问, 请重试 ***")    
            print("************************")    
            self.exit_wait()    
        else:    
            print("************************")    
            print("*** ip:{}{} ***".format(self.host, spa))    
            print("*** ip有效, 正在连接 ***")    
            print("************************")    
            print("\n连接主机 ws://{}:{}.".format(self.host, self.port))    
    
    def init_cobridge_interface(self):    
        try:    
            uri = "ws://{}:{}".format(self.host, self.port)  
              
            # 使用 WebSocketApp 而不是 WebSocket  
            def on_message(ws, message):  
                if isinstance(message, str):  
                    self.handle_text_message(message)  
                else:  
                    self.handle_binary_message(message)  
              
            def on_open(ws):  
                print("WebSocket 连接已打开")  
                # 登录  
                login_msg = {  
                    "op": "login",  
                    "username": self.username,  
                    "userId": self.userId  
                }  
                ws.send(json.dumps(login_msg))  
              
            def on_error(ws, error):  
                print(f"WebSocket 错误: {error}")  
              
            def on_close(ws, close_status_code, close_msg):  
                print("WebSocket 连接已关闭")  
                self.connected = False  
              
            self.ws = websocket.WebSocketApp(  
                uri,  
                subprotocols=["coBridge.websocket.v1"],  
                on_message=on_message,  
                on_open=on_open,  
                on_error=on_error,  
                on_close=on_close  
            )  
              
            # 在后台线程中运行 WebSocket  
            import threading  
            self.ws_thread = threading.Thread(target=self.ws.run_forever)  
            self.ws_thread.daemon = True  
            self.ws_thread.start()  
              
            # 等待连接建立  
            time.sleep(2)  
            self.connected = True  
            print("连接已建立 ws://{}:{}.".format(self.host, self.port))  
              
        except Exception as e:  
            print("连接失败:\n1. 请检查端口是否开启\n2. 请检查端口号是否正确\n3. 请检查主机是否开启了cobridge ws://{}:{}.".format(self.host, self.port))  
            print(f"错误详情: {e}")  
            self.exit_wait()  
    
    def init_topic(self):    
        # 广告所有需要的话题    
        advertisements = {    
            "op": "advertise",    
            "channels": [    
                {    
                    "id": 1,    
                    "topic": "/map",    
                    "encoding": "cdr",    
                    "schemaName": "nav_msgs/msg/OccupancyGrid"    
                },    
                {    
                    "id": 2,    
                    "topic": "/cmd_vel",    
                    "encoding": "cdr",    
                    "schemaName": "geometry_msgs/msg/Twist"    
                },    
                {    
                    "id": 3,    
                    "topic": "/sign_foxglove",    
                    "encoding": "cdr",    
                    "schemaName": "std_msgs/msg/Int32"    
                }    
            ]    
        }    
        self.ws.send(json.dumps(advertisements))    
        # print("已广告所有话题")  
          
        # 设置延迟订阅机制  
        self.pending_subscriptions = {"/sign4return": {"subscription_id": 1, "callback": self.sign_sub_callback}}  
          
        # 启动话题监控线程  
        self.topic_monitor_thread = Thread(target=self.monitor_topics)  
        self.topic_monitor_thread.daemon = True  
        self.topic_monitor_thread.start()  
          
        # print("已设置 /sign4return 话题的延迟订阅")  
            
        # 处理地图数据    
        if os.path.exists(self.image_path):    
            print("存在地图, 正在解析...")    
            image = cv2.imread(self.image_path, cv2.IMREAD_GRAYSCALE)    
            image = cv2.flip(image, -1)    
            image = cv2.flip(image, 1)    
            
            map_width, map_height = image.shape[1], image.shape[0]    
            occupancy_data = []    
            for row in image:    
                occupancy_data.extend([0 if pixel < 128 else -1 for pixel in row])    
                    
            # 获取当前时间（简化版本）    
            current_time_sec = int(time.time())    
            current_time_nsec = int((time.time() - current_time_sec) * 1e9)    
                
            self.map_data = {    
                'header': {    
                    'stamp': {    
                        'sec': current_time_sec,    
                        'nanosec': current_time_nsec    
                    },    
                    'frame_id': 'odom_combined'    
                },    
                'info': {    
                    'map_load_time': {'sec': 0, 'nanosec': 0},    
                    'resolution': 5.0 / map_width,    
                    'width': map_width,    
                    'height': map_height,    
                    'origin': {    
                        'position': {'x': 0.0, 'y': 0.0, 'z': 0.0},    
                        'orientation': {'x': 0.0, 'y': 0.0, 'z': 0.0, 'w': 1.0}    
                    }    
                },    
                'data': occupancy_data    
            }    
                
            # 发布地图    
            time.sleep(1)  # 等待广告完成    
            map_cdr = self.create_occupancy_grid_cdr_data(self.map_data)    
            self.publish_message(1, map_cdr)  # channel_id = 1 for /map    
            print("已发布地图.")
        else:    
            print("当前程序目录:不存在 map.png，跳过地图发布...")
            self.map_data = None  # 标记没有地图数据
            
        # 发布初始信号    
        sign_cdr = self.create_int32_cdr_data(0)    
        self.publish_message(3, sign_cdr)  # channel_id = 3 for /sign_foxglove    
            
        print("信号连接正常.")    
        self.help_tip()    
        print("后台正在持续监听键盘命令.", end='  ')    
    
    def init_keyboard(self):    
        self.keyboard_thread = Thread(target=self.keyboard_listener)    
        self.keyboard_thread.daemon = True    
        self.keyboard_thread.start()    
          
    def open_costudio(self):    
        if self.system_str == "Windows":    
            print("当前操作系统为: Windows.")    
            local_appdata_path = os.getenv("LOCALAPPDATA")    
            if local_appdata_path:    
                foxglove_path = os.path.join(local_appdata_path, "Programs", "coStudio", "coStudio.exe")    
            else:    
                print("未找到环境变量 LOCALAPPDATA.")    
            try:    
                foxglove_process = subprocess.Popen(foxglove_path, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)    
                print("打开coStudio软件！")    
                foxglove_pid = foxglove_process.pid    
                print("在关闭终端时将会关闭coStudio软件...")    
    
                def on_exit():    
                    try:    
                        os.kill(foxglove_pid, signal.SIGTERM)    
                        print("已关闭coStudio软件！")    
                    except OSError:    
                        pass    
    
                atexit.register(on_exit)    
    
            except FileNotFoundError:    
                print("无法找到指定的coStudio软件, 请检查路径是否正确.")    
            except Exception as e:    
                print("发生了错误:", e)    
        elif self.system_str == "Linux":    
            print("当前操作系统为:Linux,需要手动以用户模式打开coStudio.")    
    
    def keep(self):    
        try:    
            while True:    
                for i in range(4):    
                    time.sleep(0.5)    
                    print('\b\b', ['/', '|', '\\', '-'][i], end="", flush=True)    
        except KeyboardInterrupt:    
            print("\n检测到ctrl + c, 是否确认退出！")    
            self.exit_wait()    
            if self.ws:    
                self.ws.close()    
    
    def exit_wait(self):    
        print("按ESC退出.")    
        while not keyboard.is_pressed('ESC'):    
            time.sleep(0.1)    
        exit()    
    
    def update_vel(self):    
        self.key_mapping['up']['linear'] = self.linear    
        self.key_mapping['down']['linear'] = -self.linear    
        self.key_mapping['left']['angular'] = self.angular    
        self.key_mapping['right']['angular'] = -self.angular    
        self.key_mapping['up_left']['linear'] = self.linear    
        self.key_mapping['up_left']['angular'] = self.angular    
        self.key_mapping['up_right']['linear'] = self.linear    
        self.key_mapping['up_right']['angular'] = -self.angular    
        self.key_mapping['down_left']['linear'] = -self.linear    
        self.key_mapping['down_left']['angular'] = self.angular    
        self.key_mapping['down_right']['linear'] = -self.linear    
        self.key_mapping['down_right']['angular'] = -self.angular    
    
    def keyboard_listener(self):    
        print("\n\n")    
        print("------------------------------------")    
        print("**** 按下   [ r ]   开始控制小车 ****")    
        print("**** 或者等待上位机发送开始遥测信号 ****")    
        print("------------------------------------")    
            
        while True:    
            time.sleep(0.05)    
            if keyboard.is_pressed('r') or self.isStartTelemetry:    
                self.isOverTelemetry = False    
                self.isStartTelemetry = False    
                print("\n正在继续键盘监听.")    
                break    
                    
        while True:    
            time.sleep(0.05)    
            self.update_sign()    
                
            if keyboard.is_pressed('p') or self.isOverTelemetry:    
                self.isOverTelemetry = False    
                self.isStartTelemetry = False    
                print("\n已退出键盘监听.")    
                print("同时按下[ r ]继续键盘监听.")    
                while True:    
                    if keyboard.is_pressed('r') or self.isStartTelemetry:    
                        self.isOverTelemetry = False    
                        self.isStartTelemetry = False    
                        print("\n正在继续键盘监听.")    
                        sign_cdr = self.create_int32_cdr_data(0)    
                        self.publish_message(3, sign_cdr)    
                        break    
                    time.sleep(0.05)    
                        
            # 键盘控制逻辑    
            if keyboard.is_pressed('w'):    
                if keyboard.is_pressed('a'):    
                    twist_cdr = self.create_twist_cdr_data(    
                        self.key_mapping['up_left']['linear'],    
                        self.key_mapping['up_left']['angular']    
                    )    
                    self.publish_message(2, twist_cdr)    
                elif keyboard.is_pressed('d'):    
                    twist_cdr = self.create_twist_cdr_data(    
                        self.key_mapping['up_right']['linear'],    
                        self.key_mapping['up_right']['angular']    
                    )    
                    self.publish_message(2, twist_cdr)    
                else:    
                    twist_cdr = self.create_twist_cdr_data(    
                        self.key_mapping['up']['linear'],    
                        self.key_mapping['up']['angular']    
                    )    
                    self.publish_message(2, twist_cdr)    
                        
            elif keyboard.is_pressed('s'):    
                if keyboard.is_pressed('d'):    
                    twist_cdr = self.create_twist_cdr_data(    
                        self.key_mapping['down_left']['linear'],    
                        self.key_mapping['down_left']['angular']    
                    )    
                    self.publish_message(2, twist_cdr)    
                elif keyboard.is_pressed('a'):    
                    twist_cdr = self.create_twist_cdr_data(    
                        self.key_mapping['down_right']['linear'],    
                        self.key_mapping['down_right']['angular']    
                    )    
                    self.publish_message(2, twist_cdr)    
                else:    
                    twist_cdr = self.create_twist_cdr_data(    
                        self.key_mapping['down']['linear'],    
                        self.key_mapping['down']['angular']    
                    )    
                    self.publish_message(2, twist_cdr)    
                        
            elif keyboard.is_pressed('a'):    
                twist_cdr = self.create_twist_cdr_data(    
                    self.key_mapping['left']['linear'],    
                    self.key_mapping['left']['angular']    
                )    
                self.publish_message(2, twist_cdr)    
                    
            elif keyboard.is_pressed('d'):    
                twist_cdr = self.create_twist_cdr_data(    
                    self.key_mapping['right']['linear'],    
                    self.key_mapping['right']['angular']    
                )    
                self.publish_message(2, twist_cdr)    
                    
            # 速度调整    
            elif keyboard.is_pressed("up"):    
                self.linear += self.dert    
                print("线速度设置为:{:.2f}m/s.".format(self.linear))    
                self.update_vel()    
                time.sleep(0.2)    
                    
            elif keyboard.is_pressed("down"):    
                if self.linear - self.dert < 0:    
                    print("速度设置失败！(线速度为:{:.2f}).".format(self.linear))    
                else:    
                    self.linear -= self.dert    
                    print("线速度设置为:{:.2f}m/s.".format(self.linear))    
                self.update_vel()    
                time.sleep(0.2)    
                    
            elif keyboard.is_pressed("left"):    
                if self.angular - self.dert < 0:    
                    print("角度设置失败！(转角为:{:.2f}rad).".format(self.angular))    
                else:    
                    self.angular -= self.dert    
                    print("角度设置为:{:.2f}rad.".format(self.angular))    
                self.update_vel()    
                time.sleep(0.2)  
            
            elif keyboard.is_pressed("right"):    
                self.angular += self.dert    
                print("转角设置为:{:.2f}rad.".format(self.angular))    
                self.update_vel()    
                time.sleep(0.2)    
                    
            elif keyboard.is_pressed('t'):    
                self.help_tip()    
                time.sleep(0.5)    
                    
            elif keyboard.is_pressed('m'):    
                if self.map_data is not None:
                    map_cdr = self.create_occupancy_grid_cdr_data(self.map_data)    
                    self.publish_message(1, map_cdr)
                    print("已重新发布地图.")
                else:
                    print("没有地图数据可发布.")    
                    
            else:    
                # 停止    
                twist_cdr = self.create_twist_cdr_data(    
                    self.key_mapping['stop']['linear'],    
                    self.key_mapping['stop']['angular']    
                )    
                self.publish_message(2, twist_cdr)    
    
    def update_sign(self):    
        if self.signFlag:    
            sign_cdr = self.create_int32_cdr_data(self.signMsg['data'])    
            self.publish_message(3, sign_cdr)    
            self.signFlag = False    
    
    def help_tip(self):    
        print("\n\n提示：")    
        print("按   [ p ] 退出键盘控制.")    
        print("按   [ r ] 回到键盘控制.")    
        print("按   [ m ] 重新发布地图.")    
        print("按   [ t ] 显示按键帮助.", end="\n\n")    
    
        print("控制：")    
        print("--- [ w ] --- 前进: {:.2f} m/s.".format(self.linear))    
        print("--- [ a ] --- 左转: {:.2f} rad.".format(self.angular))    
        print("--- [ d ] --- 右转: {:.2f} rad.".format(-self.angular))    
        print("--- [ s ] --- 后退: {:.2f} m/s.".format(-self.linear))    
    
        print("调整速度(使用键盘的方向键).")    
        print("---  [   up  ]  --- 增加线速度.")    
        print("---  [  left ]  --- 减小转角.")    
        print("---  [ right ]  --- 增加转角.")    
        print("---  [  down ]  --- 减小线速度.")    
    
    def sign_sub_callback(self, msg):    
        if msg['data'] == 5:    
            print("\n接收到[正在C区进行遥测]信号")    
            self.isStartTelemetry = True    
        elif msg['data'] == 6:    
            print("\n接收到[C区出口结束遥测]信号")    
            self.isOverTelemetry = True    
        self.signMsg = msg    
        self.signFlag = True    
    
    
if __name__ == "__main__":    
    cobridge2OriginCar = CoBridge2OriginCar(    
        host=Host,    
        port=Port,    
        map_path=Map_path,    
        linear=Linear,    
        angular=Angular,    
        dert=Dert    
    )