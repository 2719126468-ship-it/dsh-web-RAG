# 私人 AI 知识库问答系统

这是一个让你用自己的笔记、合同、邮件等文档，搭建一个私人 AI 助手的项目。

它能做什么：问它"我和蓝海科技签的合同金额是多少？"，它会自动从你电脑里的合同文档里找到答案，并告诉你具体是哪一页、哪一段。


## 什么是 RAG？为什么要用它？

RAG 是 Retrieval-Augmented Generation 的缩写，翻译过来就是"检索增强生成"。

先解释三个词：

- 检索（Retrieval）：从一个文档库里找到和问题相关的内容
- 增强（Augmented）：把找到的内容补充给 AI
- 生成（Generation）：AI 看着这些内容，整理出一段回答

为什么要这么做？

因为现在的 AI（比如 ChatGPT、文心一言）有两个问题：

1. 它不知道你电脑里的私人文件。你公司的合同、你的笔记，它没看过
2. 在特定场景下（比如被要求"必须回答"时），它可能会编造不存在的细节

RAG 的解决方案很简单：你问问题时，先从你电脑里找出相关段落，把这些段落和问题一起发给 AI。AI 被要求"只能根据这些段落回答"，所以它就不会瞎编了。

打个比方：

- 普通 AI 像一个记忆不好的朋友，你问它问题，如果它不知道，会说"我不清楚"；但如果被逼问，可能随口编一个
- RAG 像一个"开卷考试"：你把相关的书页翻到它面前，它只能从这些书页里挑答案


## 这个项目能做什么

1. 把你的 .md / .txt / .pdf / .docx 文档读进来
2. 自动给每篇文档建立"索引"（一种加速查找的目录）
3. 你问问题时，自动找出最相关的 5 段
4. 把这 5 段连同问题一起发给大语言模型（比如 DeepSeek）
5. AI 基于这些段落给你回答，并标出引用来源

核心特性：

- 增量索引：你修改一个文件后，程序只需要几秒就能更新这个文件，不用全部重建
- 混合检索：同时用"关键词匹配"（BM25）和"语义理解"（向量）两种方式找内容，通过 RRF（倒数排名融合）合并结果，比单一方式更准
- 引用溯源：每个回答都告诉你"这段话来自哪个文件、哪一节"
- 自动评估：内置测试集，能量化"这个系统准不准"


## 项目文件结构
rag-private-docs/
├── docs/ 你的文档放这里
│ ├── 01-rag-intro.md 示例：什么是 RAG
│ ├── 02-langchain-notes.md
│ ├── 03-deepseek-api.md
│ ├── 04-contract-2024-0312.md 示例：合同
│ ├── 05-weekend-hike-moganshan.md 示例：笔记
│ └── 06-email-client-dec-launch.md 示例：邮件
├── src/ 程序源代码
│ ├── config.py 配置文件
│ ├── indexer.py 索引器（把文档变成可搜索的格式）
│ ├── retriever.py 检索器（找到相关段落）
│ ├── outline.py 提取文档目录
│ ├── qa.py 问答主程序
│ ├── evaluator.py 自动评估
│ ├── watcher.py 文件变化监听（可选）
│ ├── notion_sync.py Notion 同步（可选）
│ └── app.py 网页界面
├── example_lessons/ 5 个小教程，循序渐进
│ ├── 01_hello_llm.py
│ ├── 02_embeddings.py
│ ├── 03_vector_search.py
│ ├── 04_mini_rag.py
│ └── 05_evaluate.py
├── eval/ 自定义测试集（可选，按需创建）
│ └── test_set.json 你的测试问题（格式见"进阶功能"章节）
├── qdrant_data/ 向量数据库（程序自动生成，不要手动修改）
├── .env.example 环境变量模板（复制成 .env 后填 Key）
├── .env 你的实际配置（需自行创建，不要提交到 Git）
├── .gitignore 忽略 .env、qdrant_data/、pycache/ 等
├── TUTORIAL.md 详细教程（手把手）
├── README.md 你正在看的这个文件
└── requirements.txt 依赖库清单


## 怎么用起来

### 第一步：准备 Python 环境

Python 是一种编程语言。我们这个项目是用 Python 写的。你需要先在电脑上装 Python 3.11 或更高版本。

**Windows 用户**：去 python.org 下载安装包。安装时第一屏底部有一个 "Add Python to PATH" 选项。**建议勾选**，这样后续可以直接用 `python` 命令。安装完成后，打开命令提示符（CMD）或 PowerShell，输入：

python --version

