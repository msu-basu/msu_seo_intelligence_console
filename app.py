import pandas as pd
import plotly.express as px
import streamlit as st

# Page configuration
st.set_page_config(
    page_title="Analytics Dashboard", page_icon="📊", layout="wide"
)

st.title("📊 Platform & Course Intelligence Dashboard")


# -----------------------------------------------------------------------------
# 1. Separate Data Loaders (Fixes Data Duplication)
# -----------------------------------------------------------------------------
@st.cache_data
def load_course_data():
    """Loads dataset specific to Course Intelligence."""
    try:
        return pd.read_csv("course_data.csv")
    except FileNotFoundError:
        # Fallback sample dataset for testing
        return pd.DataFrame(
            {
                "Course ID": ["C101", "C102", "C103", "C104"],
                "Course Name": [
                    "Python Basics",
                    "Data Science 101",
                    "AI Essentials",
                    "Web Dev Bootcamp",
                ],
                "Enrolled Students": [1200, 850, 950, 1100],
                "Completion Rate (%)": [88, 74, 81, 69],
            }
        )


@st.cache_data
def load_user_analytics_data():
    """Loads dataset specific to User Devices and Geographic Data."""
    try:
        return pd.read_csv("user_analytics.csv")
    except FileNotFoundError:
        # Fallback sample dataset for testing
        return pd.DataFrame(
            {
                "user_id": range(1, 101),
                "device_type": [
                    "Mobile",
                    "Desktop",
                    "Tablet",
                    "Mobile",
                    "Desktop",
                ]
                * 20,
                "country_code": ["USA", "IND", "GBR", "CAN", "DEU"] * 20,
                "city": [
                    "New York",
                    "Mumbai",
                    "London",
                    "Toronto",
                    "Berlin",
                ]
                * 20,
            }
        )


course_df = load_course_data()
analytics_df = load_user_analytics_data()

# -----------------------------------------------------------------------------
# 2. Course Intelligence Section
# -----------------------------------------------------------------------------
st.header("📚 Course Intelligence")
col_c1, col_c2 = st.columns([3, 2])

with col_c1:
    st.subheader("Course Overview")
    st.dataframe(course_df, use_container_width=True)

with col_c2:
    if (
        "Course Name" in course_df.columns
        and "Enrolled Students" in course_df.columns
    ):
        fig_course = px.bar(
            course_df,
            x="Course Name",
            y="Enrolled Students",
            title="Enrollment by Course",
            color="Enrolled Students",
        )
        st.plotly_chart(fig_course, use_container_width=True)

st.divider()

# -----------------------------------------------------------------------------
# 3. Device Analytics Section
# -----------------------------------------------------------------------------
st.header("📱 Device Analytics")

if "device_type" in analytics_df.columns:
    device_counts = analytics_df["device_type"].value_counts().reset_index()
    device_counts.columns = ["Device Type", "User Count"]

    col_d1, col_d2 = st.columns(2)

    with col_d1:
        fig_device_pie = px.pie(
            device_counts,
            values="User Count",
            names="Device Type",
            title="User Distribution by Device",
            hole=0.4,
        )
        st.plotly_chart(fig_device_pie, use_container_width=True)

    with col_d2:
        fig_device_bar = px.bar(
            device_counts,
            x="Device Type",
            y="User Count",
            title="Device Count Breakdown",
            color="Device Type",
        )
        st.plotly_chart(fig_device_bar, use_container_width=True)

st.divider()

# -----------------------------------------------------------------------------
# 4. Geographic Intelligence Section (Placed directly below Device Analytics)
# -----------------------------------------------------------------------------
st.header("🌍 Geographic Intelligence")

col_g1, col_g2 = st.columns(2)

with col_g1:
    if "country_code" in analytics_df.columns:
        geo_country = analytics_df["country_code"].value_counts().reset_index()
        geo_country.columns = ["Country Code", "Users"]

        fig_map = px.choropleth(
            geo_country,
            locations="Country Code",
            color="Users",
            hover_name="Country Code",
            color_continuous_scale=px.colors.sequential.Plasma,
            title="Global User Distribution",
        )
        st.plotly_chart(fig_map, use_container_width=True)

with col_g2:
    if "city" in analytics_df.columns:
        geo_city = (
            analytics_df["city"].value_counts().head(10).reset_index()
        )
        geo_city.columns = ["City", "Users"]

        fig_city = px.bar(
            geo_city,
            x="Users",
            y="City",
            orientation="h",
            title="Top 10 Cities by User Count",
            color="Users",
        )
        fig_city.update_layout(yaxis=dict(autorange="reversed"))
        st.plotly_chart(fig_city, use_container_width=True)