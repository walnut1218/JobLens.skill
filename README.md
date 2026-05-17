# 👔 基于BOSS直聘的求职助手

> **搜到岗位只是第一步**——重要的是你看完就知道：这个岗位到底需要什么能力、你的差距在哪、作品集该做什么。  
> 自动采集 + 结构化分析 + 简历匹配度评分 + 作品集建议，输出 Word 报告。
## 🤔 为什么需要这个工具？

在海量 JD 里翻来翻去，最消耗时间的不是“找岗位”，而是**搞清楚这个岗位到底要什么能力、我和它差在哪里、简历里要该补什么项目/作品**。

JobSnap 帮你把这三件事自动化：  
1. 输入想要搜索的岗位后（比如杭州产品经理），它帮你自动搜索并去重  
2. 上传简历后（也可以不上传简历，只是报告里会没有简历评分这个功能，其他不受影响），每个岗位 7 维度 0-100 分打分排序  
3. 针对岗位要求直接给出作品集建议和面试准备方向  
---

## 📌 功能

| 功能 | 说明 |
|------|------|
| 🔍 岗位搜索 | 按关键词 + 城市搜索，支持薪资/学历/经验/行业/融资阶段等筛选 |
| 🧹 自动去重 | 记住已看过的岗位 ID，跨天不重复分析 |
| 📊 简历匹配度评分 | 上传简历后，7 维度（0-100 分）自动打分排序 |
| 📝 结构化分析 | 每条岗位含：核心要求、技能清单、作品集建议、面试准备方向 |
| 📄 Word 报告 | 一键生成排版好的 .docx，带链接可直达 BOSS 直聘原文 |
| 📅 每日自动推送 | 每天 9:00 自动检查新岗位，有增量直接出报告 |
| 🔄 多轮搜索 | 换城市、换关键词、加筛选项，随时重新搜 |

---

## 🚀 快速开始
### 方法一
直接拖进claw里，它会自动帮你安装

### 方法二
### 环境要求

