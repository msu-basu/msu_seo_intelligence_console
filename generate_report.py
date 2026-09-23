import os
import re
import pandas as pd
import plotly.express as px
import plotly.io as pio
from src.data.loaders import detect_and_load_all

def clean_title(path):
    clean = re.sub(r"^/blog/|^/course/|/$|^/", "", str(path), flags=re.IGNORECASE)
    return clean.replace("-", " ").title()

def categorize_blog(path):
    p = str(path).lower()
    if any(kw in p for kw in ["career", "jobs", "salary", "scope", "placement"]):
        return "Career & Placement Guides"
    elif any(kw in p for kw in ["result", "exam", "cbse", "12th", "10th", "cutoff"]):
        return "Exams & Results"
    elif any(kw in p for kw in ["skills", "courses", "learn", "how-to"]):
        return "Skills & Course Guides"
    else:
        return "General Campus News"

def categorize_course(path):
    p = str(path).lower()
    if any(kw in p for kw in ["bachelor", "btech", "b-tech", "bsc", "bca", "bba"]):
        return "Bachelor (Undergraduate)"
    elif any(kw in p for kw in ["master", "mtech", "msc", "mca", "mba"]):
        return "Master (Postgraduate)"
    elif "diploma" in p:
        return "Diploma"
    elif any(kw in p for kw in ["phd", "doctor"]):
        return "PhD / Doctoral"
    else:
        return "Other Certificate Programs"

def render_plotly_html(fig):
    fig.update_layout(
        autosize=True,
        margin=dict(l=30, r=30, t=40, b=30),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(family="Inter, -apple-system, sans-serif", size=12)
    )
    return pio.to_html(fig, full_html=False, include_plotlyjs=False)

def build_styled_table(df, columns_map):
    if df.empty:
        return "<p class='no-data'>No Data Available</p>"
    formatted_df = df.rename(columns=columns_map) if columns_map else df.copy()
    html = "<div class='table-wrap'><table class='styled-table'><thead><tr>"
    for col in formatted_df.columns:
        html += f"<th>{col}</th>"
    html += "</tr></thead><tbody>"
    for _, row in formatted_df.iterrows():
        html += "<tr>"
        for val in row:
            formatted_val = f"{val:,.0f}" if isinstance(val, (int, float)) else str(val)
            html += f"<td>{formatted_val}</td>"
        html += "</tr>"
    html += "</tbody></table></div>"
    return html

