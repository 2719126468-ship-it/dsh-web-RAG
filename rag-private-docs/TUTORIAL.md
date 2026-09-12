# 手把手教程：从零搭建你的私人 AI 知识库

这份教程会带你从"电脑里只有 Python"开始，到"拥有一个能回答你私人问题的 AI 助手"为止。

整个过程大约 2-3 小时。


## 教程结构

- 第 0 节：环境准备（15-20 分钟）—— 装 Python、装依赖
- 第 1 节：4 个迷你实验（30 分钟）—— 建立直觉
- 第 2 节：跑通完整系统（30 分钟）—— 用真实数据
- 第 3 节：调参与优化（30 分钟）—— 让它更准
- 第 4 节：进阶功能（60 分钟）—— 多轮对话、文件监听等
- 第 5 节：部署上线（60 分钟）—— 让别人也能用

如果你赶时间，只看第 0-2 节也能跑起来。


## 第 0 节：环境准备

### 0.1 装 Python

Python 是一种编程语言。我们的项目是用 Python 写的。

去 https://www.python.org/downloads/ 下载 3.11 或更高版本（建议 3.11.x，3.12 也兼容）。

**Windows 用户注意**：
- 安装时，第一屏底部有一个 **"Add Python to PATH"** 选项。**建议勾选**，这样后续可以直接用 `python` 命令。
- 安装完成后，打开**命令提示符（CMD）** 或 **PowerShell**，输入：
  python --version
  如果显示 `Python 3.11.x`，说明 OK。如果提示"找不到"，尝试用 `py --version`。如果 `py` 也不行，说明安装时没勾选 PATH，请重新运行安装包，勾选 "Add to PATH"。

**Mac 用户**：
- 系统自带 Python 2.7（已废弃），需自行安装 Python 3。
- 推荐用 Homebrew：先装 Homebrew（/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"），然后 brew install python@3.11。
- 验证：python3 --version。

**Linux 用户（Ubuntu/Debian）**：
sudo apt update
sudo apt install python3.11 python3.11-venv python3.11-dev
验证：python3.11 --version。

### 0.2 装 git（可选，推荐）

Git 是一种版本控制工具，用来下载代码。

- Windows：去 https://git-scm.com/download/win 下载安装（安装时一路默认即可，建议勾选 "Git from the command line"）
- Mac：brew install git 或去官网下载
- Ubuntu/Debian：sudo apt install git

如果不装 git，也可以直接从 GitHub 网页下载 ZIP 包。

### 0.3 拿到 DeepSeek API Key

API Key 是你调用 DeepSeek 服务的凭证。

1. 去 https://platform.deepseek.com 注册账号
2. 登录后点左侧 "API Keys"
3. 点 "Create new key"，起名（如 rag-demo）
4. **⚠️ 重要警告**：DeepSeek 的密钥**仅在创建时完整显示一次**，关闭弹窗后就再也看不到了。**请务必立刻复制并粘贴到安全的地方**（比如密码管理器或本地记事本）。
5. 格式类似 sk-xxxxxxxxxxxxxxxxxxxxxxxx。

如果遗失，无法找回，只能删除旧 key 重新创建。

### 0.4 下载项目代码

用 git：

git clone https://github.com/你的用户名/rag-private-docs.git
cd rag-private-docs

或下载 ZIP 解压后进入该目录。

### 0.5 创建虚拟环境

虚拟环境让项目依赖与系统隔离，避免冲突。

在项目根目录下执行：

# Windows CMD / PowerShell（推荐用 py 命令）
py -3.11 -m venv .venv

# Mac / Linux
python3 -m venv .venv

激活虚拟环境：

| 系统 | 命令 |
|------|------|
| Windows CMD | .venv\Scripts\activate.bat |
| Windows PowerShell | .venv\Scripts\Activate.ps1（见下方备注） |
| Mac / Linux | source .venv/bin/activate |

> **PowerShell 激活报错处理**：若提示"禁止运行脚本"，先以**管理员身份**运行 PowerShell，执行 Set-ExecutionPolicy RemoteSigned -Scope CurrentUser，输入 Y，再重新激活。

激活后，终端前缀出现 (.venv) 即成功。

### 0.6 装依赖

requirements.txt 里列出了所有需要的库。使用 pip 安装：

# 用清华镜像加速（强烈推荐）
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

# 如果不用镜像（可能很慢，甚至超时）
pip install -r requirements.txt

**Windows 用户特别提醒**：unstructured 库在安装时可能需要 C++ 编译器来编译某些依赖。如果遇到 error: Microsoft Visual C++ 14.0 is required：
1. 下载安装 Microsoft C++ Build Tools（https://visualstudio.microsoft.com/visual-cpp-build-tools/）
2. 安装时勾选 "C++ 生成工具" 和 "Windows 10 SDK"
3. 重新运行 pip install