- Python 3.10+
- [uv](https://docs.astral.sh/uv/)（包管理器）

### 安装

```bash
# 1. 安装依赖
uv sync

# 2. 安装浏览器（登录和爬虫需要）
uv sync --extra playwright
uv run patchright install chromium
```

### 登录

```bash
uv run zhipin-search login -o ./token.json
```

自动打开浏览器窗口，用 BOSS 直聘 App 扫码即可。  
登录凭证写入 `token.json`，后续使用无需重新登录（有效期一般 1-7 天）。

---

## 🔧 使用
### claw方式
拖进claw之后，根据它的提示一步步交互即可（也就是跟他聊天）

### 命令行方式

```bash
# 基本搜索
uv run python scripts/scrape_all.py --keyword "用户研究实习生" --city 上海 --pages 3

# 加筛选条件
uv run python scripts/scrape_all.py --keyword "用户研究" --city 杭州 --pages 2 \
  --education 硕士 --salary "10-20K" --industry 互联网

# 每日检查（自动去重）
uv run python scripts/push_daily.py --city 上海 --keyword "用户研究实习生" --pages 2

# 生成报告（需先有 jobs_data.json）
uv run python scripts/generate_report.py --city 上海 --keyword "用户研究实习生"
```

### 筛选参数

| 参数 | 说明 | 可选值 |
|------|------|--------|
| `--keyword` | 搜索关键词 | 任意 |
| `--city` | 城市 | 上海/北京/杭州/广州/深圳/成都/武汉 等 40+ |
| `--pages` | 页数（每页约 15 条） | 1-10 |
| `--salary` | 薪资范围 | 3K以下/3-5K/5-10K/10-20K/20-50K/50K以上 |
| `--experience` | 经验要求 | 应届/1年以内/1-3年/3-5年/5-10年/10年以上 |
| `--education` | 学历要求 | 大专/本科/硕士/博士 |
| `--industry` | 行业 | 互联网/游戏/人工智能/金融/教育/医疗 等 25+ |
| `--stage` | 融资阶段 | 未融资/天使轮/A轮/B轮/C轮/已上市 等 8 种 |
| `--scale` | 公司规模 | 0-20人/20-99人/100-499人/500-999人/1000-9999人/10000人以上 |

### PowerShell 便捷脚本

```powershell
.\run.ps1 scripts/scrape_all.py --keyword "用户研究" --city 上海 --pages 3
```

---

## 📂 项目结构

```
boss-job-analyzer/
├── SKILL.md                          # AI Skill 定义（对话式操作入口）
├── package.json                      # Skill 元数据
├── pyproject.toml                    # 项目依赖
├── uv.lock                           # 依赖锁文件
├── .gitignore
│
├── boss_zhipin_job_search/           # 核心库
│   ├── __main__.py                   # CLI 入口
│   ├── app.py                        # 搜索逻辑
│   ├── auth_browser.py               # 浏览器登录
│   ├── auth_cookie.py                # Cookie 读取
│   └── login_cmd.py                  # 登录子命令
│
├── scripts/
│   ├── scrape_all.py                 # ⭐ 主爬虫脚本
│   ├── push_daily.py                 # ⭐ 每日自动推送
│   ├── generate_report.py            # ⭐ Word 报告生成
│   ├── _dedup.py                     # 去重模块（seen_jobs.txt）
│   ├── _resume_matcher.py            # 简历匹配度评分（7 维打分）
│   ├── _token_utils.py              # Token 校验工具
│   └── _analyze.py                   # 基础分析工具
│
├── references/
│   └── analysis_prompt.md            # 分析提示词模板
│
└── run.ps1                           # PowerShell 启动包装器
```

---

## 📊 简历匹配度评分

上传简历后，每个岗位按以下维度自动打分：

| 维度 | 分值 | 说明 |
|------|------|------|
| 岗位名称匹配 | ±20分 | 是否含目标岗位关键词（用研/UX/产品等） |
| 学历匹配 | 10分 | 简历学历 vs 岗位要求 |
| 经验匹配 | 10分 | 简历经验 vs 岗位要求 |
| 技能匹配 | 25分 | JD 中出现的 Python/SPSS/NLP/爬虫 等技能与简历交集 |
| 研究方向匹配 | 15分 | 研究方向（社交媒体、用户行为等）与 JD 重合度 |
| 行业匹配 | 10分 | 熟悉行业 vs 岗位所在行业 |
| 反相关扣分 | -10分 | 非目标方向（开发/销售/运营等）直接扣分 |

总分 **0-100**，≥60 分为高匹配，自动排序前置。

---

## 📄 报告示例

生成的 Word 报告包含：

1. **整体总结**（职位 >10 条时）：行业分布、高频能力 TOP5、作品集方向建议、求职策略
2. **逐条分析**：每条岗位含岗位链接、JD 原文、核心要求、技能清单、作品集建议、面试准备方向
3. **如有简历**：匹配度评分 + 匹配分析（✅匹配点 / ❌不匹配点 / 📝修改建议）

---

## 🔄 自动去重

`seen_jobs.txt` 记录所有已见岗位的 `encryptJobId`，跨天累积。

- 新岗位 → 保留并分析
- 已见过的 → 跳过，不重复输出
- 支持多城市/多关键词独立跟踪

---

## ⚙️ 技术栈

- **httpx** — 异步 HTTP 请求
- **patchright** — 浏览器自动化（防风控）
- **python-docx** — Word 文档生成
- **re** — 正则解析与匹配度计算

---

## ⚠️ 注意事项

- **登录凭证安全**：`token.json` 包含 BOSS 直聘 cookie，不要提交到公开仓库（已加入 `.gitignore`）
- **请求频率**：默认 1.5-3 秒随机间隔，过快触发风控会返回 code 37/36
- **搜索注意**：建议每次至多就爬5页，否则可能会触发反制机制
- **合规**：本工具用于个人求职辅助，请遵守 BOSS 直聘用户协议
- **风控说明**：headless 模式下可能被风控拦截，真实浏览器（`headless=False`）更稳定
  
## 🙏 鸣谢

本项目的爬虫登录与请求模块部分借鉴了 [boss-agent-cli](https://github.com/can4hou6joeng4/boss-agent-cli) 的实现思路，感谢 [can4hou6joeng4](https://github.com/can4hou6joeng4) 的开源贡献。
---

## 📝 License

MIT
