# ADR-005：Phase D 用 pytauri standalone 打独立 .app，双运行模式并存

- **状态**：已采纳
- **日期**：2026-06-07
- **决策人**：longsizhuo

## 背景

桌面 GUI（PyTauri）此前只有 wheel dev 模式：用户必须 clone 仓库、装 uv、
`uv sync --extra tauri` 再 `uv run python -m boss_zhipin.tauri`。对目标用户
（找工作的非程序员朋友）这条链路太长——Phase D 的目标是发一个**双击就能跑**
的 .app。

## 选项

### 选项 1：PyInstaller / Nuitka 打包
- ✅ Python 生态最常见的打包方式
- ⛔ 跟 PyTauri 的 Rust binary 模型对不上——PyTauri 的窗口/IPC 在 Rust 侧，
  PyInstaller 只会打 Python 侧
- ⛔ chromadb / torch 的 hook 维护成本出名地高

### 选项 2：pytauri-wheel 直接发 wheel + 一键安装脚本
- ✅ 不需要 Rust 工程
- ⛔ 还是要求用户有 Python 环境，"双击就能跑"达不到
- ⛔ wheel 里的预编译 Rust binary 不能带自定义 bundle 资源 / 签名

### 选项 3：pytauri standalone（采纳）
- ✅ pytauri 官方支持的发布路径：Rust binary 是主进程，embed 一个
  python-build-standalone 解释器，`tauri bundle` 打成 .app/.dmg
- ✅ Tauri 配置（窗口/图标/签名）走标准 Tauri 工具链
- ⛔ 引入一个 Rust 工程（`src-tauri/`）要维护
- ⛔ 体积大：嵌入式 Python + torch + chromadb ≈ 1.5GB dmg（见"体积"）

## 双运行模式

`BOSS_TAURI_STANDALONE=1`（Rust `main.rs` 启动时 set）区分：

| | wheel dev 模式 | standalone 模式 |
|---|---|---|
| 主进程 | Python（`python -m boss_zhipin.tauri`） | Rust binary |
| Tauri 来源 | `pytauri-wheel` 预编译 binary | `src-tauri/` 自己编译 |
| Tauri 配置 | 运行时读 `src/boss_zhipin/tauri/Tauri.toml` | 编译期 `generate_context!` 嵌入 |
| capabilities | `tauri/capabilities/default.toml` | `src-tauri/capabilities/default.json` |
| CWD / 数据目录 | repo root（历史行为） | `paths.ensure_app_data_cwd()` → `~/Library/Application Support/com.longsizhuo.boss-zhipin` |

两份 capabilities / 四处版本号靠 `tests/test_standalone_sync.py` 守卫。

## 构建：只能走 `scripts/build_standalone.sh`

**不要手工跑其中某几步。** 2026-06-07 的第一次手工构建漏了
`PYO3_PYTHON` + `RUSTFLAGS`，pyo3 自动探测到系统 CLT 的
`Python3.framework 3.9`，.app 启动直接 dyld crash
（`Library not loaded: @rpath/Python3.framework/Versions/3.9/Python3`）。

脚本固化的关键步骤：
1. python-build-standalone（经 `uv python install`）→ `src-tauri/pyembed/python`
2. macOS：`install_name_tool -id '@rpath/libpython3.13.dylib'` 补丁
   （python-build-standalone 的 install_name 不带 @rpath，rpath 会失效）
3. `uv pip install ".[standalone]"` 进嵌入环境——`standalone` extra 不带
   `pytauri-wheel`（ext_mod 由我们的 Rust binary 提供）
4. `PYO3_PYTHON` 指向嵌入式解释器 + `RUSTFLAGS` 设
   `-rpath @executable_path/../Resources/lib` 和 `-L pyembed/python/lib`
5. `tauri build --config src-tauri/tauri.bundle.json -- --profile bundle-release`
   （独立 profile，不污染 `tauri dev` 的 target/release；bundle resources
   把 `pyembed/python` 整个拷进 .app 的 Resources/）

## 体积

dmg ≈ 1.5GB，大头是 torch（sentence-transformers 的依赖）。已知但暂不处理：

- 换轻量 embedding（如 ONNX 版模型）能砍掉 ~1GB，但要动 vectorization 的
  召回质量验证，单独立项
- `standalone` extra 去掉 pytauri-wheel 已省 ~40MB
- 不能为了体积去掉 RAG——deepseek/claude 模式依赖它

## 后果

- `src-tauri/**` 变更由 `.github/workflows/rust.yml` 的 `cargo check` 兜底
- 发版 checklist 多一步：四处版本号同步（测试会拦）
- standalone 的用户数据（.env / chrome_profile / logs / vectorstores）落在
  `~/Library/Application Support/com.longsizhuo.boss-zhipin/`，跟 repo 模式
  互不干扰