如果你不需要解析 PDF 或 Word，可以手动编辑 requirements.txt，删除 unstructured、pypdf、docx2txt 这三行，只安装核心库，这样无需 C++ 编译器。

### 0.7 配置 API Key

复制模板文件：

| 系统 | 命令 |
|------|------|
| Windows CMD | copy .env.example .env |
| Windows PowerShell | cp .env.example .env |
| Mac / Linux / Git Bash | cp .env.example .env |

然后用文本编辑器打开 .env，填入你的 API Key：

DEEPSEEK_API_KEY=sk-你的key
DEEPSEEK_MODEL=deepseek-chat
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1

保存。

> **安全提示**：.env 包含敏感信息，**不要提交到 Git**。项目根目录的 .gitignore 已经默认忽略了 .env，可放心。


## 第 1 节：4 个迷你实验

这一节我们开始跑代码，帮你建立"AI 到底在做什么"的直觉。

**前提**：确保你已经完成了第 0.7 节（配置好了 .env）。如果还没配置，先回去配置。

进入 example_lessons 目录：

cd example_lessons

### 实验 1：直接和 AI 对话

python 01_hello_llm.py

你会看到三个部分：
1. **基础对话**：AI 回答"什么是 RAG"
2. **温度参数的影响**：同一个问题，AI 给出不同风格的回答（温度低则稳定，温度高则更有"创造力"）
3. **幻觉演示**：在特定 prompt 下，AI 可能会编造不存在的信息

观察重点：第三步演示了"无根据回答"的风险。RAG 的核心价值正是通过提供真实文本来约束这种编造行为。

### 实验 2：把文字变成数字

python 02_embeddings.py

**首次运行会下载 BGE 模型**（bge-small-zh-v1.5，FP32 约 91MB）。如果下载慢，参考 README 第七步设置 HF_ENDPOINT 镜像。

跑通后会看到 5 句话两两之间的相似度矩阵。重点观察：

- "今天天气真好" 和 "今日阳光明媚" 相似度约 0.75（高）
- 这两句话和 "我午餐吃了红烧肉" 相似度约 0.2（低）
- "My favorite food is braised pork" 和 "红烧肉" 相似度约 0.55（中等，跨语言语义仍有响应）

这就是向量检索的基础：把意思相近的句子在向量空间里放在相近的位置。AI 不需要"读懂"文字，只需要算几何距离。

### 实验 3：用向量找文档

python 03_vector_search.py

这个实验建了一个 5 篇文档的小型向量库，然后用查询去搜索。

你会看到每个文档的相似度分数。注意：纯向量检索对 "AI 怎么学" 这种语义查询很准，但对 "LangChain 怎么用" 这种包含专有名词的查询，可能不如关键词匹配精准。

这就引出了下一个实验。

### 实验 4：完整 RAG 流程

python 04_mini_rag.py

这个实验对比了"无 RAG 的 AI"和"有 RAG 的 AI"。

问同一个问题（"蓝海科技签订的合同金额"）：

- 无 RAG（普通 AI）：如果 prompt 不加限制，AI 会回答 "我没有相关信息"；如果加了"必须回答"的强制指令，它可能编一个数字。
- 有 RAG：AI 准确回答 480,000 元，并标注来源段落。

**这就是 RAG 的全部奥义**：
1. 你问问题
2. 系统从你的文档里找相关段落
3. 把这些段落 + 问题一起发给 AI
4. AI 被 prompt 约束只能根据这些段落回答
5. 结果：准确 + 可溯源
## 第 2 节：跑通完整系统

### 2.1 索引示例文档

回到项目根目录（或 cd ../src）：

cd ../src
python indexer.py --force

**首次运行会再次下载 BGE 模型**（如果实验 2 已下载过，会复用缓存）。如果下载慢，请设置 HF_ENDPOINT（见 README）。

完成后看到：

[info] Files: 6 total, 6 changed, 0 deleted
[done] total_files: 6, new_or_changed: 6, chunks_added: 12, elapsed_seconds: 1.5

### 2.2 评估检索质量

python evaluator.py

输出每个问题的检索结果及汇总指标：

hit_at_1  = 1.0
context_precision = 0.825
context_recall    = 1.0

- **hit_at_1**：每个问题检索结果的 Top-1 段落是否包含预设关键词。1.0 表示全部命中。
- **context_precision**：返回的 5 段中，真正相关的比例。
- **context_recall**：所有相关段落中，被召回的比例。

### 2.3 快速诊断

遇到问题先跑诊断脚本：

```bash
cd src && python diagnostic.py
```

检查 6 项：Qdrant 集合大小、BM25、Dense、Hybrid、Reranker、Mini-evaluator。如果 Qdrant 点数异常（提示 WARN），运行 `python indexer.py --force` 清理累积的旧向量。