如果显示 `Python 3.11.x` 或更高，就 OK。如果提示找不到，尝试用 `py --version`。如果 `py` 也不行，说明安装时没勾选 PATH，请重新运行安装包，勾选 "Add to PATH" 后再试。

**Mac / Linux 用户**：一般系统自带 Python，但建议装个新版本。Mac 可用 Homebrew：`brew install python@3.11`。Ubuntu/Debian：`sudo apt install python3.11 python3.11-venv`。然后验证：

python3 --version

### 第二步：拿到 DeepSeek 的 API Key

DeepSeek 是国内的一个大语言模型公司，API Key 就像一把钥匙，证明你有权限使用它的服务。

1. 去 https://platform.deepseek.com 注册账号（用手机号即可）
2. 登录后点左侧 "API Keys"
3. 点 "Create new key"，起个名字（如 `my-rag`）
4. **⚠️ 重要**：DeepSeek 的安全策略是——密钥**仅在创建时完整显示一次**，关闭弹窗后就无法再查看。**请务必立即复制并保存到安全的地方**（如密码管理器）。如果忘记保存，只能删除后重新创建。
5. 复制下来的 key 格式类似 `sk-xxxxxxxxxxxxxxxxxxxxxxxx`

### 第三步：下载项目代码

如果装了 git：

git clone https://github.com/你的用户名/rag-private-docs.git
cd rag-private-docs

如果没装 git，直接从 GitHub 页面下载 ZIP 包，解压后进入该目录。

### 第四步：创建虚拟环境

虚拟环境是把项目依赖隔离在独立文件夹里，避免污染系统 Python。

在项目根目录下运行：

# Windows CMD / PowerShell 通用
py -3.11 -m venv .venv

# Mac / Linux
python3 -m venv .venv

激活虚拟环境：

系统 / Shell：激活命令
Windows CMD：.venv\Scripts\activate.bat
Windows PowerShell：.venv\Scripts\Activate.ps1（见下方备注）
Mac / Linux (bash/zsh)：source .venv/bin/activate

> **PowerShell 用户注意**：如果提示 "无法加载文件，因为在此系统上禁止运行脚本"，先以管理员身份运行 PowerShell，执行：
> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
> 输入 `Y` 确认，然后重新激活。

激活成功后，终端前面会出现 `(.venv)` 字样。

### 第五步：安装依赖

依赖清单在 `requirements.txt` 里。使用 pip 一次性安装：

# 如果下载慢，用清华镜像（推荐）
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

# 或者不用镜像（可能较慢）
pip install -r requirements.txt

> **Windows 潜在问题**：部分依赖（如 `unstructured`）在安装时可能需要编译 C++ 扩展。如果报错，请先安装 [Microsoft C++ Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/)（勾选 "C++ 生成工具"）。或者，如果你不需要解析 PDF/Word，可以手动注释掉 `requirements.txt` 中的 `unstructured`、`pypdf`、`docx2txt`，仅保留核心库。

### 第六步：配置 API Key

复制环境变量模板：

系统 / Shell：命令
Windows CMD：copy .env.example .env
Windows PowerShell：cp .env.example .env
Mac / Linux / Git Bash：cp .env.example .env

然后用记事本（Windows）或 VS Code 等编辑器打开 `.env` 文件，填入你的 DeepSeek API Key：

DEEPSEEK_API_KEY=sk-你的key
DEEPSEEK_MODEL=deepseek-chat
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1

保存。

> **安全提示**：`.env` 包含敏感信息，**不要提交到 Git**。项目根目录的 `.gitignore` 已经默认忽略了 `.env`，可放心。

### 第七步：建立索引

首次运行会下载 BGE 嵌入模型（`bge-small-zh-v1.5`，FP32 版本约 91MB）。**如果下载很慢，请先设置 HuggingFace 镜像**：

系统 / Shell：命令
Windows CMD：set HF_ENDPOINT=https://hf-mirror.com
Windows PowerShell：$env:HF_ENDPOINT="https://hf-mirror.com"
Mac / Linux：export HF_ENDPOINT=https://hf-mirror.com

然后进入 `src` 目录执行索引：

cd src
python indexer.py --force

你会看到类似输出：

[info] Files: 6 total, 6 changed, 0 deleted
[done] total_files: 6, new_or_changed: 6, chunks_added: 12, elapsed_seconds: 1.5

> `--force` 表示强制重建所有索引。日常增量更新时，不加 `--force`，程序会自动检测变化的文件。

### 第八步：启动网页界面

streamlit run app.py

浏览器会自动打开 http://localhost:8501 。如果没自动打开，手动访问该地址。


