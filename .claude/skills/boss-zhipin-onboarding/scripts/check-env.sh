#!/usr/bin/env bash
# 一次性诊断小白用户目前卡在哪个里程碑。Agent 拿到输出后能直接看出
# 1/2/3/4/5 哪一步还没做，不用反复问。
#
# 用法：在项目根目录跑
#   bash .claude/skills/boss-zhipin-onboarding/scripts/check-env.sh
#
# 输出是结构化文本，每一行一个事实。Agent 读完应该能判断：
# - 哪些里程碑 ✓ 已完成
# - 哪些 ✗ 还没做
# - 出了什么具体的故障

set +e  # 故意不退出失败 —— 我们就是要把所有问题都列出来

echo "=== 里程碑 1：uv + git + 项目 clone ==="
if command -v uv >/dev/null 2>&1; then
    echo "  ✓ uv 已安装: $(uv --version)"
else
    echo "  ✗ uv 未安装。装：curl -LsSf https://astral.sh/uv/install.sh | sh"
fi
if command -v git >/dev/null 2>&1; then
    echo "  ✓ git 已安装: $(git --version)"
else
    echo "  ✗ git 未安装。macOS 跑 xcode-select --install / Ubuntu 跑 sudo apt install git"
fi
if [ -f "pyproject.toml" ] && grep -q "boss-zhipin-job-search" pyproject.toml 2>/dev/null; then
    echo "  ✓ 在 BossZhiPin_Job_Search 项目根目录里"
else
    echo "  ✗ 不在项目根目录（找不到 pyproject.toml 或里面没有 boss-zhipin-job-search）"
    echo "    先 cd 到 clone 下来的项目目录"
fi

echo ""
echo "=== 里程碑 2：uv sync 装依赖 ==="
if [ -d ".venv" ]; then
    echo "  ✓ .venv 存在（uv sync 跑过）"
    # 抽几个关键 import 检查
    if uv run python -c "import nodriver, openai, chromadb" 2>/dev/null; then
        echo "  ✓ 核心依赖 (nodriver/openai/chromadb) 都装了"
    else
        echo "  ✗ 某些依赖没装好，重跑 uv sync"
    fi
else
    echo "  ✗ .venv 不存在，跑 uv sync"
fi

echo ""
echo "=== 里程碑 3：.env 配置 ==="
if [ ! -f ".env.example" ]; then
    echo "  ✗ .env.example 不存在 —— git pull 拉最新代码"
elif [ ! -f ".env" ]; then
    echo "  ✗ .env 不存在。先 cp .env.example .env 然后编辑填入 API key"
else
    echo "  ✓ .env 存在"
    found_key=""
    for key in DEEPSEEK_API_KEY OPENAI_API_KEY ANTHROPIC_API_KEY; do
        # 用 grep 而不是 source，避免 .env 里有奇怪字符导致 shell 出问题
        value_line=$(grep -E "^${key}=" .env 2>/dev/null | head -1)
        if [ -n "$value_line" ]; then
            value=$(echo "$value_line" | sed -E "s/^${key}=//; s/^['\"]//; s/['\"]$//; s/^[[:space:]]+//; s/[[:space:]]+$//")
            if [ -n "$value" ] && [ "$value" != "sk-xxxxxxxxxxxx" ] && [ "$value" != "sk-ant-xxxxxxxxxxxx" ]; then
                echo "  ✓ $key 已填（长度 ${#value} 字符，开头 ${value:0:5}...）"
                found_key="$key"
            fi
        fi
    done
    if [ -z "$found_key" ]; then
        echo "  ✗ 三个 *_API_KEY 都没填。至少填一个（推荐 DEEPSEEK_API_KEY）"
        echo "    DeepSeek 申请链接：https://platform.deepseek.com/api_keys"
    fi
fi

