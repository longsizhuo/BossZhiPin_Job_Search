# Boss直聘自动投递助手 - 技术文档

## 项目概述

这是一个基于 Electron 和 gRPC 的桌面应用，用于自动化 Boss 直聘的职位投递流程。项目采用前后端分离架构，使用 Python 处理后端逻辑，Electron 提供图形界面。

## 技术栈

- **前端**：Electron + HTML/CSS/JavaScript
- **后端**：Python + gRPC
- **构建工具**：electron-builder
- **包管理器**：npm/pnpm

## 项目结构

```plaintext
BossZhiPin_Job_Search/
├── electron/                 # Electron 前端
│   ├── src/
│   │   ├── main.js          # 主进程
│   │   └── renderer/        # 渲染进程
│   │       ├── index.html   # 主界面
│   │       ├── styles.css   # 样式
│   │       └── app.js       # 渲染进程逻辑
│   └── package.json         # 项目配置
└── python/                  # Python 后端
    ├── grpc_server.py      # gRPC 服务器
    └── write_response.py   # 业务逻辑处理
```

## 核心功能实现

### 1. 主进程 (main.js)

主进程负责创建应用窗口、启动 Python gRPC 服务器，并处理与渲染进程的通信。

```javascript
// 创建应用窗口
function createWindow() {
    mainWindow = new BrowserWindow({
        width: 800,
        height: 600,
        webPreferences: {
            nodeIntegration: true,
            contextIsolation: false
        }
    });
}

// 启动 Python gRPC 服务器
function startPythonServer() {
    pythonProcess = spawn('python', ['grpc_server.py']);
    // 设置 gRPC 客户端
    setupGrpcClient();
}

// 处理 IPC 通信
ipcMain.handle('start-job', async (event, data) => {
    // 处理任务启动逻辑
});
```

### 2. 渲染进程 (app.js)

渲染进程处理用户界面交互，包括文件上传、配置管理和任务控制。

```javascript
// 文件上传处理
async function handleFileUpload(file) {
    const buffer = await file.arrayBuffer();
    await ipcRenderer.invoke('upload-resume', new Uint8Array(buffer));
}

// 任务控制
startJobBtn.addEventListener('click', async () => {
    await ipcRenderer.invoke('start-job', { jobType, browserType });
});
```

### 3. gRPC 通信

使用 gRPC 实现前后端通信：

```javascript
// 设置 gRPC 客户端
const grpc = require('@grpc/grpc-js');
const protoLoader = require('@grpc/proto-loader');

// 加载 proto 文件
const PROTO_PATH = path.join(__dirname, '../protos/job_service.proto');
const packageDefinition = protoLoader.loadSync(PROTO_PATH);
```

## 用户界面设计

### 1. 布局结构

```html
<div class="container">
    <h1>Boss直聘自动投递助手</h1>
    
    <!-- 简历上传区域 -->
    <div class="section">
        <h2>上传简历</h2>
        <div class="upload-area" id="dropZone">
            <!-- 上传区域内容 -->
        </div>
    </div>

    <!-- OpenAI 配置 -->
    <div class="section">
        <h2>OpenAI 配置</h2>
        <!-- 配置表单 -->
    </div>

    <!-- 任务配置 -->
    <div class="section">
        <h2>任务配置</h2>
        <!-- 任务设置 -->
    </div>
</div>
```

### 2. 响应式设计

```css
@media (max-width: 600px) {
    .container {
        padding: 10px;
    }
    
    .section {
        padding: 15px;
    }
    
    button {
        width: 100%;
        margin-bottom: 10px;
    }
}
```

## 通信流程

1. **用户界面交互**：
   - 用户在渲染进程中操作界面
   - 触发事件通过 IPC 发送到主进程

2. **主进程处理**：
   - 主进程接收 IPC 消息
   - 通过 gRPC 调用 Python 后端服务

3. **后端处理**：
   - Python 后端处理业务逻辑
   - 返回结果通过 gRPC 发送回主进程

4. **结果展示**：
   - 主进程通过 IPC 将结果发送到渲染进程
   - 渲染进程更新界面显示