### 2.4 启动网页界面

streamlit run app.py

浏览器自动打开 http://localhost:8501 。

界面分两块：
- 左侧：文档目录树（点击可跳转）
- 中间：聊天框

试试这些问题：
- 蓝海科技签的合同金额是多少？
- 合同延期罚则是怎样的？
- 莫干山徒步要带什么装备？
- 12 月版本什么时候上线？

每个回答下面会显示引用来源。点击展开可看到原文上下文和置信度。

### 2.5 加自己的文档

把文档复制到 docs/ 文件夹，支持 .md、.txt、.pdf、.docx。

**不支持**：.doc（旧版 Word）、.pptx（PPT）、.xlsx（Excel）。

然后运行：

python indexer.py

不加 --force 时，系统智能检测变化：
- 新文件 → 加入索引
- 修改过的文件 → 重新索引
- 删除的文件 → 从索引移除
- 未变化的文件 → 跳过（耗时 < 0.1 秒）


## 第 3 节：调参与优化

系统准不准，受几个关键参数影响。这些参数都在 src/config.py 里。

### 3.1 参数表

| 参数 | 默认值 | 作用 | 调大 | 调小 |
|------|--------|------|------|------|
| CHUNK_SIZE | 500 | 每段字符数 | 上下文更全，但检索变粗 | 检索更精，但上下文可能不足 |
| CHUNK_OVERLAP | 80 | 相邻段重叠字符数 | 避免边界切断，但索引变大 | 节省存储，但可能丢边界信息 |
| TOP_K | 5 | 返回给 AI 的段落数 | 覆盖更全面，但噪声增多 | 更精准，但可能漏内容 |
| CONFIDENCE_THRESHOLD | 0.3 | 最低置信度阈值 | 系统更保守，少答但准 | 更愿意尝试，但可能答错 |

### 3.2 调参决策树

**什么时候该调哪个参数？**

1. **AI 回答时上下文明显不够**（比如问题涉及多个细节，但 AI 只引用了一小段）→ 调大 CHUNK_SIZE 到 600-800，同时适当调大 CHUNK_OVERLAP 到 100-120。
2. **AI 引用了完全不相关的内容** → 调小 TOP_K 到 3，减少噪声干扰。
3. **问题很具体（如合同编号 "HT-2024-012"）但系统找不到** → 可能是向量检索漏了精确关键词。检查 retriever.py 是否开启了混合检索（默认开启）。如果已开启，调大 TOP_K 到 10，观察 Top-20 里是否有目标段落。
4. **AI 说"没有相关信息"但你知道文档里有** → 先确认文档是否被索引（看 indexer.py 输出）。如果已索引但检索不到，调大 TOP_K 到 15 再试。
5. **AI 回答准确但废话太多** → 在 qa.py 的 STRICT_SYSTEM_PROMPT 中增加 "答案控制在 100 字以内" 的约束。

### 3.3 调参步骤

1. 修改 src/config.py 中的参数
2. 重建索引：python indexer.py --force
3. 评估：python evaluator.py 看指标变化
4. 实际测试：streamlit run app.py 手工问几个问题
5. 重复 1-4 直到满意

### 3.4 切换嵌入模型

默认 BAAI/bge-small-zh-v1.5（91MB，CPU 友好）。

更大的模型（效果更好但更慢）：
- BAAI/bge-base-zh-v1.5（约 409MB，需要更多内存）
- BAAI/bge-large-zh-v1.5（约 1.3GB，建议 GPU）

修改 .env：
EMBEDDING_MODEL=BAAI/bge-base-zh-v1.5

然后重新运行 indexer.py --force。


## 第 4 节：进阶功能

### 4.1 多轮对话

在网页界面直接试：
1. 问："蓝海科技签的合同金额是多少？"
2. AI 回答。
3. 追问："那延期罚则呢？"

第二问里"那"指什么？AI 怎么知道还是同一份合同？

原理：src/qa.py 的 format_history 函数会把最近 4 轮对话拼成历史上下文，发给 AI。AI 看到完整对话后能理解指代。

### 4.2 文件自动监听

不想手动跑 indexer.py？用监听：

python src/watcher.py

启动后，任何 docs/ 下的文件变化，2 秒内自动重新索引。背后是用 watchdog 库调用操作系统的文件通知 API（Windows 的 ReadDirectoryChangesW，Linux 的 inotify），不会轮询，性能开销极低。

### 4.3 Notion 同步

如果你用 Notion 记笔记，可以一键同步到本系统。

1. 访问 https://www.notion.so/my-integrations 创建 integration
2. 复制 Internal Integration Token（以 secret_ 开头）
3. 在你的 Notion 数据库页面，右上角 ... → Connections → 添加刚才的 integration
4. 从数据库 URL 中复制 database id（URL 中 notion.so/xxx?v=yyy 的 xxx 部分）
5. 填入 .env：
   NOTION_API_KEY=secret_xxxxxxxx
   NOTION_DATABASE_ID=xxxxxxxx
