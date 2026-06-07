请首先配置好openai的api，随后将pdf简历上传到文件夹auto_job_find里，命名为“my_cover".随后执行write_response.py即可
会自动生成openai的assistant，并在本地产生一个.json文件，只有第一次运行的时候才会产生，后面每次运行如果检测到这个json，就会调用已有的assistant


关于openai部分的包：
openai

About RPA
tutorial video about how to learn rpa: https://www.youtube.com/watch?v=65OPFmEgCbM&list=PLx4LEkEdFArgrdD_lvXe_hYBy8zM0Sp3b&index=1
Package of RPA
selenium
robotframework
robotframework-seleniumlibrary
robotframework-pythonlibcore

Plugin: Intellibot@Selenium Library

1. 项目结构设计
我们创建了一个基于 Electron 和 gRPC 的桌面应用，采用前后端分离架构：
    1. Python 后端：处理核心业务逻辑
    2. Electron 前端：提供图形界面
2. 后端设计

```python
## 主要组件：
- grpc_server.py：gRPC 服务器，处理前端请求
- write_response.py：处理职位描述和聊天功能
```
3. 前端设计
```text
electron/
├── src/
│   ├── main.js          # 主进程
│   └── renderer/        # 渲染进程
│       ├── index.html   # 主界面
│       ├── styles.css   # 样式
│       └── app.js       # 渲染进程逻辑
```


