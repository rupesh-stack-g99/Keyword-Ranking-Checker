import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="GSC Keyword Rank Tracker", page_icon="🔍", layout="wide"
)

st.title("🔍 Google Search Console Keyword Rank Tracker")
st.write(
    "Query official keyword performance metrics directly from Search Console."
)


# --- 1. Authenticate with Google Search Console API ---
@st.cache_resource
def get_gsc_service():
    """Builds and caches the GSC API service object using Streamlit secrets."""
    try:
        credentials_info = st.secrets["gcp_service_account"]
        credentials = service_account.Credentials.from_service_account_info(
            credentials_info,
            scopes=["https://www.googleapis.com/auth/webmasters.readonly"],
        )
        service = build("searchconsole", "v1", credentials=credentials)
        return service
    except Exception as e:
        st.error(f"Failed to authenticate: {e}")
        return None


service = get_gsc_service()

# --- 2. Streamlit Sidebar Controls ---
st.sidebar.header("Query Parameters")

site_url = st.sidebar.text_input(
    "GSC Site URL (Property)",
    value="https://example.com/",
    help="Must match your verified property in GSC exact URL or sc-domain:domain.com",
)

col1, col2 = st.sidebar.columns(2)
today = datetime.date.today()
start_date = col1.date_input("Start Date", today - datetime.timedelta(days=30))
end_date = col2.date_input("End Date", today - datetime.timedelta(days=2))

dimensions = st.sidebar.multiselect(
    "Group By Dimensions",
    options=["query", "page", "country", "device", "date"],
    default=["query"],
)

row_limit = st.sidebar.slider("Max Results", 10, 5000, 100)

keyword_filter = st.sidebar.text_input(
    "Filter Keyword (Optional)",
    value="",
    help="Filter results for specific keywords containing this string",
)

# --- 3. Query Processing Functions ---


def fetch_gsc_data(site, start, end, dims, limit, kw_filter):
    """Executes the request against the Google Search Console API."""
    body = {
        "startDate": str(start),
        "endDate": str(end),
        "dimensions": dims,
        "rowLimit": limit,
    }

    if kw_filter:
        body["dimensionFilterGroups"] = [
            {
                "filters": [
                    {
                        "dimension": "query",
                        "operator": "contains",
                        "expression": kw_filter,
                    }
                ]
            }
        ]

    try:
        response = (
            service.searchanalytics().query(siteUrl=site, body=body).execute()
        )
        return response.get("rows", [])
    except Exception as e:
        st.error(f"API Error: {e}")
        return None


# --- 4. Main Page Application Logic ---
if st.button("Fetch Rankings"):
    if not service:
        st.stop()

    with st.spinner("Querying Google Search Console..."):
        raw_rows = fetch_gsc_data(
            site_url, start_date, end_date, dimensions, row_limit, keyword_filter
        )

    if raw_rows:
        parsed_data = []
        for r in raw_rows:
            entry = {}
            for idx, dim in enumerate(dimensions):
                entry[dim.capitalize()] = r["keys"][idx]

            entry["Clicks"] = r["clicks"]
            entry["Impressions"] = r["impressions"]
            entry["CTR (%)"] = round(r["ctr"] * 100, 2)
            entry["Avg Rank"] = round(r["position"], 2)

            parsed_data.append(entry)

        df = pd.DataFrame(parsed_data)

        # Overview Metrics
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Clicks", f"{df['Clicks'].sum():,}")
        m2.metric("Total Impressions", f"{df['Impressions'].sum():,}")
        m3.metric(
            "Avg CTR",
            f"{round((df['Clicks'].sum() / df['Impressions'].sum()) * 100, 2)}%",
        )
        m4.metric("Avg Position", round(df["Avg Rank"].mean(), 2))

        st.subheader("Data Table")
        st.dataframe(df, use_container_width=True)

        # Download option
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Download CSV",
            data=csv,
            file_name=f"gsc_rankings_{start_date}_to_{end_date}.csv",
            mime="text/csv",
        )
    else:
        st.warning(
            "No data found for the selected parameters or permission is missing for this URL."
        )
