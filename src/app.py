"""
Constitutional Content Guardian - Streamlit Dashboard

Interactive demo dashboard for the HIPAA compliance system.
"""

import sys
import os
import json
from datetime import datetime, timedelta

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from loguru import logger
from pypdf import PdfReader

from src.agents.compliance_workflow import ComplianceWorkflow

# Configure page
st.set_page_config(
    page_title="Constitutional Content Guardian",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #666;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
    }
    .violation-critical {
        color: #d32f2f;
        font-weight: bold;
    }
    .violation-high {
        color: #f57c00;
        font-weight: bold;
    }
    .violation-medium {
        color: #fbc02d;
        font-weight: bold;
    }
    .compliant {
        color: #388e3c;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'workflow_result' not in st.session_state:
    st.session_state.workflow_result = None

# Header
st.markdown('<div class="main-header">🛡️ Constitutional Content Guardian</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">AI-Powered HIPAA Compliance Analysis System</div>', unsafe_allow_html=True)

st.markdown("""
Autonomous compliance agent that detects HIPAA violations using **Constitutional AI principles**
and generates self-healing remediation plans.

**Powered by:** AWS Bedrock (Claude Sonnet 4.5) + LangGraph Multi-Agent Orchestration
""")

st.divider()

# Sidebar - Document Metadata
with st.sidebar:
    st.header("📋 Document Metadata")

    document_id = st.text_input(
        "Document ID",
        value=f"DOC-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
        help="Unique document identifier"
    )

    document_type = st.selectbox(
        "Document Type",
        options=[
            "medical_record",
            "psychotherapy_notes",
            "audit_log",
            "authorization_form",
            "notice_of_privacy_practices"
        ],
        help="Type of healthcare document"
    )

    created_date = st.date_input(
        "Created Date",
        value=datetime.now() - timedelta(days=365*4),  # 4 years ago
        help="Document creation date"
    )

    last_use_date = st.date_input(
        "Last Use Date (Optional)",
        value=None,
        help="Last date document was accessed/modified"
    )

    st.subheader("Access Control Settings")

    current_access = st.multiselect(
        "Current Access Roles",
        options=["physician", "nurse", "billing_staff", "researcher", "patient", "public"],
        default=["physician", "billing_staff"],
        help="Roles that currently have access"
    )

    legal_hold = st.selectbox(
        "Legal Hold Status",
        options=["Unknown", "Active", "Not Active"],
        help="Whether document is under legal hold"
    )

    state_jurisdiction = st.selectbox(
        "State Jurisdiction",
        options=["Federal", "CA", "TX", "NY"],
        help="State for retention policy (CA=7yr, TX=10yr)"
    )

    st.divider()

    # Sample Documents
    st.subheader("📄 Sample Documents")

    if st.button("Load Sample: High Severity"):
        st.session_state.sample_doc = """PATIENT MEDICAL RECORD

Patient Name: Sarah Johnson
MRN: MRN-78901
DOB: 08/22/1975
SSN: 123-45-6789
Phone: 555-234-5678
Email: sarah.j@email.com
Address: 456 Oak Street, Los Angeles, CA 90001

CONFIDENTIAL - PSYCHOTHERAPY NOTES

Chief Complaint: Severe depression and anxiety following domestic violence incident.

Diagnosis:
- Major Depressive Disorder (ICD-10: F33.2)
- Post-Traumatic Stress Disorder (ICD-10: F43.10)
- History of substance abuse (cocaine)

Treatment Plan:
- Prozac 40mg daily
- Weekly cognitive behavioral therapy sessions
- Substance abuse counseling referral

Lab Results:
- Urine drug screen: Positive for cocaine metabolites
- TSH: 2.5 mIU/L (normal)

Provider: Dr. Michael Chen, Psychiatrist
Date: 04/08/2026

CRITICAL NOTE: Patient at high risk. History of suicide attempts. Close monitoring required.
"""

    if st.button("Load Sample: Medium Severity"):
        st.session_state.sample_doc = """PATIENT VISIT SUMMARY

Patient: John Smith
MRN: 45678
Visit Date: 04/08/2026

Reason for Visit: Annual physical examination

Vital Signs:
- BP: 128/82 mmHg
- HR: 72 bpm
- Temp: 98.6°F
- Weight: 185 lbs

Assessment: Overall good health. Mild hypertension noted.

Plan:
- Continue current medications
- Diet and exercise counseling
- Follow-up in 6 months

Medications:
- Lisinopril 10mg daily

Dr. Jane Williams, MD
"""

# Main content area
col1, col2 = st.columns([2, 1])

with col1:
    st.header("📝 Document Content")

    # File upload option
    uploaded_file = st.file_uploader(
        "Upload PDF Document (Optional)",
        type=['pdf'],
        help="Upload a PDF healthcare document for analysis"
    )

    # Extract text from PDF if uploaded
    extracted_text = ""
    if uploaded_file is not None:
        try:
            pdf_reader = PdfReader(uploaded_file)
            extracted_text = ""
            for page in pdf_reader.pages:
                extracted_text += page.extract_text() + "\n"
            st.success(f"✅ Extracted text from {len(pdf_reader.pages)} page(s)")
        except Exception as e:
            st.error(f"❌ Failed to read PDF: {str(e)}")

    # Document text input
    document_text = st.text_area(
        "Or paste document content here:",
        value=extracted_text if extracted_text else st.session_state.get('sample_doc', ''),
        height=400,
        placeholder="Upload PDF above or paste document text here...",
        help="The document will be analyzed for PHI, access control, and retention compliance"
    )

    # Analyze button
    analyze_button = st.button("🔍 Run Compliance Analysis", type="primary", use_container_width=True)

with col2:
    st.header("⚙️ Analysis Configuration")

    enable_llm_phi = st.checkbox(
        "Enable LLM for PHI Detection",
        value=True,
        help="Use Claude for advanced PHI detection (slower but more accurate)"
    )

    show_reasoning = st.checkbox(
        "Show Detailed Reasoning",
        value=True,
        help="Display agent reasoning and regulatory citations"
    )

    st.info("""
    **Analysis Pipeline:**
    1. 🔍 PHI Detection
    2. 🔐 Access Control
    3. 📅 Retention Policy
    4. 🔧 Remediation Plan
    """)

st.divider()

# Run analysis
if analyze_button and document_text:
    with st.spinner("🤖 Running compliance analysis..."):
        try:
            # Convert inputs
            legal_hold_bool = None if legal_hold == "Unknown" else (legal_hold == "Active")

            # Initialize workflow
            workflow = ComplianceWorkflow()

            # Process document
            result = workflow.process_document(
                document_id=document_id,
                document_text=document_text,
                document_type=document_type,
                created_date=created_date.isoformat(),
                current_access_roles=current_access,
                last_use_date=last_use_date.isoformat() if last_use_date else None,
                legal_hold_active=legal_hold_bool,
                state=state_jurisdiction
            )

            st.session_state.workflow_result = result

        except Exception as e:
            st.error(f"❌ Analysis failed: {str(e)}")
            st.exception(e)

# Display results
if st.session_state.workflow_result:
    result = st.session_state.workflow_result

    # Overall Status
    st.header("📊 Compliance Analysis Results")

    if result['workflow_status'] == 'completed':
        st.success("✅ Analysis completed successfully")
    else:
        st.error(f"❌ Analysis status: {result['workflow_status']}")
        if result['errors']:
            for error in result['errors']:
                st.error(error)

    # Metrics row
    col1, col2, col3, col4 = st.columns(4)

    phi_count = len(result.get('phi_result', {}).get('phi_detected', []))
    access_violations = len(result.get('access_result', {}).get('violations', []))
    retention_violations = len(result.get('retention_result', {}).get('violations', []))
    remediation_actions = len(result.get('remediation_plan', {}).get('remediation_plan', []))

    with col1:
        st.metric("PHI Entities Detected", phi_count)
    with col2:
        st.metric("Access Violations", access_violations, delta=None if access_violations == 0 else f"-{access_violations}")
    with col3:
        st.metric("Retention Violations", retention_violations, delta=None if retention_violations == 0 else f"-{retention_violations}")
    with col4:
        st.metric("Remediation Actions", remediation_actions)

    st.divider()

    # Tabs for detailed results
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🔍 PHI Detection",
        "🔐 Access Control",
        "📅 Retention Policy",
        "🔧 Remediation Plan",
        "📄 Full Report"
    ])

    # Tab 1: PHI Detection
    with tab1:
        if result.get('phi_result'):
            phi = result['phi_result']

            col1, col2 = st.columns(2)
            with col1:
                st.subheader("Detection Summary")
                st.metric("Sensitivity Level", phi['sensitivity_level'].upper())
                st.metric("Confidence", f"{phi['overall_confidence']:.0%}")
                st.metric("Total Entities", len(phi['phi_detected']))

            with col2:
                # Pie chart of PHI types
                if phi['phi_detected']:
                    type_counts = {}
                    for entity in phi['phi_detected']:
                        type_counts[entity['type']] = type_counts.get(entity['type'], 0) + 1

                    fig = px.pie(
                        values=list(type_counts.values()),
                        names=list(type_counts.keys()),
                        title="PHI by Type"
                    )
                    st.plotly_chart(fig, use_container_width=True)

            if show_reasoning:
                st.info(f"**Reasoning:** {phi['reasoning']}")

            # Entity table
            if phi['phi_detected']:
                st.subheader("Detected Entities")

                entity_data = []
                for entity in phi['phi_detected'][:20]:  # Show first 20
                    entity_data.append({
                        "Category": entity['category'],
                        "Type": entity['type'],
                        "Location": entity['location'],
                        "Confidence": f"{entity['confidence']:.0%}",
                        "Regulation": entity['regulation']
                    })

                st.dataframe(entity_data, use_container_width=True)

                if len(phi['phi_detected']) > 20:
                    st.caption(f"Showing 20 of {len(phi['phi_detected'])} entities")

    # Tab 2: Access Control
    with tab2:
        if result.get('access_result'):
            access = result['access_result']

            col1, col2 = st.columns(2)
            with col1:
                st.subheader("Current Access")
                for role in access['current_access']:
                    st.write(f"- {role}")

            with col2:
                st.subheader("Required Access")
                for role in access['required_access']:
                    st.write(f"- {role}")

            st.divider()

            # Violations
            if access['violations']:
                st.subheader("⚠️ Access Control Violations")

                for i, violation in enumerate(access['violations'], 1):
                    severity_class = f"violation-{violation['severity']}"

                    with st.expander(f"Violation {i}: {violation['violation_type']} [{violation['severity'].upper()}]"):
                        st.markdown(f"**Type:** {violation['violation_type']}")
                        st.markdown(f"**Severity:** <span class='{severity_class}'>{violation['severity'].upper()}</span>", unsafe_allow_html=True)
                        st.markdown(f"**Current State:** {violation['current_state']}")
                        st.markdown(f"**Required State:** {violation['required_state']}")
                        st.markdown(f"**Regulation:** {violation['regulation']}")
                        st.markdown(f"**Affected Roles:** {', '.join(violation['affected_roles'])}")
            else:
                st.success("✅ No access control violations detected")

            if access['requires_human_review']:
                st.warning("⚠️ Human compliance officer review required")

            if show_reasoning:
                st.info(f"**Reasoning:** {access['reasoning']}")

    # Tab 3: Retention Policy
    with tab3:
        if result.get('retention_result'):
            retention = result['retention_result']

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Document Type", retention['document_type'])
                st.metric("Created Date", retention['created_date'][:10])
            with col2:
                st.metric("Retention Deadline", retention['retention_deadline'][:10])
                schedule = retention['applicable_schedule']
                st.metric("Retention Period", schedule['most_restrictive'])
            with col3:
                status = retention['current_status']
                status_emoji = "✅" if status == "compliant" else "⚠️"
                st.metric("Status", f"{status_emoji} {status.upper()}")

                if retention['legal_hold_check']['status'] == 'required':
                    st.error("🔒 LEGAL HOLD ACTIVE")

            st.divider()

            # Violations
            if retention['violations']:
                st.subheader("⚠️ Retention Violations")

                for i, violation in enumerate(retention['violations'], 1):
                    with st.expander(f"Violation {i}: {violation['violation_type']} [{violation['severity'].upper()}]"):
                        st.markdown(f"**Type:** {violation['violation_type']}")
                        st.markdown(f"**Severity:** {violation['severity'].upper()}")
                        st.markdown(f"**Details:** {violation['details']}")
                        st.markdown(f"**Regulation:** {violation['regulation']}")
            else:
                st.success("✅ No retention violations detected")

            if show_reasoning:
                st.info(f"**Reasoning:** {retention['reasoning']}")

    # Tab 4: Remediation Plan
    with tab4:
        if result.get('remediation_plan'):
            remediation = result['remediation_plan']

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Actions", len(remediation['remediation_plan']))
            with col2:
                st.metric("Overall Confidence", f"{remediation['overall_confidence']:.0%}")
            with col3:
                st.metric("Estimated Time", remediation['estimated_total_time'])

            if remediation['requires_human_review']:
                st.warning(f"⚠️ **Human Review Required:** {remediation['requires_human_review_reason']}")

            st.divider()

            # Actions
            if remediation['remediation_plan']:
                st.subheader("🔧 Remediation Actions")

                # Priority order visualization
                st.caption(f"**Execution Order:** {' → '.join(remediation['priority_order'])}")

                for i, action in enumerate(remediation['remediation_plan'], 1):
                    severity_color = {
                        'critical': '🔴',
                        'high': '🟠',
                        'medium': '🟡',
                        'low': '🟢'
                    }.get(action['severity'], '⚪')

                    auto_badge = "🤖 AUTO" if action['auto_executable'] else "👤 MANUAL"

                    with st.expander(f"{severity_color} Action {i}: {action['action_type']} [{auto_badge}]"):
                        col1, col2 = st.columns([2, 1])

                        with col1:
                            st.markdown(f"**Details:** {action['action_details']}")
                            st.markdown(f"**Rollback Plan:** {action['rollback_plan']}")

                        with col2:
                            st.metric("Confidence", f"{action['confidence']:.0%}")
                            st.metric("Estimated Time", action['estimated_time'])
                            st.metric("Severity", action['severity'].upper())

                            if action['requires_approval_from']:
                                st.warning(f"Requires approval: {action['requires_approval_from']}")

            if show_reasoning:
                st.info(f"**Reasoning:** {remediation['reasoning']}")

    # Tab 5: Full Report
    with tab5:
        st.subheader("📄 Complete Compliance Report")

        st.json(result, expanded=False)

        # Download button
        report_json = json.dumps(result, indent=2)
        st.download_button(
            label="⬇️ Download Full Report (JSON)",
            data=report_json,
            file_name=f"compliance_report_{document_id}.json",
            mime="application/json"
        )

# Footer
st.divider()
st.markdown("""
<div style='text-align: center; color: #666; padding: 2rem;'>
    <p><strong>Constitutional Content Guardian</strong> - Built for Hyland's Product & Technology Hackathon 2026</p>
    <p>Powered by AWS Bedrock (Claude Sonnet 4.5) | LangGraph Multi-Agent Orchestration | Constitutional AI Principles</p>
    <p><em>HIPAA Compliance: 45 CFR §164.502(b), §164.524-528, §164.530(j)</em></p>
</div>
""", unsafe_allow_html=True)
