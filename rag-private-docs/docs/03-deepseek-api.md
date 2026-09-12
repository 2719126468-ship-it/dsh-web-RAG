# DeepSeek API 速查

## 获取 API Key

访问 https://platform.deepseek.com/ 注册并创建 API Key。

## 通过 OpenAI 兼容接口调用

DeepSeek 的 API 兼容 OpenAI 格式，所以可以直接用 `langchain_openai.ChatOpenAI`：

```python
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    model="deepseek-chat",
    openai_api_key="sk-xxx",
    openai_api_base="https://api.deepseek.com/v1",
    temperature=0.2,
)
```

## 主要模型

- `deepseek-chat`：通用对话，性价比高
- `deepseek-reasoner`：强推理，适合复杂问题

## 上下文窗口

- `deepseek-chat`：128K tokens
- `deepseek-reasoner`：128K tokens

## 注意事项

- 国内访问可能需要代理
- 单价约为 GPT-4 的 1/30
- 长上下文场景下注意费用