def build_html_report():
    datasets = detect_and_load_all()
    df_blog = datasets.get("blog", pd.DataFrame())
    df_course = datasets.get("course", pd.DataFrame())
    df_device = datasets.get("device", pd.DataFrame())

    # --- 1. BLOG ---
    if not df_blog.empty:
        b_df = df_blog.copy()
        p_col = "Page path and screen class" if "Page path and screen class" in b_df.columns else b_df.columns[0]
        v_col = next((c for c in ["Views", "Event count"] if c in b_df.columns), b_df.columns[1])
        u_col = next((c for c in ["Active users", "Users"] if c in b_df.columns), b_df.columns[1])
        
        b_df = b_df[~b_df[p_col].isin(["/blog", "/blog/", "/", "(not set)"])].copy()
        b_df["Views"] = pd.to_numeric(b_df[v_col], errors='coerce').fillna(0)
        b_df["Active Users"] = pd.to_numeric(b_df[u_col], errors='coerce').fillna(0)
        b_df["Category"] = b_df[p_col].apply(categorize_blog)
        b_df["Title"] = b_df[p_col].apply(clean_title)

        tot_blog_views = int(b_df["Views"].sum())
        tot_blog_urls = b_df["Title"].nunique()

        b_cat = b_df.groupby("Category")["Views"].sum().reset_index()
        fig_b_pie = px.pie(b_cat, values="Views", names="Category", title="Blog Views Share", hole=0.4)
        chart_b_pie = render_plotly_html(fig_b_pie)

        top10_b = b_df.groupby("Title")["Views"].sum().reset_index().sort_values(by="Views", ascending=True).tail(10)
        fig_b_top = px.bar(top10_b, x="Views", y="Title", orientation="h", title="Top 10 Blog Articles")
        chart_b_top = render_plotly_html(fig_b_top)

        blog_summary = b_df.groupby(["Title", "Category"])[["Views", "Active Users"]].sum().reset_index().sort_values(by="Views", ascending=False)
        blog_table_html = build_styled_table(blog_summary, {"Title": "Blog Article Title", "Category": "Category", "Views": "Total Views", "Active Users": "Active Readers"})
    else:
        tot_blog_views = tot_blog_urls = 0
        chart_b_pie = chart_b_top = blog_table_html = "<p class='no-data'>No Blog Data</p>"

    # --- 2. COURSE ---
    if not df_course.empty:
        c_df = df_course.copy()
        cp_col = "Page path and screen class" if "Page path and screen class" in c_df.columns else c_df.columns[0]
        cv_col = next((c for c in ["Views", "Event count"] if c in c_df.columns), c_df.columns[1])
        cu_col = next((c for c in ["Active users", "Users"] if c in c_df.columns), c_df.columns[1])
        ce_col = next((c for c in ["Key events", "Conversions"] if c in c_df.columns), cv_col)

        c_df = c_df[~c_df[cp_col].isin(["/", "(not set)", ""])].copy()
        c_df["Views"] = pd.to_numeric(c_df[cv_col], errors='coerce').fillna(0)
        c_df["Active Users"] = pd.to_numeric(c_df[cu_col], errors='coerce').fillna(0)
        c_df["Leads"] = pd.to_numeric(c_df[ce_col], errors='coerce').fillna(0)
        c_df["Degree Level"] = c_df[cp_col].apply(categorize_course)
        c_df["Title"] = c_df[cp_col].apply(clean_title)

        tot_course_views = int(c_df["Views"].sum())
        tot_course_leads = int(c_df["Leads"].sum())
        tot_course_urls = c_df["Title"].nunique()

        c_deg = c_df.groupby("Degree Level")["Views"].sum().reset_index()
        fig_c_pie = px.pie(c_deg, values="Views", names="Degree Level", title="Program Demand", hole=0.4)
        chart_c_pie = render_plotly_html(fig_c_pie)

        top10_c = c_df.groupby("Title")["Views"].sum().reset_index().sort_values(by="Views", ascending=True).tail(10)
        fig_c_top = px.bar(top10_c, x="Views", y="Title", orientation="h", title="Top Demanded Programs")
        chart_c_top = render_plotly_html(fig_c_top)

        course_summary = c_df.groupby(["Title", "Degree Level"])[["Views", "Active Users", "Leads"]].sum().reset_index().sort_values(by="Views", ascending=False)
        course_table_html = build_styled_table(course_summary, {"Title": "Course Title", "Degree Level": "Degree Level", "Views": "Page Views", "Active Users": "Applicants", "Leads": "Leads"})
    else:
        tot_course_views = tot_course_leads = tot_course_urls = 0
        chart_c_pie = chart_c_top = course_table_html = "<p class='no-data'>No Course Data</p>"

    # --- 3. DEVICE ---
    if not df_device.empty:
        dev_col = "Device category" if "Device category" in df_device.columns else df_device.columns[0]
        val_col = "Active users" if "Active users" in df_device.columns else df_device.columns[1]
        fig_dev = px.pie(df_device, values=val_col, names=dev_col, title="Device Distribution", hole=0.45)
        chart_dev = render_plotly_html(fig_dev)
    else:
        chart_dev = "<p class='no-data'>No Device Data</p>"

    # FINAL HTML BUILD
    full_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MSU SEO Console</title>
    <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
    <style>
        :root {{ --bg: #f8fafc; --sidebar: #0f172a; --text: #1e293b; --border: #e2e8f0; }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        html, body {{ min-height: 100%; background: var(--bg); color: var(--text); font-family: sans-serif; }}
        .wrapper {{ display: flex; min-height: 100vh; }}
        .sidebar {{ width: 240px; background: var(--sidebar); color: #fff; flex-shrink: 0; }}
        .sidebar-brand {{ padding: 20px; font-weight: bold; color: #38bdf8; border-bottom: 1px solid #1e293b; }}
        .nav-item {{ padding: 12px 20px; cursor: pointer; color: #94a3b8; font-size: 14px; }}
        .nav-item.active {{ background: #1e293b; color: #fff; border-left: 3px solid #38bdf8; }}
        .main-panel {{ flex-grow: 1; padding: 30px; overflow-y: auto; }}
        .tab-content {{ display: none; }}
        .tab-content.active {{ display: block; }}
        .kpi-row {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 15px; margin-bottom: 20px; }}
        .kpi-card {{ background: #fff; padding: 15px; border-radius: 8px; border: 1px solid var(--border); }}
        .kpi-card .label {{ font-size: 11px; color: #64748b; font-weight: bold; }}
        .kpi-card .value {{ font-size: 22px; font-weight: bold; margin-top: 5px; }}
        .grid-2 {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(380px, 1fr)); gap: 20px; margin-bottom: 20px; }}
        .card {{ background: #fff; border-radius: 8px; border: 1px solid var(--border); padding: 20px; }}
        .table-wrap {{ overflow-x: auto; max-height: 400px; overflow-y: auto; }}
        .styled-table {{ width: 100%; border-collapse: collapse; font-size: 13px; text-align: left; }}
        .styled-table th {{ background: #f1f5f9; padding: 10px; position: sticky; top: 0; }}
        .styled-table td {{ padding: 10px; border-bottom: 1px solid var(--border); }}
    </style>
</head>
<body>
    <div class="wrapper">
        <aside class="sidebar">
            <div class="sidebar-brand">🎓 MSU Console</div>
            <div class="nav-item active" onclick="switchTab('overview', this)">📌 Overview</div>
            <div class="nav-item" onclick="switchTab('blog', this)">📝 Blog Intelligence</div>
            <div class="nav-item" onclick="switchTab('course', this)">🎓 Course Intelligence</div>
            <div class="nav-item" onclick="switchTab('device', this)">📱 Device Attribution</div>
        </aside>
        <main class="main-panel">
            <section id="overview" class="tab-content active">
                <h2>Executive Overview</h2>
                <div class="kpi-row">
                    <div class="kpi-card"><div class="label">BLOG ARTICLES</div><div class="value">{tot_blog_urls:,}</div></div>
                    <div class="kpi-card"><div class="label">BLOG VIEWS</div><div class="value">{tot_blog_views:,}</div></div>
                    <div class="kpi-card"><div class="label">COURSE PAGES</div><div class="value">{tot_course_urls:,}</div></div>
                    <div class="kpi-card"><div class="label">COURSE VIEWS</div><div class="value">{tot_course_views:,}</div></div>
                    <div class="kpi-card"><div class="label">ADMISSION LEADS</div><div class="value">{tot_course_leads:,}</div></div>
                </div>
                <div class="grid-2"><div class="card">{chart_b_pie}</div><div class="card">{chart_c_pie}</div></div>
            </section>
            <section id="blog" class="tab-content">
                <h2>Blog Performance</h2>
                <div class="grid-2"><div class="card">{chart_b_pie}</div><div class="card">{chart_b_top}</div></div>
                <div class="card">{blog_table_html}</div>
            </section>
            <section id="course" class="tab-content">
                <h2>Course Performance</h2>
                <div class="grid-2"><div class="card">{chart_c_pie}</div><div class="card">{chart_c_top}</div></div>
                <div class="card">{course_table_html}</div>
            </section>
            <section id="device" class="tab-content">
                <h2>Device Breakdown</h2>
                <div class="card">{chart_dev}</div>
            </section>
        </main>
    </div>
    <script>
        function switchTab(tabId, el) {{
            document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
            document.getElementById(tabId).classList.add('active');
            el.classList.add('active');
            setTimeout(() => {{
                if (window.Plotly) {{
                    document.getElementById(tabId).querySelectorAll('.js-plotly-plot').forEach(c => Plotly.Plots.resize(c));
                }}
            }}, 50);
        }}
    </script>
</body>
</html>"""
    
    output_filename = "MSU_Analytics_Report_2026.html"
    with open(output_filename, "w", encoding="utf-8") as f:
        f.write(full_html)
    print(f"✅ Standalone HTML Report successfully generated: {os.path.abspath(output_filename)}")

if __name__ == "__main__":
    build_html_report()