## 日常怎么用

往 `docs/` 文件夹里丢新文档（合同、笔记、PDF、Word 都行），然后运行：

cd src
python indexer.py

程序会智能地只处理"有变化"的文件。比如你改了 `01-rag-intro.md`，它就只重新索引这一个文件，几秒就好。

想自动监听文件变化？跑：

python src/watcher.py

之后你改任何文档，它会自动重新索引，不用手动。


## 怎么知道系统准不准？

cd src
python evaluator.py

会输出一张表格，例如：

问题数: 8
hit_at_1  = 1.0    每个问题的 Top-1 检索结果都命中了预设关键词
context_precision = 0.825  返回的段落中真正相关的比例
context_recall    = 1.0    应该召回的相关段落全被找回来了

**指标含义**：
- **hit_at_1**：对每个问题，取检索结果的第一段，检查它是否包含预设的"正确答案关键词"。如果包含，该问题计 1 分。最终得分 = 命中数 / 总问题数。1.0 表示完美。
- **context_precision**：返回的所有段落里，真正相关的比例（精度）。
- **context_recall**：所有应该被找到的相关段落中，实际被召回的比例（召回率）。

调参方向见 `src/config.py`：
- `CHUNK_SIZE`（默认 500）：每段字符数。调大则上下文更全但检索变粗；调小则检索更精但上下文可能不足。
- `CHUNK_OVERLAP`（默认 80）：相邻段重叠字符数，避免切断关键信息。
- `TOP_K`（默认 5）：返回给 AI 的段落数。调大则覆盖更全但噪声增多；调小则更精准但可能漏内容。


## 它的工作原理（简化版）

### 索引阶段：把文档变成可搜索

原文档（md、txt、pdf、docx） → 切成小段（每段约 500 字符，相邻段重叠 80） → 每段转成一个 512 维的数字向量（用 BGE-small-zh 模型） → 存入向量数据库（Qdrant）

为什么切成小段？因为整篇文档太长，AI 无法一次处理，而且用户的问题通常只对应文档的一小部分。

为什么转成向量？因为向量可以做相似度计算。比如"天气真好"和"阳光明媚"意思相近，它们的向量距离就很近；而和"合同金额"距离就远。

### 检索阶段：找到相关段落

用户提问 → 同样转成向量 → 同时进行两种检索：
1. **向量检索**：在向量库里找最相似的段落
2. **关键词检索**（BM25）：用关键词匹配找段落
→ 两种结果通过 **RRF（倒数排名融合）** 合并，取 Top_K 返回

混合检索比单一检索准：纯向量检索对"语义相近"很敏感，但对"明确关键词"（比如合同编号、人名）容易漏；纯关键词检索反过来。RRF 不依赖分数尺度，只根据排名融合，稳定且无需调权重。

### 回答阶段：AI 基于内容生成

系统把找到的 K 段 + 用户的提问 + 一个严格的 prompt（指令），一起发给 DeepSeek。

prompt 明确告诉 AI："你只能根据这些段落回答，不能瞎编。引用事实时标注 [1][2] 这样的角标。"

AI 返回答案时，每个事实都标了来源，你可以点击展开看到原文。


## 进阶功能

### 切换大语言模型

编辑 `src/qa.py`，把 `ChatOpenAI(...)` 换成你想用的模型，比如通义千问、文心一言，或者本地的 Ollama（需修改 base_url）。

### 自定义测试集

在 `eval/` 目录下新建 `test_set.json`，格式：

[
  {
    "question": "你的问题",
    "ground_truth_keywords": ["关键词1", "关键词2"],
    "must_cite": "文件名.md"
  }
]

然后跑 `python evaluator.py`，它会自动用你的测试集评估。

### Notion 同步

如果你用 Notion 管理笔记，可以把 Notion 页面自动转成 markdown 存到 `docs/notion/`，然后被本系统索引。

详见 `src/notion_sync.py` 的注释。

## 升级日志（v6）

v6 解决了两个长期被忽略的问题：

1. **指标测量 bug**：parent-child 架构下，evaluator 检查的是 child chunk（200 字符），但 LLM 实际看到的是 parent（1500 字符）。修复：让 `context_precision` 和 `context_recall` 用 parent_text 算。
2. **测试集关键词错误**：测试集写的 "top-1" 但 PDF 实际是 "op-1"（连字符+换行截断）。修复：把 ground_truth_keywords 改为 "op-1"。

效果：

- hit@1: 1.0（保持）
- context_precision: 0.65 → 0.9（+38%）
- context_recall: 0.951 → 1.0（完美）

