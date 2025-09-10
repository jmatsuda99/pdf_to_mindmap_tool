#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import re
import json
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
import streamlit as st
from io import BytesIO

try:
    import PyPDF2
except Exception as e:
    PyPDF2 = None

# ------------------------------
# Data structures
# ------------------------------
@dataclass
class Node:
    title: str
    children: List["Node"] = field(default_factory=list)

    def to_dict(self):
        return {"title": self.title, "children": [c.to_dict() for c in self.children]}

# ------------------------------
# Simple PDF text extractor
# ------------------------------
def extract_text_from_pdf(file_bytes: bytes) -> str:
    if PyPDF2 is None:
        raise RuntimeError("PyPDF2 is not installed. Please `pip install PyPDF2`.")
    reader = PyPDF2.PdfReader(BytesIO(file_bytes))
    texts = []
    for page in reader.pages:
        try:
            texts.append(page.extract_text() or "")
        except Exception:
            texts.append("")
    return "\n".join(texts)

# ------------------------------
# Outline parser
# ------------------------------
# Heuristics: detect headings that look like:
#   1.
#   1.1
#   1-1
#   1) / 1）
#   第1章 / 付録 / Appendix
# We fallback to lines in ALLCAPS-ish or lines with strong numbering patterns.

_heading_patterns = [
    r"^(?:第\s*\d+\s*章)\s*(.+)?$",                            # 第1章 〇〇
    r"^(?:Appendix|付録)\s*[:：]?\s*(.+)?$",                   # Appendix / 付録
    r"^(\d+(?:[.\-]\d+){0,3})[)\.．]\s*(.+)$",                 # 1) 1. 1.1 1-2-3.
    r"^(\d+)\s*[:：-]\s*(.+)$",                                # 1: 1- 1：
]

def is_heading(line: str) -> Optional[Tuple[int, str]]:
    s = line.strip()
    if not s:
        return None
    # try patterns
    for pat in _heading_patterns:
        m = re.match(pat, s)
        if m:
            # assign levels heuristically by counting dot/hyphen segments if present
            if len(m.groups()) == 2 and m.group(1):
                num = m.group(1)
                level = num.count(".") + num.count("-") + 1
                title = m.group(2).strip()
                return level, f"{num} {title}".strip()
            else:
                # 第1章 / 付録 etc. treat as level 1
                rest = m.group(1) if len(m.groups()) >= 1 else ""
                title = (rest or s).strip()
                return 1, title
    # very short strong line (fallback)
    if len(s) <= 30 and re.search(r"[A-Za-z0-9一-龥ぁ-んァ-ン]+", s) and s.endswith((":", "：")):
        return 1, s[:-1].strip()
    return None

def build_tree_from_lines(lines: List[str]) -> Node:
    root = Node("ROOT")
    stack: List[Tuple[int, Node]] = [(0, root)]
    last_added = root
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        h = is_heading(line)
        if h:
            level, title = h
            # clamp level to at least 1
            level = max(1, level)
            node = Node(title)
            # pop to parent level
            while stack and stack[-1][0] >= level:
                stack.pop()
            parent_level, parent_node = stack[-1]
            parent_node.children.append(node)
            stack.append((level, node))
            last_added = node
        else:
            # attach as bullet under the last heading (level+1)
            bullet = Node(line)
            # ensure at least one heading exists; otherwise under root
            parent = last_added if last_added is not None else root
            parent.children.append(bullet)
    return root

# ------------------------------
# Depth trimming
# ------------------------------
def trim_depth(node: Node, depth: int, current: int = 0) -> Optional[Node]:
    if current >= depth:
        return None
    new_node = Node(node.title)
    if node.children and current + 1 < depth:
        for ch in node.children:
            trimmed = trim_depth(ch, depth, current + 1)
            if trimmed is not None:
                new_node.children.append(trimmed)
    return new_node

