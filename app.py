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
except Exception:
    PyPDF2 = None

try:
    import graphviz
except Exception:
    graphviz = None

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

def extract_text_from_pdf(file_bytes: bytes) -> str:
    if PyPDF2 is None:
        raise RuntimeError("PyPDF2 not installed. Please `pip install PyPDF2`.")
    reader = PyPDF2.PdfReader(BytesIO(file_bytes))
    texts = []
    for page in reader.pages:
        try:
            texts.append(page.extract_text() or "")
        except Exception:
            texts.append("")
    return "\n".join(texts)

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

def html_escape(s: str) -> str:
    return s.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

def to_graphviz(node: Node):
    if graphviz is None:
        raise RuntimeError("graphviz is not installed. Please `pip install graphviz`.")
    dot = graphviz.Digraph(format="svg")
    def add(n: Node, parent_id: Optional[str]=None, idx=[0]):
        idx[0]+=1
        nid=f"n{idx[0]}"
        label=html_escape(n.title)
        dot.node(nid, f"<{label}>", shape="box", style="rounded,filled", fillcolor="white")
        if parent_id:
            dot.edge(parent_id, nid)
        for c in node.children:
            add(c, nid, idx)
        return nid
    add(node, None)
    return dot

def to_edges(node: Node, parent_title: Optional[str]=None, rows=None):
    if rows is None: rows = []
    rows.append({"id": node.title, "parent": parent_title})
    for c in node.children:
        to_edges(c, node.title, rows)
    return rows

# ------------------------------
# Streamlit UI (with explicit keys)
# ------------------------------
st.set_page_config(page_title="PDF→構文木（Graphviz/Sunburst） L=2", layout="wide")
st.title("構文木解析 → 視覚化（Graphvizツリー / Sunburst）")

uploaded=st.file_uploader("PDFファイルをアップロード", type=["pdf"], key="pdf_file")
col1,col2=st.columns([2,1])
depth=col2.slider("表示する深さ (L)", min_value=1, max_value=8, value=DEFAULT_DEPTH, step=1, key="depth_slider")
options=("Graphvizツリー","Sunburst","Treemap","アウトライン")
view = col2.radio("表示モード", options=options, index=0, key="view_mode")

if uploaded is not None:
    try:
        content=uploaded.read()
        text=extract_text_from_pdf(content)
    except Exception as e:
        st.error(f"PDF抽出エラー: {e}")
        st.stop()

    with st.expander("抽出テキストを見る"):
        st.text_area("Raw text", text, height=200)

    lines=[ln.strip() for ln in text.splitlines() if ln.strip()!=""]
    tree=build_tree_from_lines(lines)
    root=tree.children[0] if len(tree.children)==1 else Node(uploaded.name.rsplit(".",1)[0], children=tree.children)
    trimmed=trim_depth(root, depth)
    if trimmed is None:
        st.warning("この深さではノードがありません。")
    else:
        if view=="Graphvizツリー":
            try:
                dot = to_graphviz(trimmed)
                st.graphviz_chart(dot.source, use_container_width=True)
            except Exception as e:
                st.error(f"Graphviz描画エラー: {e}")
        elif view in ("Sunburst","Treemap"):
            if px is None or pd is None:
                st.error("plotly と pandas が必要です。 `pip install plotly pandas`")
            else:
                rows = to_edges(trimmed)
                df = pd.DataFrame(rows)
                if view=="Sunburst":
                    fig = px.sunburst(df, names="id", parents="parent")
                else:
                    fig = px.treemap(df, names="id", parents="parent")
                fig.update_layout(margin=dict(l=0,r=0,t=30,b=0))
                st.plotly_chart(fig, use_container_width=True)
        else:
            def to_outline(n:Node, level=0, out=None):
                if out is None: out=[]
                out.append("  "*level + "- " + n.title)
                for c in node.children: to_outline(c, level+1, out)
                return "\n".join(out)
            st.code(to_outline(trimmed), language="text")

        with st.expander("エクスポート"):
            colA, colB = st.columns(2)
            json_bytes=json.dumps(trimmed.to_dict(), ensure_ascii=False, indent=2).encode("utf-8")
            colA.download_button("JSON", data=json_bytes, file_name="tree.json", key="dl_json")
            if graphviz is not None:
                dot = to_graphviz(trimmed)
                colB.download_button("Graphviz DOT", data=dot.source.encode("utf-8"), file_name="tree.dot", key="dl_dot")
else:
    st.info("右上のファイルピッカーからPDFを選択してください。")
