import streamlit as st
import requests

st.title("📊 Company Financial Analyser")

# Example list of companies — replace with your actual company list
company_list = ["Select a company", "Acme Corp", "Globex Inc", "Stark Industries", "Wayne Enterprises"]

# Dropdown for selecting company
company = st.selectbox("Choose Company", company_list)

# File uploader
uploaded_file = st.file_uploader("Upload CMA data", type=["xlsx"])

tab1, tab2 = st.tabs(["Upload File", "View Results"])

with tab1:

    # Submission logic
    if st.button("Submit", key="submit_button"):
        if company == "Select a company":
            st.warning("Please select a valid company.")
        elif uploaded_file is None:
            st.warning("Please upload an Excel file.")
        else:
            with st.spinner("Processing Summary Report..."):
                try:
                    file = {
                        "file": (uploaded_file.name, uploaded_file, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                    }
                    data = {
                        "account_name": company
                    }
                    response = requests.post("https://cred360-genai.onrender.com/api/analysis", data=data, files=file)

                    if response.status_code == 200:
                        st.success("File processed successfully!")
                        st.json(response.json())
                    else:
                        st.error(f"Error {response.status_code}")
                        st.text(response.text)
                except Exception as e:
                    st.error(f"Request failed: {e}")
# Tab for viewing results
with tab2:

    st.header("Summary of Financial Analysis")

    selected_result_company = st.selectbox("Select Company to View Result", company_list, key="result_company")
    #lower case the default selection to avoid confusion
    selected_result_company = selected_result_company.lower() if selected_result_company != "Select a company" else selected_result_company
    if st.button("Fetch Result", key="fetch_button"):
        with st.spinner("Fetching result..."):
            try:
                response = requests.get(f"https://cred360-genai.onrender.com/api/reports/{selected_result_company}")   
                if response.status_code == 200:
                    result_text = response.json()
                    st.title("📊 Financial Analysis Summary")
                    for report in result_text:
                        with st.expander(f"📄 {report['report_name']}"):
                            st.markdown(report["content"], unsafe_allow_html=True)
                else:
                    st.error(f"Error {response.status_code}")
                    st.json(response)
            except Exception as e:
                st.error(f"Request failed: {e}")

    

