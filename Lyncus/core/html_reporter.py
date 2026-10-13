"""
Enhanced HTML Reporter — Phase 3
Dark theme, interactive filtering, charts, category breakdown.
"""

from __future__ import annotations

from datetime import datetime
from html import escape
from pathlib import Path
from typing import TYPE_CHECKING

from Lyncus.core.utils import calc_score  # ✅ Fix #10: shared score function

if TYPE_CHECKING:
    from Lyncus.core.parser import Problem

SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2}

# ✅ Fix #10: Alias — pichla code _score() call karta tha
_score = calc_score


def export_html_report(
    problems: list[Problem],
    project_path: str,
    language: str,
    tools_used: list[str],
    scan_time: float,
    output_file: str = "Lyncus-report.html",
) -> None:
    """
    Full interactive HTML report banao.
    - Dark theme
    - Severity filter buttons
    - Category breakdown chart
    - Sortable table
    - Copy-to-clipboard for file paths
    """
    score = _score(problems)
    critical = sum(1 for p in problems if p.severity == "critical")
    warnings = sum(1 for p in problems if p.severity == "warning")
    info = sum(1 for p in problems if p.severity == "info")

    if score >= 80:
        score_color = "#22c55e"
    elif score >= 50:
        score_color = "#f59e0b"
    else:
        score_color = "#ef4444"

    # Problem rows
    rows_html = ""
    for p in sorted(problems, key=lambda x: SEVERITY_ORDER.get(x.severity, 9)):
        sev_badge_color = {
            "critical": "#ef4444",
            "warning": "#f59e0b",
            "info": "#3b82f6",
        }.get(p.severity, "#6b7280")

        # XSS fix: user-controlled data escape karo
        safe_severity = escape(p.severity)
        safe_category = escape(p.category)
        safe_copy_text = escape(f"{p.file}:{p.line}", quote=True)
        safe_tool = escape(p.tool)
        safe_message = escape(p.message)
        safe_file_loc = escape(f"{p.file}:{p.line}") if p.file else "—"
        suggestion_html = (
            f"<br><small style='color:#94a3b8'>💡 {escape(p.suggestion)}</small>"
            if p.suggestion
            else ""
        )

        rows_html += f"""
        <tr class="problem-row" data-severity="{safe_severity}" data-category="{safe_category}">
          <td>
            <span class="badge" style="background:{sev_badge_color}">
              {safe_severity.upper()}
            </span>
          </td>
          <td><code class="cat-badge">{safe_category}</code></td>
          <td>
            <span class="file-loc" data-copy-text="{safe_copy_text}" title="Click to copy">
              {safe_file_loc}
            </span>
          </td>
          <td class="tool-cell">{safe_tool}</td>
          <td>{safe_message}{suggestion_html}</td>
        </tr>"""

    # Tools list — tool names escape karo
    tools_html = " ".join(f"<span class='tool-tag'>{escape(t)}</span>" for t in tools_used)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>🐺 Lyncus Report — {escape(Path(project_path).name)}</title>
  <style>
    :root {{
      --bg:      #0f172a;
      --surface: #1e293b;
      --border:  #334155;
      --text:    #e2e8f0;
      --muted:   #94a3b8;
      --accent:  #7dd3fc;
      --red:     #ef4444;
      --yellow:  #f59e0b;
      --blue:    #3b82f6;
      --green:   #22c55e;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
      background: var(--bg); color: var(--text);
      padding: 24px; line-height: 1.5;
    }}
    .header {{ display: flex; align-items: center; gap: 16px; margin-bottom: 8px; }}
    .header h1 {{ font-size: 1.5rem; color: var(--accent); }}
    .meta {{ color: var(--muted); font-size: 0.85rem; margin-bottom: 24px; }}
    .meta code {{ background: var(--border); padding: 2px 6px; border-radius: 4px; color: var(--text); }}

    /* Score ring */
    .summary {{ display: flex; gap: 16px; margin-bottom: 24px; flex-wrap: wrap; align-items: flex-start; }}
    .score-ring {{
      width: 100px; height: 100px; border-radius: 50%;
      background: conic-gradient({score_color} {score}%, var(--border) 0%);
      display: flex; align-items: center; justify-content: center;
      position: relative; flex-shrink: 0;
    }}
    .score-inner {{
      width: 76px; height: 76px; border-radius: 50%;
      background: var(--surface);
      display: flex; flex-direction: column;
      align-items: center; justify-content: center;
    }}
    .score-num {{ font-size: 1.5rem; font-weight: bold; color: {score_color}; }}
    .score-label {{ font-size: 0.65rem; color: var(--muted); }}

    /* Stat cards */
    .stat-cards {{ display: flex; gap: 12px; flex-wrap: wrap; }}
    .card {{
      background: var(--surface); border: 1px solid var(--border);
      border-radius: 10px; padding: 14px 20px; min-width: 100px; text-align: center;
    }}
    .card .num {{ font-size: 1.8rem; font-weight: bold; }}
    .card .lbl {{ font-size: 0.75rem; color: var(--muted); margin-top: 2px; }}

    /* Filter buttons */
    .filters {{ display: flex; gap: 8px; margin-bottom: 16px; flex-wrap: wrap; align-items: center; }}
    .filters span {{ color: var(--muted); font-size: 0.85rem; }}
    .filter-btn {{
      padding: 6px 14px; border-radius: 20px; border: 1px solid var(--border);
      background: var(--surface); color: var(--text); cursor: pointer;
      font-size: 0.8rem; transition: all 0.15s;
    }}
    .filter-btn:hover {{ border-color: var(--accent); color: var(--accent); }}
    .filter-btn.active {{ background: var(--accent); color: #0f172a; border-color: var(--accent); font-weight: bold; }}

    /* Search */
    .search-box {{
      padding: 8px 12px; border-radius: 8px;
      border: 1px solid var(--border); background: var(--surface);
      color: var(--text); font-size: 0.85rem; width: 220px;
    }}
    .search-box:focus {{ outline: none; border-color: var(--accent); }}

    /* Table */
    .table-wrap {{ overflow-x: auto; border-radius: 10px; border: 1px solid var(--border); }}
    table {{ width: 100%; border-collapse: collapse; }}
    th {{
      background: var(--border); padding: 10px 14px;
      text-align: left; color: var(--accent);
      font-size: 0.8rem; white-space: nowrap;
      cursor: pointer; user-select: none;
    }}
    th:hover {{ color: var(--text); }}
    td {{ padding: 9px 14px; border-bottom: 1px solid var(--border); font-size: 0.85rem; vertical-align: top; }}
    tr:last-child td {{ border-bottom: none; }}
    tr.problem-row:hover {{ background: rgba(125,211,252,0.04); }}

    .badge {{
      padding: 2px 8px; border-radius: 12px;
      font-size: 0.7rem; font-weight: bold; white-space: nowrap; color: #fff;
    }}
    .cat-badge {{
      background: var(--border); padding: 2px 7px;
      border-radius: 6px; font-size: 0.75rem;
    }}
    .file-loc {{
      color: var(--accent); cursor: pointer; font-family: monospace;
      font-size: 0.78rem; white-space: nowrap;
    }}
    .file-loc:hover {{ text-decoration: underline; }}
    .tool-cell {{ color: var(--muted); font-size: 0.78rem; white-space: nowrap; }}
    .tool-tag {{
      display: inline-block; background: var(--border);
      padding: 2px 8px; border-radius: 4px;
      font-size: 0.75rem; margin: 2px;
    }}

    /* Toast */
    #toast {{
      position: fixed; bottom: 24px; right: 24px;
      background: #1e293b; border: 1px solid var(--accent);
      color: var(--accent); padding: 10px 18px; border-radius: 8px;
      font-size: 0.85rem; opacity: 0; transition: opacity 0.3s;
      pointer-events: none;
    }}
    #toast.show {{ opacity: 1; }}

    /* No results */
    .no-results {{ text-align: center; padding: 40px; color: var(--muted); display: none; }}

    .footer {{ margin-top: 32px; color: var(--muted); font-size: 0.75rem; text-align: center; }}
  </style>
