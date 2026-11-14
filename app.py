"""EchoRadar - The Innovation Connection Engine. Entry point: `streamlit run app.py`."""
import streamlit as st

PAGES = [
    st.Page("pages/0_Home.py", title="Home", icon=":material/hub:", default=True),
    st.Page("pages/1_Innovation_Overview.py", title="Innovation Overview", icon=":material/dashboard:", url_path="Innovation_Overview"),
    st.Page("pages/2_Company_DNA.py", title="Company DNA", icon=":material/fingerprint:", url_path="Company_DNA"),
    st.Page("pages/3_Innovation_Graph.py", title="Innovation Graph", icon=":material/share:", url_path="Innovation_Graph"),
    st.Page("pages/4_Opportunity_Radar.py", title="Opportunity Radar", icon=":material/radar:", url_path="Opportunity_Radar"),
    st.Page("pages/5_Innovation_Blueprint.py", title="Innovation Blueprint", icon=":material/description:", url_path="Innovation_Blueprint"),
    st.Page("pages/6_Evaluation.py", title="Evaluation", icon=":material/fact_check:", url_path="Evaluation"),
    st.Page("pages/7_Staff_View.py", title="Staff View", icon=":material/groups:", url_path="Staff_View"),
]
st.navigation(PAGES).run()
