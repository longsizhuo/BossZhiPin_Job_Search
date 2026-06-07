# Resume 目录技术说明

## 目录结构
```
resume/               # 简历存储目录
└── .gitkeep         # Git 空目录占位文件
```

## 功能说明

### 简历存储
- 用于存储用户上传的简历文件
- 作为临时存储位置
- 实际文件会被复制到用户数据目录和桌面

## 存储位置
1. 应用数据目录：
   - Windows: `%LOCALAPPDATA%\BossZhiPin\BossZhiPin_Job_Search\resume\`
   - 用于程序内部访问

2. 桌面：
   - `Desktop\BossZhiPin_Resume_文件名`
   - 方便用户访问和管理

## 文件命名规则
- 如果用户提供文件名：使用用户提供的文件名
- 如果文件名为空：使用 `resume_时间戳.pdf` 格式

## 注意事项
1. 此目录主要用于开发环境
2. 生产环境中文件会被复制到用户可访问的位置
3. 目录通过 .gitkeep 文件保持在版本控制中 