## 依赖管理

主要依赖包：
```json
{
    "dependencies": {
        "electron": "^29.4.6",
        "@grpc/grpc-js": "^1.13.2",
        "@grpc/proto-loader": "^0.7.13"
    }
}
```

## 开发指南

### 1. 环境设置

1. 安装 Node.js 和 Python
2. 安装项目依赖：
   ```bash
   # 安装前端依赖
   cd electron
   npm install

   # 安装后端依赖
   cd ../python
   pip install -r requirements.txt
   ```

### 2. 开发流程

1. **前端开发**：
   - 修改 `src/renderer` 下的文件
   - 使用 `npm start` 启动应用

2. **后端开发**：
   - 修改 Python 后端代码
   - 重启 gRPC 服务器

### 3. 调试技巧

1. **前端调试**：
   - 使用 Chrome DevTools 调试渲染进程
   - 使用 `console.log` 输出调试信息

2. **后端调试**：
   - 使用 Python 调试器
   - 查看 gRPC 服务器日志

## 注意事项

1. 确保 Python 环境正确配置
2. 保持 gRPC 服务正常运行
3. 注意文件路径的正确性
4. 处理异步操作和错误情况

## 常见问题

1. **gRPC 连接失败**：
   - 检查 Python 服务是否运行
   - 验证端口配置是否正确

2. **文件上传失败**：
   - 检查文件大小限制
   - 验证文件格式

3. **界面无响应**：
   - 检查 IPC 通信是否正常
   - 查看主进程日志

## 服务器启动和连接检查

1. **服务器启动**：
   - 检查 Python 服务是否启动
   - 确认端口 50051 未被占用
   - 查看服务器输出日志

2. **连接测试**：
   - 检查网络连接
   - 确认防火墙设置
   - 验证服务器地址和端口

3. **超时处理**：
   - 设置合理的超时时间
   - 处理连接超时情况

4. **错误处理**：
   - 捕获并处理连接错误
   - 提供用户友好的错误提示

## 启动流程

1. **用户启动**：
   - 用户启动 Electron 应用
   - 主进程创建应用窗口
   - 主进程启动 Python gRPC 服务器

2. **等待服务器**：
   - 等待服务器输出启动成功标志
   - 建立 gRPC 连接并测试

3. **连接成功**：
   - 连接成功后通知渲染进程
   - 用户界面准备就绪，可以开始操作

## 错误处理

1. **服务器启动失败**：
   - 检查 Python 环境
   - 确认端口 50051 未被占用
   - 查看服务器错误输出

2. **连接超时**：
   - 检查网络连接
   - 确认防火墙设置
   - 验证服务器地址和端口

3. **文件上传失败**：
   - 检查文件权限
   - 确认磁盘空间
   - 验证文件格式

4. **任务执行错误**：
   - 捕获并处理任务执行错误
   - 提供用户友好的错误提示

## 依赖管理

主要依赖包：
```json
{
    "dependencies": {
        "@grpc/grpc-js": "^1.9.13",
        "@grpc/proto-loader": "^0.7.0"
    },
    "devDependencies": {
        "electron": "^28.1.0",
        "electron-builder": "^24.9.1"
    }
}
```

## 开发指南

1. **环境设置**：
   - 安装 Node.js 和 Python
   - 安装项目依赖
   - 配置 Python 环境

2. **开发流程**：
   - 修改 proto 文件后需要重新生成代码
   - 启动 Python 服务器进行测试
   - 使用 `npm start` 启动 Electron 应用

3. **调试提示**：
   - 查看主进程日志了解服务器状态
   - 使用 Chrome DevTools 调试渲染进程
   - 检查 Python 服务器输出排查问题

## 常见问题

1. **服务器启动失败**：
   - 检查 Python 环境
   - 确认端口 50051 未被占用
   - 查看服务器错误输出

2. **连接超时**：
   - 检查网络连接
   - 确认防火墙设置
   - 验证服务器地址和端口

3. **文件上传失败**：
   - 检查文件权限
   - 确认磁盘空间
   - 验证文件格式 