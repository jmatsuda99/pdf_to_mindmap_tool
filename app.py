#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import re
import json
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
import streamlit as st
from io import BytesIO

# ---- PDF libs: try pypdf, then PyPDF2 ----
try:
    import pypdf as _pypdf
except Exception:
    _pypdf = None
try:
    import PyPDF2 as _pypdf2
except Exception:
    _pypdf2 = None

# ---- Plot libs ----
try:
    import plotly.express as px
    import pandas as pd
except Exception:
    px = None
    pd = None

DEFAULT_DEPTH = 2

@dataclass
class Node:
    title: str
    children: List["Node"] = field(default_factory=list)
    def to_dict(self):
        return {"title": self.title, "children": [c.to_dict() for c in self.children]}

# ------------------------------
# PDF / TEXT extraction
# ------------------------------
def extract_text_from_pdf(file_bytes: bytes) -> str:
    if _pypdf is not None:
        reader = _pypdf.PdfReader(BytesIO(file_bytes))
        return "\n".join([(p.extract_text() or "") for p in reader.pages])
    if _pypdf2 is not None:
        reader = _pypdf2.PdfReader(BytesIO(file_bytes))
        return "\n".join([(p.extract_text() or "") for p in reader.pages])
    raise RuntimeError("PDFライブラリが未インストールです。`pip install pypdf` もしくは `pip install PyPDF2` を実行してください。")

def extract_text_from_txt(file_bytes: bytes, encoding: str = "utf-8") -> str:
    try:
        return file_bytes.decode(encoding, errors="ignore")
    except Exception:
        return file_bytes.decode("utf-8", errors="ignore")

# ------------------------------
# Heading detection
# ------------------------------
_heading_patterns = [
    r"^(?:第\s*\d+\s*章)\s*(.+)?$",
    r"^(?:Appendix|付録)\s*[:：]?\s*(.+)?$",
    r"^(\d+(?:[.\-]\d+){0,3})[)\.．]\s*(.+)$",
    r"^(\d+)\s*[:：-]\s*(.+)$",
]

def is_heading(line: str) -> Optional[Tuple[int,str]]:
    s = line.strip()
    if not s: return None
    for pat in _heading_patterns:
        m = re.match(pat, s)
        if m:
            if len(m.groups())==2 and m.group(1):
                num = m.group(1)
                level = num.count(".")+num.count("-")+1
                title = m.group(2).strip()
                return level, f"{num} {title}".strip()
            else:
                rest = m.group(1) if len(m.groups())>=1 else ""
                title = (rest or s).strip()
                return 1, title
    if len(s)<=30 and re.search(r"[A-Za-z0-9一-龥ぁ-んァ-ン]+", s) and s.endswith((":", "：")):
        return 1, s[:-1].strip()
    return None

def build_tree_from_lines(lines):
    root = Node("ROOT")
    stack=[(0,root)]
    last_added=root
    for raw in lines:
        line=raw.strip()
        if not line: continue
        h=is_heading(line)
        if h:
            level,title=h
            level=max(1,level)
            node=Node(title)
            while stack and stack[-1][0]>=level:
                stack.pop()
            parent_level,parent_node=stack[-1]
            parent_node.children.append(node)
            stack.append((level,node))
            last_added=node
        else:
            parent=last_added if last_added is not None else root
            parent.children.append(Node(line))
    return root

def trim_depth(node: Node, depth:int, current:int=0)->Optional[Node]:
    if current>=depth: return None
    new_node=Node(node.title)
    if node.children and current+1<depth:
        for ch in node.children:
            trimmed=trim_depth(ch,depth,current+1)
            if trimmed is not None:
                new_node.children.append(trimmed)
    return new_node

# ------------------------------
# Graphviz DOT source builder (no python-graphviz dependency)
# ------------------------------
def to_dot(node: Node) -> str:
    lines = ["digraph G {",
             '  graph [rankdir=TB, bgcolor="white"];',
             '  node [shape=box, style="rounded,filled", color="#444444", fillcolor="white", fontname="sans-serif"];',
             '  edge [color="#888888"];']
    counter = {"i": 0}
    def esc(s: str)->str:
        s = s.replace("\\", "\\\\").replace('"','\\"')
        s = s.replace("\n"," ")
        return s
    def add(n: Node, parent: Optional[str] = None):
        counter["i"] += 1
        nid = f"n{counter['i']}"
        label = esc(n.title)
        lines.append(f'  {nid} [label="{label}"];')
        if parent:
            lines.append(f"  {parent} -> {nid};")
        for c in n.children:
            add(c, nid)
    add(node, None)
    lines.append("}")
    return "\n".join(lines)

