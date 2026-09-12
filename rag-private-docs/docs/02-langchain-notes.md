# LangChain 使用笔记

## 安装

```bash
pip install langchain langchain-community langchain-openai
```

## Document Loaders

LangChain 提供多种加载器：

- `TextLoader`：纯文本
- `UnstructuredMarkdownLoader`：Markdown
- `PyPDFLoader`：PDF 文件
- `Docx2txtLoader`：Word 文档

## Text Splitters

- `RecursiveCharacterTextSplitter`：按分隔符递归切分，推荐
- `CharacterTextSplitter`：固定字符数
- `TokenTextSplitter`：按 token 数

## 关键参数

- `chunk_size`：每块大小（中文建议 300-800 字符）
- `chunk_overlap`：相邻块的重叠（建议 10-20%）
- `separators`：分隔符列表，按优先级使用

## 嵌入模型

- `HuggingFaceBgeEmbeddings`：本地运行，免费
- `OpenAIEmbeddings`：调用 OpenAI API
- `DashScopeEmbeddings`：阿里云通义千问

## 向量数据库

- `Chroma`：轻量，适合本地
- `Qdrant`：生产级，支持本地文件模式
- `Milvus`：大规模分布式
