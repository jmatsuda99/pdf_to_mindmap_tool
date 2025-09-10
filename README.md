# PDF → Mindmap (Mermaid図・強化サニタイズ v4)

- 先頭が**数字だけ**の行は `No. <数字>` に変換（例：`1` → `No. 1`）
- 先頭の **- / • / ・ / ·** は除去（`-予測周期` → `予測周期`）
- 記号（`\ { } [ ] < > # | ~ " \` など）を安全文字に置換
- デフォルト深さ L=2、Mermaid図で描画

## 使い方
```bash
pip install -r requirements.txt
streamlit run app.py
```
