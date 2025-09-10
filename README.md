# PDF → 構文木（Graphviz / Sunburst） v5

Mermaidではエラーになりやすいケースに対応するため、**Graphvizツリー**と**Plotly Sunburst/Treemap**で安定表示する版です。  
デフォルト深さは **L=2**。

## 使い方
```bash
pip install -r requirements.txt
streamlit run app.py
```
- 表示モードを「Graphvizツリー / Sunburst / Treemap / アウトライン」から選択
- JSON と Graphviz DOT のダウンロードに対応
- Sunburst/Treemap で全体の包含関係を直感的に把握可能

※ GraphvizはPythonパッケージで描画できます（外部バイナリ不要）。
