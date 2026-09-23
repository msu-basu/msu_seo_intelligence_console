import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.io as pio
import re
from src.data.loaders import detect_and_load_all

st.set_page_config(page_title="Generate HTML SEO Console", layout="wide")
st.title("📄 Multi-Page Offline HTML Report Generator")
st.caption("Generate a standalone, interactive HTML analytics console based strictly on GA4 Blog, Course, and Device data.")

# Load only available datasets (Blog, Course, Device)
datasets = detect_and_load_all()
df_blog = datasets.get("blog", pd.DataFrame())
df_course = datasets.get("course", pd.DataFrame())
df_device = datasets.get("device", pd.DataFrame())

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
    """Converts Plotly figure into responsive HTML div string without outer wrappers."""
    fig.update_layout(
        autosize=True,
        margin=dict(l=30, r=30, t=40, b=30),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(family="Inter, -apple-system, sans-serif", size=12)
    )
    return pio.to_html(fig, full_html=False, include_plotlyjs=False)

def build_styled_table(df, columns_map):
    """Formats Pandas DataFrames into styled HTML tables with scroll containers."""
    if df.empty:
        return "<p class='no-data'>No Data Available</p>"
    
    formatted_df = df.copy()
    if columns_map:
        formatted_df = formatted_df.rename(columns=columns_map)
        
    html = "<div class='table-wrap'><table class='styled-table'><thead><tr>"
    for col in formatted_df.columns:
        html += f"<th>{col}</th>"
    html += "</tr></thead><tbody>"
    
    for _, row in formatted_df.iterrows():
        html += "<tr>"
        for val in row:
            if isinstance(val, (int, float)):
                formatted_val = f"{val:,.0f}" if isinstance(val, int) or (hasattr(val, 'is_integer') and val.is_integer()) else f"{val:,.2f}"
            else:
                formatted_val = str(val)
            html += f"<td>{formatted_val}</td>"
        html += "</tr>"
    html += "</tbody></table></div>"
    return html

