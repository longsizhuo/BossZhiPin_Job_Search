"""招呼语 prompt 模板。

默认模板刻意追求"像真人在 BOSS 直聘上随手发的打招呼"——口语、简短、去套话，
而不是 AI 公文腔（"招聘负责人您好 / 深感契合 / 期待贡献力量 / 真诚的，X"那种一眼
就是代写、招聘者反感）。

**可配置**：用户能在 GUI 配置页（或 ``.env`` 的 ``BOSS_LETTER_PROMPT``）整段覆盖
这个 system prompt；自定义模板里用 ``{usr_name}`` 占位求职者名字（唯一占位符）。
"""
from __future__ import annotations

import os

LETTER_PROMPT_ENV = "BOSS_LETTER_PROMPT"

# 默认 prompt。改这里 = 改所有"没自定义 prompt"的用户的默认风格。
DEFAULT_LETTER_PROMPT = """\
你在帮一位求职者，根据他的简历和某个岗位描述，写一条在 BOSS 直聘上**主动打招呼**的开场消息。

务必遵守：
1. 写得像**真人随手发的微信式打招呼**：口语、自然、简短——控制在 80~150 个中文字，最多别超过 200 字。招聘者一眼扫过，太长没人看。
2. 只挑**1~2 个跟这个岗位最相关**的点说（结合简历里的真实经历/技能 + 岗位描述），具体、有信息量，别堆形容词。
3. **不要**任何套话和 AI 腔：禁止"招聘负责人您好""深感契合""贵公司/贵司""期待进一步沟通""为……贡献力量""我的优势如下：1.…2.…"这种排比清单，也不要"真诚的，{usr_name}"之类的署名落款。
4. 开头自然点，比如"你好，我是{usr_name}，"或直接说看到了什么岗位；结尾可以是一句自然的"方便聊一下吗 / 想了解下这个岗位"。
5. 全程中文；不要放微信/电话等联系方式（平台不允许）。
6. **只输出这条招呼语正文**，不要任何解释、前言、引号、或"以下是为您生成的…"这类话，方便直接复制发送。
"""


def assistant_instructions(usr_name) -> str:
    """返回招呼语 system prompt。

    优先用环境变量 ``BOSS_LETTER_PROMPT``（GUI 配置页可填）的自定义模板，留空则用
    ``DEFAULT_LETTER_PROMPT``。``{usr_name}`` 是唯一占位符，做**字面替换**而非
    ``str.format``——避免用户模板里写了 JSON 大括号之类导致 format 崩。
    """
    template = (os.getenv(LETTER_PROMPT_ENV) or "").strip() or DEFAULT_LETTER_PROMPT
    return template.replace("{usr_name}", str(usr_name))
