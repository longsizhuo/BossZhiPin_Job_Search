# Python 目录技术说明

## 目录结构
```
python/
├── grpc_server.py     # gRPC 服务器实现
├── job_service.proto  # gRPC 服务定义文件
├── job_service_pb2.py # 自动生成的 gRPC 代码
├── job_service_pb2_grpc.py # 自动生成的 gRPC 代码
├── write_response.py  # 响应处理模块
└── requirements.txt   # Python 依赖配置
```

## 功能说明

### gRPC 服务器 (grpc_server.py)
- 实现 gRPC 服务接口
- 处理简历上传和存储
- 管理 API 密钥配置
- 处理职位搜索请求
- 提供日志记录功能

### 服务定义 (job_service.proto)
- 定义 gRPC 服务接口
- 定义请求和响应消息格式
- 定义服务方法

### 响应处理 (write_response.py)
- 处理职位搜索响应
- 格式化输出结果
- 与 ChatGPT 集成

## 技术栈
- Python 3.x
- gRPC
- Protocol Buffers
- OpenAI API

## 关键功能
1. 简历文件管理
2. API 密钥验证
3. 职位搜索处理
4. 结果格式化
5. 日志记录 