def generate_unified_report():
    # --- 1. BLOG PROCESSING ---
    if not df_blog.empty:
        b_df = df_blog.copy()
        p_col = "Page path and screen class" if "Page path and screen class" in b_df.columns else b_df.columns[0]
        v_col = next((c for c in ["Views", "Event count"] if c in b_df.columns), b_df.columns[1])
        u_col = next((c for c in ["Active users", "Users"] if c in b_df.columns), b_df.columns[1])
        s_col = next((c for c in ["Sessions"] if c in b_df.columns), v_col)

        b_df = b_df[~b_df[p_col].isin(["/blog", "/blog/", "/", "(not set)"])].copy()
        b_df["Views"] = pd.to_numeric(b_df[v_col], errors='coerce').fillna(0)
        b_df["Active Users"] = pd.to_numeric(b_df[u_col], errors='coerce').fillna(0)
        b_df["Sessions"] = pd.to_numeric(b_df[s_col], errors='coerce').fillna(0)
        b_df["Category"] = b_df[p_col].apply(categorize_blog)
        b_df["Title"] = b_df[p_col].apply(clean_title)

        tot_blog_views = int(b_df["Views"].sum())
        tot_blog_urls = b_df["Title"].nunique()

        b_cat = b_df.groupby("Category")["Views"].sum().reset_index()
        fig_b_pie = px.pie(b_cat, values="Views", names="Category", title="Blog Views Share by Category", hole=0.4, color_discrete_sequence=px.colors.qualitative.Set2)
        chart_b_pie = render_plotly_html(fig_b_pie)

        top10_b = b_df.groupby("Title")["Views"].sum().reset_index().sort_values(by="Views", ascending=True).tail(10)
        fig_b_top = px.bar(top10_b, x="Views", y="Title", orientation="h", title="Top 10 Most Read Blog Articles", color_discrete_sequence=["#2563eb"])
        chart_b_top = render_plotly_html(fig_b_top)

        blog_summary = b_df.groupby(["Title", "Category"])[["Views", "Sessions", "Active Users"]].sum().reset_index().sort_values(by="Views", ascending=False)
        blog_table_html = build_styled_table(blog_summary, {"Title": "Blog Article Title", "Category": "Category", "Views": "Total Views", "Sessions": "Sessions", "Active Users": "Active Readers"})
    else:
        tot_blog_views = tot_blog_urls = 0
        chart_b_pie = chart_b_top = blog_table_html = "<p class='no-data'>No Blog Data Loaded</p>"

    # --- 2. COURSE PROCESSING ---
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
        fig_c_pie = px.pie(c_deg, values="Views", names="Degree Level", title="Program Demand Share", hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
        chart_c_pie = render_plotly_html(fig_c_pie)

        top10_c = c_df.groupby("Title")["Views"].sum().reset_index().sort_values(by="Views", ascending=True).tail(10)
        fig_c_top = px.bar(top10_c, x="Views", y="Title", orientation="h", title="Top Demanded Programs", color_discrete_sequence=["#0d9488"])
        chart_c_top = render_plotly_html(fig_c_top)

        course_summary = c_df.groupby(["Title", "Degree Level"])[["Views", "Active Users", "Leads"]].sum().reset_index().sort_values(by="Views", ascending=False)
        course_table_html = build_styled_table(course_summary, {"Title": "Course Title", "Degree Level": "Degree Level", "Views": "Page Views", "Active Users": "Applicants", "Leads": "Lead Conversions"})
    else:
        tot_course_views = tot_course_leads = tot_course_urls = 0
        chart_c_pie = chart_c_top = course_table_html = "<p class='no-data'>No Course Data Loaded</p>"

    # --- 3. DEVICE SPLIT ---
    if not df_device.empty:
        dev_col = "Device category" if "Device category" in df_device.columns else df_device.columns[0]
        val_col = "Active users" if "Active users" in df_device.columns else df_device.columns[1]
        fig_dev = px.pie(df_device, values=val_col, names=dev_col, title="Reader Share by Device Type", hole=0.45)
        chart_dev = render_plotly_html(fig_dev)
    else:
        chart_dev = "<p class='no-data'>No Device Data Loaded</p>"

    # CLEAN HTML TEMPLATE (WITHOUT GSC REFERENCES)
    full_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MSU SEO & Traffic Intelligence Console</title>
    <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
    <style>
        :root {{
            --bg-main: #f8fafc;
            --sidebar-bg: #0f172a;
            --text-main: #1e293b;
            --text-muted: #64748b;
            --accent: #2563eb;
            --border: #e2e8f0;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        
        html, body {{
            min-height: 100%;
            background: var(--bg-main);
            color: var(--text-main);
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        }}
        
        .wrapper {{
            display: flex;
            min-height: 100vh;
            width: 100%;
        }}
        
        .sidebar {{
            width: 250px;
            background: var(--sidebar-bg);
            color: #fff;
            flex-shrink: 0;
            display: flex;
            flex-direction: column;
        }}
        .sidebar-brand {{
            padding: 20px;
            font-size: 16px;
            font-weight: 700;
            color: #38bdf8;
            border-bottom: 1px solid #1e293b;
        }}
        .nav-list {{ list-style: none; padding: 10px 0; }}
        .nav-item {{
            padding: 12px 20px;
            cursor: pointer;
            font-size: 14px;
            color: #94a3b8;
            font-weight: 500;
            border-left: 3px solid transparent;
            transition: all 0.2s ease;
        }}
        .nav-item:hover, .nav-item.active {{
            background: #1e293b;
            color: #ffffff;
            border-left-color: #38bdf8;
        }}
        
        .main-panel {{
            flex-grow: 1;
            padding: 30px;
            overflow-y: auto;
        }}
        .tab-content {{ display: none; }}
        .tab-content.active {{ display: block; }}
        
        .page-title {{ font-size: 22px; font-weight: 700; color: #0f172a; margin-bottom: 5px; }}
        .page-subtitle {{ font-size: 13px; color: var(--text-muted); margin-bottom: 20px; }}
        
        .kpi-row {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 15px;
            margin-bottom: 25px;
        }}
        .kpi-card {{
            background: #fff;
            padding: 18px;
            border-radius: 8px;
            border: 1px solid var(--border);
            box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        }}
        .kpi-card .label {{ font-size: 11px; font-weight: 600; color: var(--text-muted); text-transform: uppercase; }}
        .kpi-card .value {{ font-size: 24px; font-weight: 700; color: #0f172a; margin-top: 4px; }}
        
        .grid-2 {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap: 20px; margin-bottom: 25px; }}
        .card {{
            background: #fff;
            border-radius: 8px;
            border: 1px solid var(--border);
            padding: 20px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        }}
        
        .table-wrap {{ overflow-x: auto; max-height: 450px; overflow-y: auto; margin-top: 10px; }}
        .styled-table {{ width: 100%; border-collapse: collapse; text-align: left; font-size: 13px; }}
        .styled-table th {{
            background: #f1f5f9;
            color: #334155;
            font-weight: 600;
            padding: 10px 12px;
            position: sticky;
            top: 0;
            border-bottom: 2px solid var(--border);
        }}
        .styled-table td {{ padding: 10px 12px; border-bottom: 1px solid var(--border); color: #334155; }}
        .styled-table tbody tr:hover {{ background: #f8fafc; }}
        .no-data {{ color: var(--text-muted); font-style: italic; padding: 10px 0; }}
        
        .roadmap-list li {{ padding: 10px 0; border-bottom: 1px solid var(--border); font-size: 14px; line-height: 1.5; }}
    </style>
</head>
<body>

    <div class="wrapper">
        <aside class="sidebar">
            <div class="sidebar-brand">🎓 MSU SEO Console</div>
            <ul class="nav-list">
                <li class="nav-item active" onclick="switchTab('overview', this)">📌 Executive Summary</li>
                <li class="nav-item" onclick="switchTab('blog', this)">📝 Blog Intelligence (~320)</li>
                <li class="nav-item" onclick="switchTab('course', this)">🎓 Course Intelligence (~100)</li>
                <li class="nav-item" onclick="switchTab('device', this)">📱 Device Attribution</li>
                <li class="nav-item" onclick="switchTab('roadmap', this)">🎯 SEO Action Roadmap</li>
            </ul>
        </aside>

        <main class="main-panel">

            <!-- TAB 1: OVERVIEW -->
            <section id="overview" class="tab-content active">
                <div class="page-title">Executive Summary</div>
                <div class="page-subtitle">Overview of traffic acquisition, blog inventory, course pages, and applicant leads.</div>
                
                <div class="kpi-row">
                    <div class="kpi-card"><div class="label">Blog Articles</div><div class="value">{tot_blog_urls:,}</div></div>
                    <div class="kpi-card"><div class="label">Blog Traffic Views</div><div class="value">{tot_blog_views:,}</div></div>
                    <div class="kpi-card"><div class="label">Course Pages</div><div class="value">{tot_course_urls:,}</div></div>
                    <div class="kpi-card"><div class="label">Course Views</div><div class="value">{tot_course_views:,}</div></div>
                    <div class="kpi-card"><div class="label">Admissions Leads</div><div class="value">{tot_course_leads:,}</div></div>
                </div>

                <div class="grid-2">
                    <div class="card">{chart_b_pie}</div>
                    <div class="card">{chart_c_pie}</div>
                </div>
            </section>

            <!-- TAB 2: BLOG -->
            <section id="blog" class="tab-content">
                <div class="page-title">Blog Intelligence Console (~320 URLs)</div>
                <div class="page-subtitle">Article categorization and performance metrics.</div>
                <div class="grid-2">
                    <div class="card">{chart_b_pie}</div>
                    <div class="card">{chart_b_top}</div>
                </div>
                <div class="card">
                    <h3 style="margin-bottom: 10px;">📋 Blog Directory Performance</h3>
                    {blog_table_html}
                </div>
            </section>

            <!-- TAB 3: COURSE -->
            <section id="course" class="tab-content">
                <div class="page-title">Academic Course Intelligence (~100 URLs)</div>
                <div class="page-subtitle">Demand breakdown across degree levels.</div>
                <div class="grid-2">
                    <div class="card">{chart_c_pie}</div>
                    <div class="card">{chart_c_top}</div>
                </div>
                <div class="card">
                    <h3 style="margin-bottom: 10px;">📋 Academic Course Directory</h3>
                    {course_table_html}
                </div>
            </section>

            <!-- TAB 4: DEVICE -->
            <section id="device" class="tab-content">
                <div class="page-title">Device Attribution</div>
                <div class="page-subtitle">Visitor distribution by mobile, desktop, and tablet.</div>
                <div class="grid-2">
                    <div class="card">{chart_dev}</div>
                </div>
            </section>

            <!-- TAB 5: ROADMAP -->
            <section id="roadmap" class="tab-content">
                <div class="page-title">SEO Action Roadmap</div>
                <div class="page-subtitle">Prioritized technical & content strategy recommendations.</div>
                <div class="card">
                    <ul class="roadmap-list">
                        <li><strong>P1 - Meta & Title Tag Refresh:</strong> Update title tags on low-performing blogs sitting on Google Page 2 to target high-intent year modifiers ("2026").</li>
                        <li><strong>P1 - Mobile Lead CRO:</strong> Add sticky inquiry buttons on top mobile Bachelor & Master course pages.</li>
                        <li><strong>P2 - Internal Linking:</strong> Contextually link high-traffic career blogs to relevant degree pages to boost overall authority.</li>
                    </ul>
                </div>
            </section>

        </main>
    </div>

    <script>
        function switchTab(tabId, tabElement) {{
            document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
            
            const activeTab = document.getElementById(tabId);
            activeTab.classList.add('active');
            tabElement.classList.add('active');

            setTimeout(() => {{
                if (window.Plotly) {{
                    activeTab.querySelectorAll('.js-plotly-plot').forEach(chart => {{
                        Plotly.Plots.resize(chart);
                    }});
                }}
            }}, 50);
        }}
    </script>
</body>
</html>"""
    return full_html

# STREAMLIT UI RENDER
html_data = generate_unified_report()

st.subheader("Preview & Export Console")
st.download_button(
    label="📥 Download Clean HTML Console (GA4 Only)",
    data=html_data,
    file_name="MSU_Analytics_Report_2026.html",
    mime="text/html",
    type="primary"
)

st.markdown("---")
st.components.v1.html(html_data, height=850, scrolling=True)