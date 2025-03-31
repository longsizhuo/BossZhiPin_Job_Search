# 🤝 How to Contribute to BossZhiPin_Job_Search

## 🌟 简介 | Introduction
欢迎你为本项目做出贡献！无论你是开发新功能、优化现有代码，还是改进用户界面或文档，我们都非常欢迎。
Welcome, and thank you for your interest in contributing! Whether you're fixing bugs, improving the UI, or adding new features, we appreciate your help.

---

## 🚀 如何运行本项目 | How to Run the Project

### 步骤一：安装依赖 | Step 1: Install Dependencies
```bash
pip install -r requirements.txt
```

### 步骤二：配置 OpenAI API 密钥 | Step 2: Add OpenAI API Key
在项目根目录创建 `.env` 文件，并写入以下内容：
Create a `.env` file in the root directory and add:
```env
OPENAI_API_KEY=your_openai_api_key_here
```

---

## 🌱 当前贡献路线 | Current Contribution Paths

本项目分为两个主要贡献方向：
There are two current development paths you can contribute to:

### 1️⃣ UI 可视化路线（dev 分支）| UI Route (`dev` branch)
目标：让不会写代码的人也能使用本工具。
Goal: Make the tool usable for non-technical users.

- ✅ 提供简单直观的界面，只需填写 API Key 和简历即可运行。
- 🐛 修复运行一次后不能继续的问题（当前必须重启脚本）。
- 💡 可能采用 Streamlit、Gradio 或 Flask 构建界面。

📸 当前界面截图：
<img width="590" alt="0b929fc5f54bbf149bc74c93d682e76" src="https://github.com/user-attachments/assets/ba0658a7-4c0d-4651-8bef-2764ca1a34ea" />


### 2️⃣ 功能增强路线（main 分支）| Feature Enhancements (`main` branch)
目标：提升功能完整性，增强交互能力。
Goal: Add new capabilities to enhance job search automation.

- 🖼 用户可在对话中附加图片，例如上传简历截图或职位截图。
- 🔍 将图片信息与文本合并传送至 OpenAI（考虑使用 base64, PIL, requests 等）


---

## 🧑‍💻 如何提交代码 | How to Contribute

### 🔀 Fork 本项目 | Fork this Repository
点击右上角的 `Fork` 按钮，将本项目复制到你的账户。
Click the `Fork` button to copy the project to your GitHub.

### 📂 创建新分支 | Create a Feature Branch
```bash
git checkout -b your-feature-name
```
- UI 开发建议从 `dev` 分支创建
- 新功能开发建议从 `main` 分支创建

### ✏️ 编写并测试代码 | Write and Test Your Code
- 保持代码风格一致（推荐使用 `black`）
- 添加必要的注释和测试
- 本地运行确认无异常

### ✅ 提交更改 | Commit Changes
```bash
git add .
git commit -m "Add: your change description"
git push origin your-feature-name
```

### 📩 创建 Pull Request
- 若基于 `dev` 分支，PR 请提交至 `dev`
- 若基于 `main` 分支，PR 请提交至 `main`

请在 PR 中说明：
- 所完成的内容
- 修改原因
- 是否通过测试

---

## 🙋‍♂️ 有问题？| Questions?
欢迎在 Discussions 区或通过 Issues 提问！
Ask in Discussions or open an Issue — we’re happy to help!

---

感谢你的贡献！Thanks for contributing and making this project better! 🎉