# ------------------------------
# Mermaid mindmap generator
# ------------------------------
def to_mermaid(node: Node) -> str:
    lines = ["mindmap"]
    def rec(n: Node, indent: int):
        prefix = "  " * indent
        title = n.title.replace("`", "'")  # escape backticks
        if indent == 0:
            lines.append(f"{prefix}root(({title}))")
        else:
            lines.append(f"{prefix}{title}")
        for c in n.children:
            rec(c, indent + 1)
    rec(node, 0)
    return "\n".join(lines)

# ------------------------------
# Streamlit UI
# ------------------------------
st.set_page_config(page_title="PDF → Mindmap (Mermaid) with Depth", layout="wide")

st.title("構文木解析 → マインドマップ（Mermaid）")
st.caption("PDFから章節構造を抽出し、深さ指定でマインドマップを表示・エクスポートできます。")

uploaded = st.file_uploader("PDFファイルをアップロード", type=["pdf"])
col1, col2 = st.columns([2, 1])

default_depth = 3
depth = col2.slider("表示する深さ (L)", min_value=1, max_value=8, value=default_depth, step=1)

if uploaded is not None:
    with st.spinner("PDFテキストを抽出中..."):
        try:
            content = uploaded.read()
            text = extract_text_from_pdf(content)
        except Exception as e:
            st.error(f"PDF抽出でエラー: {e}")
            st.stop()

    # Show raw preview (collapsible)
    with st.expander("抽出テキストを表示"):
        st.text_area("Raw text", text, height=200)

    # Normalize lines
    lines = [ln.strip() for ln in text.splitlines()]
    # Remove excessive blank lines
    lines = [ln for ln in lines if ln.strip() != ""]

    with st.spinner("章節を解析中..."):
        tree = build_tree_from_lines(lines)

    # Build a cleaned tree (remove ROOT wrapper)
    # If root has only one big child (common), use its title as root
    root = tree
    if len(tree.children) == 1:
        root = tree.children[0]
    else:
        # Create a synthetic title from filename
        title = uploaded.name.rsplit(".", 1)[0]
        root = Node(title, children=tree.children)

    trimmed = trim_depth(root, depth)

    if trimmed is None:
        st.warning("選択された深さでは表示できるノードがありません。")
    else:
        # Mermaid text
        mermaid_code = "```mermaid\n" + to_mermaid(trimmed) + "\n```"

        # Display Mermaid via components (load mermaid js from CDN)
        # For environments without internet, we still show the code block as text.
        st.subheader("マインドマップ表示")
        st.markdown(mermaid_code)

        # Exporters
        with st.expander("エクスポート / ダウンロード"):
            colA, colB, colC = st.columns(3)
            # JSON
            json_bytes = json.dumps(trimmed.to_dict(), ensure_ascii=False, indent=2).encode("utf-8")
            colA.download_button("JSONをダウンロード", data=json_bytes, file_name="mindmap.json", mime="application/json")
            # Mermaid
            colB.download_button("Mermaidコードをダウンロード", data=mermaid_code.encode("utf-8"), file_name="mindmap.mmd", mime="text/plain")
            # Plain text outline
            def to_outline(n: Node, level=0, out=None):
                if out is None:
                    out = []
                out.append("  " * level + "- " + n.title)
                for c in n.children:
                    to_outline(c, level+1, out)
                return "\n".join(out)
            outline_txt = to_outline(trimmed)
            colC.download_button("テキストアウトラインをダウンロード", data=outline_txt.encode("utf-8"),
                                 file_name="outline.txt", mime="text/plain")

        with st.expander("解析パラメータ（微調整）"):
            st.write("見出し検出は正規表現ベースのヒューリスティックです。PDFの体裁によっては誤検知が起きる場合があります。")

else:
    st.info("右上のファイルピッカーからPDFを選択してください。")

st.markdown("---")
st.caption("Tips: 見出し番号（1., 1.1, 1-1 など）や「第1章」「付録」等を優先的に見出しとして扱います。誤検知がある場合は、PDFのレイアウト崩れや抽出精度が原因のことがあります。")