## 升级日志（v7 最新）

v7 发现了三个关键 bug 并修复，retriever 池现在干净了：

1. **Index 累积 bug（最严重）**：`indexer.py --force` 之前用 `delete_collection` 看起来成功，但 Windows + SQLite WAL 模式下旧数据没真正删掉。重复 reindex 后旧向量累积（实测：跑 5 次累积到 220 个点）。修复：force 模式下 `shutil.rmtree(QDRANT_PATH)` 整个目录删掉，再创建空 client。
2. **Per-source BM25 归一化**：`retriever.py _bm25_search` 现在按 source 做归一化（每个 source 最高得 1.0），防止长文档（多 token）压制短文档（少 token）。
3. **Confidence 混合公式**：`retriever.py retrieve` 的 confidence 从纯 sigmoid(rerank_score) 改为 `0.8 * rerank + 0.2 * rrf`，让 reranker 主导同时保留 RRF 的文档级信号。
4. **PDF metadata 保留**：`parent_child_splitter.py` 现在保留 `chunk_role=pdf_metadata` 的文档，不再走 parent-child 切分（真实 PDF 有 Title/Author 时会生效）。
5. **诊断脚本**：`src/diagnostic.py` 新建 6 项快速健康检查（Qdrant 集合大小、BM25、Dense、Hybrid、Reranker、Mini-evaluator），能自动检测出索引累积类问题。

效果：

| 指标 | v6 | v7（真实） |
|---|---|---|
| hit@1 | 1.0 | 1.0 |
| context_precision | 0.9 | 0.9 |
| context_recall | 1.0 | 1.0 |
| Qdrant 集合点 | 未知 | 44（干净）|

注意：v6 测试时 Qdrant 集合已经有 88-220 个点（含重复），context_precision 1.0 是污染数据下的假象。v7 真正清干净后是 0.9，这是真实性能。如果以后想保持集合干净（44 点），按下面的 v8 经验跑 `indexer.py --force`。

## 常见问题

**Q：装依赖时报网络超时**

A：用国内镜像：
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

**Q：BGE 模型下载很慢**

A：设置环境变量走镜像（见"怎么用起来"第七步），然后重新运行 `indexer.py`。

**Q：回答不准确**

A：分两种情况。
- 引用片段根本不对 → 检索问题。试着在 `config.py` 调大 `TOP_K` 到 8 或 10，然后运行 `evaluator.py` 看 Top-20 里有没有更相关的段落。
- 引用片段对，但 AI 还是瞎编 → prompt 不够强。参考 `src/qa.py` 里的 `STRICT_SYSTEM_PROMPT`，把规则改得更严（如"严禁添加任何未提及的信息"）。

**Q：检索不到内容**

A：先确认文档是否已被索引。运行 `python indexer.py` 看输出，确认 `docs/` 目录下的文件是否被扫描到。

**Q：Streamlit 启动报错**

A：删除用户目录下的 `.streamlit` 缓存文件夹（`C:\Users\你的用户名\.streamlit` 或 `~/.streamlit`）。

**Q：Windows 报 "qdrant_data already accessed"**

A：Qdrant 数据库文件被锁了。重启 Python 进程，或删除 `qdrant_data/.lock` 文件（如果存在）。

**Q：想支持 .doc 或 .pptx 文件**

A：本系统暂不支持。如需扩展，可参考 `unstructured` 库的 `partition` 接口自行修改 `indexer.py`。


## 推荐学习路径

如果你刚接触 AI 编程，建议按这个顺序看：

1. 先看 `TUTORIAL.md` 的"第 0 节"（环境准备）
2. 跑 `example_lessons/01` 到 `04`（30 分钟体验 4 个核心概念）
3. 把项目跑起来（30 分钟）
4. 看 `TUTORIAL.md` 的"第 3 节"（调参与优化）
5. 看 `TUTORIAL.md` 的"第 4 节"（进阶功能）

如果你是开发者，建议直接看 `TUTORIAL.md` 全文，再看 `src/` 下的代码注释。


## 进一步学习

推荐资料：

- RAG 综述论文：arxiv.org/abs/2312.10997 （用翻译工具读）
- LangChain 官方文档：python.langchain.com
- DeepSeek 使用文档：platform.deepseek.com/docs

可以接着改造的方向：

- 多模态：让系统能读图片、PDF 里的图表
- GraphRAG：用知识图谱替代向量检索
- 多用户：让系统支持多个账号，各自看各自的文档


## 协议

MIT 协议，可以自由使用、修改、商用。
