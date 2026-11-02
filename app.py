import streamlit as st
import pandas as pd
import requests
import os

st.set_page_config(page_title="CloudSync Pro Feedback Hub", layout="wide")

# Allowed labels for system validation
ALLOWED_LABELS = [
    "bug_technical",
    "feature_request",
    "billing_pricing",
    "usability_ui",
    "positive_feedback",
    "needs_manual_review"
]

# Initialize Session State Database
if "feedback_db" not in st.session_state:
    st.session_state.feedback_db = pd.DataFrame(columns=["Rating", "Comment", "LLM_Label", "Manual_Review"])

def classify_feedback_with_groq(comment_text, rating):
    """Calls Groq API to label SaaS customer feedback."""
    groq_api_key = st.secrets.get("GROQ_API_KEY", os.getenv("GROQ_API_KEY"))
    
    if not groq_api_key:
        return "needs_manual_review"

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {groq_api_key}",
        "Content-Type": "application/json"
    }

    prompt = (
        "You label customer feedback for CloudSync Pro, a B2B SaaS platform.\n"
        "Categorize the comment into EXACTLY ONE of the following categories:\n"
        "- bug_technical: System crashes, sync failures, software errors, or slow performance.\n"
        "- feature_request: Requests for new features, missing tools, or third-party integrations.\n"
        "- billing_pricing: Concerns about subscription plans, invoices, upgrades, or prices.\n"
        "- usability_ui: Confusing interface layout, navigation friction, or design complaints.\n"
        "- positive_feedback: General praise, satisfaction with reliability, or high utility.\n"
        "- needs_manual_review: Urgent churn threats, sarcasm, ambiguous text, or edge cases.\n\n"
        f"Customer Rating: {rating} Stars\n"
        f"Customer Comment: {comment_text}\n"
    )

    payload = {
        "model": "openai/gpt-oss-20b",
        "temperature": 0,
        "messages": [{"role": "user", "content": prompt}]
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        if response.status_code == 200:
            result = response.json()["choices"][0]["message"]["content"].strip().lower()
            return result if result in ALLOWED_LABELS else "needs_manual_review"
        else:
            return "needs_manual_review"
    except Exception:
        return "needs_manual_review"

# ---------------------------------------------------------
# Sidebar Navigation
# ---------------------------------------------------------
st.sidebar.title("CloudSync Portal")
page = st.sidebar.radio("Navigation", ["Submit Customer Feedback", "Executive Owner Dashboard"])

# ---------------------------------------------------------
# Page 1: Customer Feedback Portal
# ---------------------------------------------------------
if page == "Submit Customer Feedback":
    st.title("💻 CloudSync Pro User Feedback")
    st.write("Help us improve CloudSync Pro. Leave a star rating, a comment, or both.")

    with st.form("feedback_form"):
        rating = st.slider("Satisfaction Rating (1 = Poor, 5 = Excellent)", min_value=1, max_value=5, value=5)
        comment = st.text_area("Your Feedback / Feature Request / Issues", placeholder="Describe your experience with CloudSync Pro...")
        submitted = st.form_submit_button("Submit Response")

    if submitted:
        if not comment.strip() and rating is None:
            st.error("Please provide at least a star rating or a written comment.")
        else:
            with st.spinner("Analyzing feedback..."):
                if comment.strip():
                    llm_label = classify_feedback_with_groq(comment.strip(), rating)
                else:
                    llm_label = "positive_feedback" if rating >= 4 else "needs_manual_review"

                # Flag mismatch rules (e.g., Low rating given with positive label)
                needs_review = False
                if llm_label == "needs_manual_review" or (rating <= 2 and llm_label == "positive_feedback"):
                    needs_review = True
                    llm_label = "needs_manual_review"

                # Store result
                new_entry = pd.DataFrame([{
                    "Rating": rating,
                    "Comment": comment if comment.strip() else "N/A (Rating only)",
                    "LLM_Label": llm_label,
                    "Manual_Review": needs_review
                }])
                st.session_state.feedback_db = pd.concat([st.session_state.feedback_db, new_entry], ignore_index=True)
                st.success("Your response has been recorded and routed to product management!")

# ---------------------------------------------------------
# Page 2: Executive Dashboard
# ---------------------------------------------------------
elif page == "Executive Owner Dashboard":
    st.title("📊 Product & Churn Intelligence Dashboard")
    st.write("Categorized insights to track software health, churn risk, and critical issues.")

    df = st.session_state.feedback_db

    if df.empty:
        st.info("No feedback entries available yet. Use the sidebar to submit test data.")
    else:
        # 1. Key Metrics
        c1, c2, c3 = st.columns(3)
        
        total_feedback = len(df)
        avg_rating = df["Rating"].mean()
        manual_review_count = len(df[df["LLM_Label"] == "needs_manual_review"])

        c1.metric("Total Submissions", total_feedback)
        c2.metric("Average Rating", f"{avg_rating:.2f} ⭐")
        c3.metric("Requires Manual Review", manual_review_count)

        st.markdown("---")

        # 2. Charts
        col_a, col_b = st.columns(2)
        
        with col_a:
            st.subheader("Feedback Category Breakdown")
            label_counts = df["LLM_Label"].value_counts()
            st.bar_chart(label_counts)

        with col_b:
            st.subheader("Rating Distribution")
            rating_counts = df["Rating"].value_counts().sort_index()
            st.bar_chart(rating_counts)

        st.markdown("---")

        # 3. Manual Review Table
        st.subheader("🚨 Accounts Needing Urgent Manual Review")
        flagged_df = df[df["LLM_Label"] == "needs_manual_review"]

        if flagged_df.empty:
            st.success("No high-risk feedback currently flagged for manual intervention.")
        else:
            st.dataframe(
                flagged_df[["Rating", "Comment", "LLM_Label"]], 
                use_container_width=True
            )
