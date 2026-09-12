"""记忆管理命令行工具。

用法：
    python memory_cli.py add "用户偏好用中文回答"
    python memory_cli.py search "偏好"
    python memory_cli.py list
    python memory_cli.py delete mem_xxx
"""
import sys

from memory import add_memory, search_memory, list_memories, delete_memory


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    cmd = sys.argv[1]

    if cmd == "add":
        if len(sys.argv) < 3:
            print("用法：python memory_cli.py add \"内容\"")
            return
        item = add_memory(sys.argv[2])
        print(f"已存储：{item['id']}")

    elif cmd == "search":
        if len(sys.argv) < 3:
            print("用法：python memory_cli.py search \"查询\"")
            return
        results = search_memory(sys.argv[2])
        if not results:
            print("无匹配记忆")
        for r in results:
            print(f"  [{r['id']}] {r['content']}")

    elif cmd == "list":
        items = list_memories()
        if not items:
            print("暂无记忆")
        for m in items:
            print(f"  [{m['id']}] {m['content']}")

    elif cmd == "delete":
        if len(sys.argv) < 3:
            print("用法：python memory_cli.py delete mem_xxx")
            return
        ok = delete_memory(sys.argv[2])
        print("已删除" if ok else "未找到")

    else:
        print(f"未知命令：{cmd}")
        print(__doc__)


if __name__ == "__main__":
    main()
