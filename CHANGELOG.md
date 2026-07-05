## 2026-07-05 17:00 - 精简推荐 feed 滚动加载修复

### 变更内容
- 修改 `src/boss_zhipin/website_oper/finding_jobs.py`，`scroll_to_load_more_jobs` 在找不到左侧可滚动岗位容器时改为滚动整个页面到底部，等待 feed 懒加载追加岗位卡。
- 修改 `src/boss_zhipin/website_oper/write_response.py`，超出当前可见岗位卡数量时先尝试加载更多岗位卡，并在虚拟列表场景使用可见岗位索引继续扫描。
- 修改 `tests/conftest.py`、`tests/test_finding_jobs_text.py`，补充 feed 滚动、window 滚动成功/失败和相关环境变量清理测试。
- 新增 `tests/test_write_response_flow.py`，覆盖滚动后重试、发送后返回列表、发送上限和随机等待。

### 原因
真实页面 `https://www.zhipin.com/web/geek/jobs?jobType=1902&experience=108` 没有独立可滚动的左侧列表，也没有翻页控件；它通过页面整体滚到底部触发 feed 懒加载。真实验证中岗位卡可从 30 张增加到 45 张。

### 影响范围
影响岗位 feed 加载更多、扫描索引推进、发送后返回列表和发送节流；不改变岗位筛选规则和招呼语生成逻辑。window 滚动只有在岗位卡数量增加时才算成功，避免误判。
