import os
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="HTML Report Generator - MSU Analytics",
    layout="wide",
    page_icon="📄",
)

st.title("📄 Standalone HTML Report Generator")
st.caption(
    "Generate and download the complete executive HTML analytics package."
)

# --- DATA ARRAYS ---
top_pages_data = [
    ("/", 1),
    ("/robots.txt", 1),
    ("/our-faculty", 1),
    ("/course/btech-in-cloud-computing-and-cyber-security", 1),
    ("/blog/why-skill-based-education-is-important-in-this-era", 1),
    (
        "/events/hospitality-and-tourism-hosts-grooming-and-etiquette-workshop",
        1,
    ),
    (
        "/events/hospitality-and-hotel-management-students-embark-on-ojt-journey",
        1,
    ),
    (
        "/blog/unlocking-the-secrets-to-great-hospitality-a-hotel-management-perspective",
        1,
    ),
    (
        "/events/halloween-at-medhavi-skills-university:-a-spooktacular-showcase-of-creativity-&-coordination",
        1,
    ),
    (
        "/course/diploma-in-computer-science-engineering?utm_source=meta&utm_medium=paid&utm_campaign=cse_diploma",
        1,
    ),
]

top_referrers_data = [
    ("https://www.google.com/", 405),
    ("https://international.msu.edu.in/", 19),
    ("https://msu.edu.in/grievance-redressal", 16),
    ("https://www.msu.edu.in/", 15),
    (
        "https://www.msu.edu.in/school/school-of-indigenous-knowledge-research-and-applications",
        12,
    ),
    ("https://www.msu.edu.in/wise", 11),
    ("http://msu.edu.in/wp-login.php", 9),
    (
        "http://www.msu.edu.in/school/school-of-indigenous-knowledge-research-application.html",
        8,
    ),
    ("android-app://com.google.android.googlequicksearchbox/", 7),
]

# --- HTML ROW GENERATION ---
pages_rows = "".join(
    f"<tr><td style='padding: 8px; border-bottom: 1px solid #eee; word-break: break-all;'>{page}</td>"
    f"<td style='padding: 8px; border-bottom: 1px solid #eee; text-align: right;'><b>{count}</b></td></tr>"
    for page, count in top_pages_data
)

referrers_rows = "".join(
    f"<tr><td style='padding: 8px; border-bottom: 1px solid #eee; word-break: break-all;'>"
    f"<a href='{ref}' target='_blank' style='color: #0066cc; text-decoration: none;'>{ref}</a></td>"
    f"<td style='padding: 8px; border-bottom: 1px solid #eee; text-align: right;'><b>{count}</b></td></tr>"
    for ref, count in top_referrers_data
)

# --- COMPLETE HTML TEMPLATE WITH CLEAN HEADER ---
html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MSU SEO Intelligence Executive Report</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #f8fafc; color: #1e293b; margin: 0; padding: 24px; }}
        .container {{ max-width: 1100px; margin: 0 auto; background: #ffffff; padding: 32px; border-radius: 12px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); }}
        h1 {{ margin-top: 0; color: #0f172a; border-bottom: 2px solid #e2e8f0; padding-bottom: 12px; }}
        .card-grid {{ display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 24px; }}
        .card {{ flex: 1; min-width: 140px; background: #f1f5f9; padding: 14px; border-radius: 8px; border: 1px solid #cbd5e1; text-align: center; }}
        .card-label {{ font-size: 11px; text-transform: uppercase; font-weight: bold; color: #64748b; }}
        .card-val {{ font-size: 22px; font-weight: bold; color: #0f172a; margin-top: 4px; }}
        .flex-tables {{ display: flex; gap: 24px; flex-wrap: wrap; }}
        .table-col {{ flex: 1; min-width: 320px; }}
        table {{ width: 100%; border-collapse: collapse; font-size: 13px; margin-top: 8px; }}
        th {{ background: #f1f5f9; padding: 10px; text-align: left; border-bottom: 2px solid #cbd5e1; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🌐 Latest Server Traffic Snapshot</h1>
        
        <div class="card-grid">
            <div class="card"><div class="card-label">Total Requests</div><div class="card-val">3,570</div></div>
            <div class="card"><div class="card-label">Page Views</div><div class="card-val" style="color: #2563eb;">3,570</div></div>
            <div class="card"><div class="card-label">Unique IPs</div><div class="card-val" style="color: #059669;">1,276</div></div>
            <div class="card"><div class="card-label">Bot Requests</div><div class="card-val" style="color: #d97706;">0</div></div>
            <div class="card"><div class="card-label">Error Count</div><div class="card-val" style="color: #dc2626;">0</div></div>
        </div>

        <div class="flex-tables">
            <div class="table-col">
                <h3>📄 Top Requested Pages</h3>
                <table>
                    <thead><tr><th>Page Path</th><th style="text-align: right;">Views</th></tr></thead>
                    <tbody>{pages_rows}</tbody>
                </table>
            </div>

            <div class="table-col">
                <h3>🔗 Top Referrers</h3>
                <table>
                    <thead><tr><th>Referrer URL</th><th style="text-align: right;">Visits</th></tr></thead>
                    <tbody>{referrers_rows}</tbody>
                </table>
            </div>
        </div>
    </div>
</body>
</html>
"""

output_path = "MSU_Analytics_Report_2026.html"

if st.button("🚀 Re-Generate HTML Report File"):
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    st.success(f"Successfully generated clean report: `{output_path}`")

if os.path.exists(output_path):
    with open(output_path, "rb") as f:
        st.download_button(
            label="📥 Download Clean Standalone HTML Report",
            data=f,
            file_name="MSU_Analytics_Report_2026.html",
            mime="text/html",
        )