echo ""
echo "=== 里程碑 4：简历 PDF ==="
resume_path="${RESUME_PATH:-resume/my_cover.pdf}"
if [ -f "$resume_path" ]; then
    size=$(stat -f%z "$resume_path" 2>/dev/null || stat -c%s "$resume_path" 2>/dev/null || echo 0)
    if [ "$size" -gt 1000 ]; then
        # 验证是 PDF
        if head -c 4 "$resume_path" | grep -q "%PDF"; then
            echo "  ✓ 简历存在: $resume_path ($((size / 1024)) KB)"
        else
            echo "  ✗ $resume_path 存在但不是 PDF 格式（不是以 %PDF 开头）"
            echo "    需要 PDF 简历，Word 文档要先导出 PDF"
        fi
    else
        echo "  ✗ $resume_path 太小（$size bytes），可能是空文件"
    fi
else
    echo "  ✗ 简历文件不存在: $resume_path"
    echo "    mkdir -p resume 然后把 PDF 放进去命名 my_cover.pdf"
    echo "    或者在 .env 里设 RESUME_PATH=/your/path/to.pdf"
fi

echo ""
echo "=== 里程碑 5：Chrome profile（首次扫码） ==="
profile_dir="${BOSS_CHROME_PROFILE:-./chrome_profile}"
if [ -d "$profile_dir" ]; then
    if [ -f "$profile_dir/Default/Cookies" ]; then
        cookie_size=$(stat -f%z "$profile_dir/Default/Cookies" 2>/dev/null || stat -c%s "$profile_dir/Default/Cookies" 2>/dev/null || echo 0)
        if [ "$cookie_size" -gt 4096 ]; then
            echo "  ✓ chrome_profile/Default/Cookies 存在 ($((cookie_size / 1024)) KB)"
            # 检查 zhipin 关键 cookie
            if command -v sqlite3 >/dev/null 2>&1; then
                zhipin_cookies=$(sqlite3 "$profile_dir/Default/Cookies" \
                    "SELECT COUNT(*) FROM cookies WHERE host_key LIKE '%zhipin%';" 2>/dev/null || echo "?")
                echo "  ℹ zhipin 相关 cookie 数：$zhipin_cookies"
                if [ "$zhipin_cookies" -gt 0 ] && [ "$zhipin_cookies" != "?" ]; then
                    auth_cookies=$(sqlite3 "$profile_dir/Default/Cookies" \
                        "SELECT name FROM cookies WHERE host_key LIKE '%zhipin%' AND (name='wt2' OR name='bex' OR name LIKE '%token%' OR name LIKE '%stoken%');" 2>/dev/null)
                    if [ -n "$auth_cookies" ]; then
                        echo "  ✓ 检测到登录态 cookie，应该跳过扫码"
                    else
                        echo "  ⚠ 只有跟踪 cookie，没有登录态 —— 第一次跑时要扫码"
                    fi
                fi
            fi
        else
            echo "  ⚠ Cookies 文件存在但很小，profile 可能没真正用过"
        fi
    else
        echo "  ⚠ chrome_profile 存在但 Default/Cookies 不存在 —— 跑过但没登录成功？"
    fi
else
    echo "  ✗ chrome_profile 不存在 —— 还没跑过 main.py"
fi

echo ""
echo "=== 推荐下一步 ==="
if [ ! -d ".venv" ]; then
    echo "  → 跑 uv sync"
elif [ ! -f ".env" ]; then
    echo "  → 跑 cp .env.example .env 然后编辑填 DEEPSEEK_API_KEY"
elif ! grep -E "^DEEPSEEK_API_KEY=.+|^OPENAI_API_KEY=.+|^ANTHROPIC_API_KEY=.+" .env 2>/dev/null | grep -qv "xxxxxxx"; then
    echo "  → 编辑 .env 填一个真实的 API key"
elif [ ! -f "${RESUME_PATH:-resume/my_cover.pdf}" ]; then
    echo "  → mkdir -p resume 把 PDF 简历放进去命名 my_cover.pdf"
elif [ ! -d "${BOSS_CHROME_PROFILE:-./chrome_profile}" ]; then
    echo "  → 第一次跑！DRY_RUN=1 uv run main.py，准备好微信扫码"
else
    echo "  → 看起来全部 ready 了，直接 DRY_RUN=1 uv run main.py 跑就行"
fi
