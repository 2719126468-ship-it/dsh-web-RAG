"""多模态解析：从 PDF 提取图片，用 VLM 生成描述文本。

依赖：PyMuPDF（fitz）、openai
配置：config.ENABLE_MULTIMODAL / VLM_MODEL / VLM_BASE_URL / VLM_API_KEY
"""
import base64
import os
from pathlib import Path
from typing import List, Optional

from langchain_core.documents import Document


def _get_vlm_client():
    try:
        from openai import OpenAI
    except ImportError:
        print("[warn] 未安装 openai，多模态功能不可用")
        return None

    from config import config

    api_key = getattr(config, "VLM_API_KEY", "") or os.getenv("DEEPSEEK_API_KEY", "")
    base_url = getattr(config, "VLM_BASE_URL", "") or os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")

    if not api_key:
        print("[warn] 未配置 VLM_API_KEY / DEEPSEEK_API_KEY，跳过图片描述生成")
        return None

    return OpenAI(api_key=api_key, base_url=base_url)


def _caption_image(client, img_bytes: bytes, model: str) -> str:
    b64 = base64.b64encode(img_bytes).decode("ascii")
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "请用简洁的中文描述这张图片的内容，包括图表中的关键数据和趋势。不超过 200 字。"},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                    ],
                }
            ],
            temperature=0.0,
            max_tokens=400,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        print(f"[warn] VLM 调用失败：{e}")
        return ""


def extract_images_with_captions(
    path: Path,
    min_size: int = 100,
    max_images: int = 20,
) -> List[Document]:
    """从 PDF 提取图片并生成描述。

    min_size：过滤掉小于该像素尺寸的小图（如装饰线）
    max_images：最多处理的图片数，防止 PDF 里几百张图拖慢索引
    """
    try:
        import fitz
    except ImportError:
        print(f"[warn] 未安装 PyMuPDF，跳过多模态解析。安装：pip install PyMuPDF")
        return []

    try:
        doc = fitz.open(str(path))
    except Exception as e:
        print(f"[warn] 打开 PDF 失败 {path}: {e}")
        return []

    client = _get_vlm_client()
    if client is None:
        doc.close()
        return []

    from config import config
    model = getattr(config, "VLM_MODEL", "gpt-4o-mini")

    docs: List[Document] = []
    count = 0
    for page_num, page in enumerate(doc, start=1):
        if count >= max_images:
            break
        for img_info in page.get_images(full=True):
            if count >= max_images:
                break
            xref = img_info[0]
            try:
                pix = fitz.Pixmap(doc, xref)
                if pix.width < min_size or pix.height < min_size:
                    continue
                if pix.n - pix.alpha >= 4:
                    pix = fitz.Pixmap(fitz.csRGB, pix)
                img_bytes = pix.tobytes("png")
            except Exception as e:
                print(f"[warn] 提取图片失败 page={page_num} xref={xref}: {e}")
                continue

            caption = _caption_image(client, img_bytes, model)
            if not caption:
                continue

            docs.append(Document(
                page_content=f"[图片描述] {caption}",
                metadata={
                    "source": str(path),
                    "page": page_num,
                    "type": "image",
                    "parser": "multimodal",
                },
            ))
            count += 1

    doc.close()
    print(f"[info] 从 {path.name} 提取并描述了 {len(docs)} 张图片")
    return docs