# ------------------------------
# Sunburst/Treemap
# ------------------------------
def to_edges(node: Node, parent_title: Optional[str]=None, rows=None):
    if rows is None: rows = []
    rows.append({"id": node.title, "parent": parent_title})
    for c in node.children:
        to_edges(c, node.title, rows)
    return rows

# ------------------------------
# UI
# ------------------------------
st.set_page_config(page_title="PDF→構文木（Graphviz/Sunburst） L=2", layout="wide")
st.title("構文木解析 → 視覚化（Graphvizツリー / Sunburst）")

input_mode = st.radio("入力モード", options=("PDFアップロード","テキスト貼付/アップロード"), index=0, key="input_mode")

uploaded = None
text = ""
if input_mode == "PDFアップロード":
    uploaded = st.file_uploader("PDFファイルをアップロード", type=["pdf"], key="pdf_file")
else:
    st.write("テキストを直接貼り付けるか、.txtをアップロードしてください。")
    txt_file = st.file_uploader("テキストファイル（任意）", type=["txt"], key="txt_file")
    text_area = st.text_area("テキスト貼付", height=200, key="text_area")
    if txt_file is not None:
        text = extract_text_from_txt(txt_file.read())
    elif text_area.strip():
        text = text_area

col1,col2=st.columns([2,1])
depth=col2.slider("表示する深さ (L)", min_value=1, max_value=8, value=DEFAULT_DEPTH, step=1, key="depth_slider")
view = col2.radio("表示モード", options=("Graphvizツリー","Sunburst","Treemap","アウトライン"), index=0, key="view_mode")

if input_mode == "PDFアップロード" and uploaded is not None:
    try:
        content=uploaded.read()
        text=extract_text_from_pdf(content)
    except Exception as e:
        st.error(f"PDF抽出エラー: {e}")
        st.info("→ `pip install pypdf` もしくは `pip install PyPDF2` を実行するか、上の入力モードを「テキスト貼付」に切替えてお試しください。")
        st.stop()

if text:
    with st.expander("抽出テキストを見る"):
        st.text_area("Raw text", text, height=200)

    lines=[ln.strip() for ln in text.splitlines() if ln.strip()!=""]
    tree=build_tree_from_lines(lines)
    root=tree.children[0] if len(tree.children)==1 else Node("Document", children=tree.children)
    trimmed=trim_depth(root, depth)
    if trimmed is None:
        st.warning("この深さではノードがありません。")
    else:
        if view=="Graphvizツリー":
            dot_src = to_dot(trimmed)
            st.graphviz_chart(dot_src, use_container_width=True)
        elif view in ("Sunburst","Treemap"):
            if px is None or pd is None:
                st.error("plotly と pandas が必要です。 `pip install plotly pandas`")
            else:
                rows = to_edges(trimmed)
                df = pd.DataFrame(rows)
                fig = px.sunburst(df, names="id", parents="parent") if view=="Sunburst" else px.treemap(df, names="id", parents="parent")
                fig.update_layout(margin=dict(l=0,r=0,t=30,b=0))
                st.plotly_chart(fig, use_container_width=True)
        else:
            def to_outline(n:Node, level=0, out=None):
                if out is None: out=[]
                out.append("  "*level + "- " + n.title)
                for c in n.children: to_outline(c, level+1, out)
                return "\n".join(out)
            st.code(to_outline(trimmed), language="text")

        with st.expander("エクスポート"):
            colA, colB = st.columns(2)
            json_bytes=json.dumps(trimmed.to_dict(), ensure_ascii=False, indent=2).encode("utf-8")
            colA.download_button("JSON", data=json_bytes, file_name="tree.json", key="dl_json")
            colB.download_button("Graphviz DOT", data=to_dot(trimmed).encode("utf-8"), file_name="tree.dot", key="dl_dot")
else:
    st.info("PDF または テキストを入力してください。")