</head>
<body>

<div class="header">
  <span style="font-size:2rem">🐺</span>
  <h1>Lyncus — Code Quality Report</h1>
</div>
<div class="meta">
  <strong>Project:</strong> <code>{escape(project_path)}</code> &nbsp;
  <strong>Language:</strong> <code>{escape(language)}</code> &nbsp;
  <strong>Scan time:</strong> {scan_time:.1f}s &nbsp;
  <strong>Generated:</strong> {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
</div>
<div class="meta" style="margin-top:6px">
  <strong>Tools used:</strong> {tools_html}
</div>

<div class="summary">
  <div class="score-ring" title="Quality Score">
    <div class="score-inner">
      <div class="score-num">{score}</div>
      <div class="score-label">/ 100</div>
    </div>
  </div>
  <div class="stat-cards">
    <div class="card"><div class="num" style="color:var(--red)">{critical}</div><div class="lbl">Critical ❌</div></div>
    <div class="card"><div class="num" style="color:var(--yellow)">{warnings}</div><div class="lbl">Warnings ⚠️</div></div>
    <div class="card"><div class="num" style="color:var(--blue)">{info}</div><div class="lbl">Info ℹ️</div></div>
    <div class="card"><div class="num" style="color:var(--text)">{len(problems)}</div><div class="lbl">Total</div></div>
  </div>
</div>

<div class="filters">
  <span>Filter:</span>
  <button class="filter-btn active" onclick="filterSeverity('all', this)">All ({len(problems)})</button>
  <button class="filter-btn" onclick="filterSeverity('critical', this)">❌ Critical ({critical})</button>
  <button class="filter-btn" onclick="filterSeverity('warning', this)">⚠️ Warning ({warnings})</button>
  <button class="filter-btn" onclick="filterSeverity('info', this)">ℹ️ Info ({info})</button>
  &nbsp;
  <input class="search-box" type="text" placeholder="🔍 Search file, message..." oninput="searchProblems(this.value)">
</div>

<div class="table-wrap">
  <table id="problemTable">
    <thead>
      <tr>
        <th onclick="sortTable(0)">Severity ↕</th>
        <th onclick="sortTable(1)">Category ↕</th>
        <th onclick="sortTable(2)">Location ↕</th>
        <th onclick="sortTable(3)">Tool ↕</th>
        <th>Message</th>
      </tr>
    </thead>
    <tbody id="tableBody">
      {rows_html}
    </tbody>
  </table>
  <div class="no-results" id="noResults">No problems match your filter.</div>
</div>

<div class="footer">
  Generated by <strong>Lyncus v1.0.0</strong> — "Jo dikhta nahi, woh pakad lega" 🐺
</div>

<div id="toast">📋 Copied to clipboard!</div>

<script>
  let currentSeverity = 'all';
  let currentSearch   = '';

  function filterSeverity(sev, btn) {{
    currentSeverity = sev;
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    applyFilters();
  }}

  function searchProblems(val) {{
    currentSearch = val.toLowerCase();
    applyFilters();
  }}

  function applyFilters() {{
    const rows = document.querySelectorAll('.problem-row');
    let visible = 0;
    rows.forEach(row => {{
      const matchSev = currentSeverity === 'all' || row.dataset.severity === currentSeverity;
      const rowText  = row.innerText.toLowerCase();
      const matchSrc = !currentSearch || rowText.includes(currentSearch);
      const show     = matchSev && matchSrc;
      row.style.display = show ? '' : 'none';
      if (show) visible++;
    }});
    document.getElementById('noResults').style.display = visible === 0 ? 'block' : 'none';
  }}

  function sortTable(colIdx) {{
    const tbody = document.getElementById('tableBody');
    const rows  = Array.from(tbody.querySelectorAll('.problem-row'));
    const dir   = tbody.dataset.sortDir === 'asc' ? -1 : 1;
    tbody.dataset.sortDir = dir === 1 ? 'asc' : 'desc';
    rows.sort((a, b) => {{
      const aVal = a.cells[colIdx].innerText.trim();
      const bVal = b.cells[colIdx].innerText.trim();
      return aVal.localeCompare(bVal) * dir;
    }});
    rows.forEach(r => tbody.appendChild(r));
  }}

  function copyToClipboard(text) {{
    navigator.clipboard.writeText(text).then(() => {{
      const toast = document.getElementById('toast');
      toast.classList.add('show');
      setTimeout(() => toast.classList.remove('show'), 2000);
    }});
  }}

  document.querySelectorAll('.file-loc').forEach(element => {{
    element.addEventListener('click', () => copyToClipboard(element.dataset.copyText || ''));
  }});
</script>

</body>
</html>"""

    Path(output_file).write_text(html, encoding="utf-8")
