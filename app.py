#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import re
import json
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
import streamlit as st
from io import BytesIO
import uuid

try:
    import PyPDF2
except Exception as e:
    PyPDF2 = None

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
            bullet=Node(line)
            parent=last_added if last_added is not None else root
            parent.children.append(bullet)
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

def to_mermaid(node: Node)->str:
    lines=["mindmap"]
    def rec(n:Node, indent:int):
        prefix="  "*indent
        title=n.title.replace("`","'")
        if indent==0:
            lines.append(f"{prefix}root(({title}))")
        else:
            lines.append(f"{prefix}{title}")
        for c in n.children:
            rec(c,indent+1)
    rec(node,0)
    return "\n".join(lines)

def render_mermaid(mermaid_inner:str):
    unique_id=f"mermaid-{uuid.uuid4().hex}"
    html=f"""
    <div id="{unique_id}">
      <pre class="mermaid">
{mermaid_inner}
      </pre>
    </div>
    <script>
      if (!window._mermaidLoaded) {{
        var s=document.createElement('script');
        s.src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js";
        s.onload=function(){{
          window._mermaidLoaded=true;
          mermaid.initialize({{ startOnLoad:false, securityLevel:'loose' }});
          mermaid.run();
        }};
        document.head.appendChild(s);
      }} else {{
        mermaid.run();
      }}
    </script>
    """
    st.components.v1.html(html,height=600,scrolling=True)

st.set_page_config(page_title="PDF→Mindmap (Mermaid)", layout="wide")
st.title("構文木解析 → マインドマップ（Mermaid図）")

uploaded=st.file_uploader("PDFファイルをアップロード", type=["pdf"])
col1,col2=st.columns([2,1])
depth=col2.slider("表示する深さ (L)",min_value=1,max_value=8,value=2,step=1)

if uploaded is not None:
    try:
        content=uploaded.read()
        text=extract_text_from_pdf(content)
    except Exception as e:
        st.error(f"PDF抽出エラー: {e}")
        st.stop()
    with st.expander("抽出テキストを見る"):
        st.text_area("Raw text",text,height=200)
    lines=[ln.strip() for ln in text.splitlines() if ln.strip()!=""]
    tree=build_tree_from_lines(lines)
    root=tree
    if len(tree.children)==1:
        root=tree.children[0]
    else:
        root=Node(uploaded.name.rsplit(".",1)[0],children=tree.children)
    trimmed=trim_depth(root,depth)
    if trimmed is None:
        st.warning("この深さではノードなし")
    else:
        mermaid_inner=to_mermaid(trimmed)
        st.subheader("マインドマップ表示（Mermaid図）")
        render_mermaid(mermaid_inner)
        mermaid_code="```mermaid\n"+mermaid_inner+"\n```"
        with st.expander("エクスポート"):
            colA,colB,colC=st.columns(3)
            json_bytes=json.dumps(trimmed.to_dict(),ensure_ascii=False,indent=2).encode("utf-8")
            colA.download_button("JSON",data=json_bytes,file_name="mindmap.json")
            colB.download_button("Mermaidコード",data=mermaid_code.encode("utf-8"),file_name="mindmap.mmd")
            def to_outline(n:Node,level=0,out=None):
                if out is None: out=[]
                out.append("  "*level+"- "+n.title)
                for c in n.children: to_outline(c,level+1,out)
                return "\n".join(out)
            outline_txt=to_outline(trimmed)
            colC.download_button("テキストアウトライン",data=outline_txt.encode("utf-8"),file_name="outline.txt")
else:
    st.info("右上のファイルピッカーからPDFを選択してください。")
