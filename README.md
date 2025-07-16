# CoBridge4OriginCar 使用说明

## 文件说明
- `CoBridge4OriginCar.exe` - 主程序
- `config.yaml` - 配置文件
- `map.png` - 地图文件

## 使用方法

### 1. 直接运行
双击 `CoBridge4OriginCar.exe` 即可运行程序

### 2. 命令行运行
```cmd
CoBridge4OriginCar.exe [IP地址] [端口号]
```
example:
```cmd
CoBridge4OriginCar.exe 192.168.1.170 21274
```

## 配置说明
编辑 `config.yaml` 文件可以修改以下设置：
- `ip`: 服务器IP地址
- `port`: 服务器端口号
- `map_path`: 地图文件路径
- `linear`: 默认线速度
- `angular`: 默认角速度
- `dert`: 速度调整增量
- `username`: 用户名
- `userId`: 用户ID

## 控制说明
- W/A/S/D: 控制小车移动
- 方向键: 调整速度参数
- R: 开始控制
- P: 暂停控制
- T: 显示帮助
- M: 重新发布地图
- ESC: 退出程序

## 注意事项
1. 确保所有文件在同一目录下
2. 确保目标服务器可访问
3. 首次运行可能需要防火墙授权

## 故障排除
1. 如果连接失败，检查IP和端口设置
2. 如果键盘控制无效，尝试以管理员身份运行
3. 如果找不到地图文件，确保map.png在程序目录下
