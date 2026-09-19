import streamlit as st
import pandas as pd
import tempfile
import os
from landxml_tpdm_validator import (
    LandXMLGeometryParser,
    ComprehensiveTPDMValidator,
    TPDM_STANDARDS,
)

# Page Configuration
st.set_page_config(
    page_title="Hong Kong TPDM Road Design Validator",
    page_icon="🛣️",
    layout="wide"
)

st.title("🛣️ Hong Kong TPDM Road Geometric Compliance Web App")
st.markdown("""
Upload one or multiple **LandXML (`.xml`)** road alignment files. 
The system parses horizontal elements (`CoordGeom`), profiles (`Profile`), and checks compliance against **TPDM Volume 2 Chapter 3**.
""")

# Sidebar: Configuration
st.sidebar.header("⚙️ Design Parameters")
speed_choice = st.sidebar.selectbox(
    "Design Speed (km/h):",
    options=[50, 60, 70, 80, 100],
    index=0,
    help="Select the design speed corresponding to your road classification in TPDM."
)

std = TPDM_STANDARDS[speed_choice]
st.sidebar.info(f"**Road Class:** {std['road_class_desc']}")

with st.sidebar.expander("📋 View Active TPDM Limits"):
    st.write(f"- **Min Radius (Abs / Des):** {std['min_radius_absolute_m']}m / {std['min_radius_desirable_m']}m")
    st.write(f"- **Min Spiral Transition:** {std['min_transition_length_m']}m")
    st.write(f"- **Min Horiz. Curve Length:** {std['min_horizontal_curve_length_m']}m")
    st.write(f"- **Max Gradient (Abs / Des):** {std['max_gradient_absolute_pct']}% / {std['max_gradient_desirable_pct']}%")
    st.write(f"- **Min Drainage Gradient:** {std['min_gradient_drainage_pct']}%")
    st.write(f"- **Crest K (Abs / Des):** {std['min_crest_k_absolute']} / {std['min_crest_k_desirable']}")
    st.write(f"- **Sag K (Abs / Des):** {std['min_sag_k_absolute']} / {std['min_sag_k_desirable']}")
    st.write(f"- **Min Vertical Curve Length:** {std['min_vertical_curve_length_m']}m")
    st.write(f"- **Flat Spot Drainage Hazard:** K > {std['drainage_risk_k_threshold']}")

# File Uploader
uploaded_files = st.file_uploader(
    "Upload LandXML alignment files (.xml):", 
    type=["xml", "html", "xhtml"],
    accept_multiple_files=True
)

if uploaded_files:
    validator = ComprehensiveTPDMValidator(speed_choice)
    
    for uploaded_file in uploaded_files:
        st.subheader(f"📄 Audit File: `{uploaded_file.name}`")
        
        # Save uploaded buffer temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xml") as tmp:
            tmp.write(uploaded_file.getvalue())
            tmp_path = tmp.name

        try:
            parser = LandXMLGeometryParser(tmp_path)
            alignments = parser.extract_alignments()
        except Exception as e:
            st.error(f"Failed to parse XML file: {e}")
            os.remove(tmp_path)
            continue
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

        if not alignments:
            st.warning("No `<Alignment>` elements found in this LandXML file.")
            continue

        # Run validation
        all_issues = []
        for align in alignments:
            issues = validator.validate_alignment(align)
            all_issues.extend(issues)

        # Overview Metrics
        col1, col2, col3, col4 = st.columns(4)
        total_align = len(alignments)
        total_issues = len(all_issues)
        critical_cnt = sum(1 for x in all_issues if "CRITICAL" in x["severity"])
        drainage_cnt = sum(1 for x in all_issues if "DRAINAGE" in x["severity"])
        warning_cnt = total_issues - critical_cnt - drainage_cnt

        col1.metric("Alignments Parsed", total_align)
        col2.metric("Critical Non-Compliances", critical_cnt, delta=None if critical_cnt == 0 else f"{critical_cnt} flags", delta_color="inverse")
        col3.metric("Drainage Risks", drainage_cnt, delta=None if drainage_cnt == 0 else f"{drainage_cnt} flags", delta_color="inverse")
        col4.metric("Warnings / Advisories", warning_cnt)

        # Display Data Table and Download Option
        if all_issues:
            df = pd.DataFrame(all_issues)

            # Styling helpers
            def highlight_severity(val):
                if "CRITICAL" in str(val):
                    return "background-color: #ffcccc; color: #990000; font-weight: bold;"
                elif "DRAINAGE" in str(val):
                    return "background-color: #fff2cc; color: #b25900; font-weight: bold;"
                elif "WARNING" in str(val):
                    return "background-color: #e6f2ff; color: #004085;"
                return ""

            styled_df = df.style.applymap(highlight_severity, subset=["severity"])
            st.dataframe(styled_df, use_container_width=True)

            # CSV Download Button
            csv_data = df.to_csv(index=False).encode('utf-8')
            clean_name = os.path.splitext(uploaded_file.name)[0]
            st.download_button(
                label=f"📥 Download Audit CSV for {uploaded_file.name}",
                data=csv_data,
                file_name=f"audit_{clean_name}_{speed_choice}kph.csv",
                mime="text/csv",
                key=uploaded_file.name
            )
        else:
            st.success("🎉 Full Compliance: Zero geometric violations found for the selected TPDM criteria!")
        
        st.divider()
else:
    st.info("👈 Upload your LandXML files above to begin the automated compliance audit.")
