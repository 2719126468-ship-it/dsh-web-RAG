# 贡献指南

感谢你对本项目的关注！欢迎提交 Issue 和 Pull Request。

## 开发环境

- Python 3.11 或更高版本
- 依赖见 rag-private-docs/requirements.txt

## 本地运行测试

pytest tests/ -v

预期结果：4 通过 + 5 跳过（未安装完整依赖时）。

## 提交 PR 的流程

1. Fork 本仓库
2. 新建分支：git checkout -b feature/your-feature
3. 修改代码，确保测试通过
4. 提交：git commit -m "描述你的改动"
5. 推送：git push origin feature/your-feature
6. 在 GitHub 上创建 Pull Request

## 代码风格

- 遵循 PEP 8
- 新增功能请附上对应测试

## 问题反馈

遇到问题请在 Issues 中提出，尽量附上：

- 操作系统和 Python 版本
- 复现步骤
- 完整报错信息