6. 安装依赖：pip install notion-client
7. 运行：python src/notion_sync.py

脚本会拉取所有页面，转成 Markdown 存到 docs/notion/，然后跑 indexer.py 即可索引。

### 4.4 自定义测试集

默认测试集在 src/evaluator.py 的 DEFAULT_TEST_SET 中。你也可以自定义：

1. 在 eval/ 目录下新建 test_set.json（目录不存在则手动创建）
2. 格式：
   [
     {
       "question": "你的问题",
       "ground_truth_keywords": ["关键词1", "关键词2"],
       "must_cite": "期望引用的文件名.md"
     }
   ]
3. 运行 python evaluator.py，它会自动合并你的测试集进行评估。
## 第 5 节：部署上线

### 5.1 部署到云服务器

最简方案：租一台云服务器（阿里云、腾讯云等），把代码传上去。

# 在本地打包（排除虚拟环境和数据）
scp -r src docs requirements.txt .env.example user@server:/opt/rag/

# 在服务器上
ssh user@server
cd /opt/rag
python3.11 -m venv .venv
source .venv/bin/activate
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt
cp .env.example .env
# 编辑 .env 填 API Key
cd src
python indexer.py --force
nohup streamlit run app.py --server.port 8501 --server.address 0.0.0.0 &

最后一行 nohup ... & 让程序后台运行，关闭终端也不影响。

服务器防火墙需开放 8501 端口。然后访问 http://服务器IP:8501。

### 5.2 Docker 部署（推荐）

Docker 将应用打包成镜像，方便迁移和管理。

**Dockerfile**：

FROM python:3.11-slim

# 创建非 root 用户（安全最佳实践）
RUN adduser --disabled-password --gecos '' appuser

WORKDIR /app

# 先复制依赖文件，利用 Docker 缓存
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 复制源码并设置权限
COPY . .
RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 8501

CMD ["streamlit", "run", "src/app.py", "--server.port=8501", "--server.address=0.0.0.0"]

**docker-compose.yml**（更方便）：

version: '3'
services:
  rag:
    build: .
    ports:
      - "8501:8501"
    volumes:
      - ./docs:/app/docs
      - ./qdrant_data:/app/qdrant_data
    environment:
      - DEEPSEEK_API_KEY=${DEEPSEEK_API_KEY}
      - HF_ENDPOINT=https://hf-mirror.com
    restart: unless-stopped

构建并运行：

docker-compose up -d

-v 挂载的 docs 和 qdrant_data 在宿主机上，容器删除后数据不丢失。

### 5.3 加域名和 HTTPS

裸跑在 8501 端口不美观。用 Nginx 反向代理 + Let's Encrypt 免费证书。

**Nginx 配置**（/etc/nginx/sites-available/rag）：

server {
    listen 80;
    server_name rag.yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400;   # 防止长连接超时
    }
}

启用并装证书：

sudo ln -s /etc/nginx/sites-available/rag /etc/nginx/sites-enabled/
sudo certbot --nginx -d rag.yourdomain.com

完成后访问 https://rag.yourdomain.com。

### 5.4 加访问密码（Basic Auth）

Streamlit 本身无认证，可以用 Nginx 加一层密码。

安装工具：

# Ubuntu / Debian
sudo apt install apache2-utils

# CentOS / RHEL
sudo yum install httpd-tools

创建密码文件：

# 第一次创建（-c 参数）
sudo htpasswd -c /etc/nginx/.htpasswd myuser

# 后续添加用户（不加 -c）
sudo htpasswd /etc/nginx/.htpasswd anotheruser

# 确保 Nginx 有读取权限
sudo chmod 644 /etc/nginx/.htpasswd

修改 Nginx 配置，在 location / 块中加入：

location / {
    auth_basic "Restricted";
    auth_basic_user_file /etc/nginx/.htpasswd;
    # ... 其他 proxy 配置同上
}

重载 Nginx：sudo nginx -s reload。再次访问就需要输入用户名密码了。


## 写在最后

到这里你应该已经有一个能用的私人 AI 助手了。

**下一步可以做什么？**

- 用 Obsidian 写笔记，然后改造本系统支持 Obsidian Vault 同步
- 换更大的 LLM（如 GPT-4）或本地模型（Ollama + Qwen）提升回答质量
- 加多模态支持（读取 PDF 中的图表），可参考 unstructured 的 partition_pdf 的 extract_images 参数
- 多用户系统，让家人朋友也能用

最重要的：**拿你自己的真实数据去试**。教程里的 6 篇示例是给你跑的，真正好玩的是把你自己的笔记、合同、邮件丢进去，让 AI 帮你找答案。

Good luck!