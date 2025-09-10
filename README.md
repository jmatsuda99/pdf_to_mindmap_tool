# PDF → Mindmap (Mermaid図)

PDFから章節構造を解析し、**深さ(L)指定**でマインドマップをMermaid図として描画します。

## 使い方
```bash
pip install -r requirements.txt
streamlit run app.py
```

- デフォルト深さは L=2
- PDFをアップロードし、スライダーで階層深さを変更
- マインドマップをブラウザ上にMermaid図として表示
- JSON / Mermaidコード / テキストアウトラインをエクスポート可能
