# Constitutional Content Guardian

An autonomous AI compliance agent that continuously monitors document repositories, detects HIPAA violations using Constitutional AI principles, and orchestrates self-healing remediation workflows.

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────┐
│          Orchestrator Agent (LangGraph)         │
│  Routes documents to specialist agents          │
└─────────────────┬───────────────────────────────┘
                  │
        ┌─────────┼─────────┬─────────────┐
        ▼         ▼         ▼             ▼
    ┌─────┐  ┌─────┐  ┌──────┐      ┌─────────┐
    │ PHI  │  │Access│  │Retention│   │Remediation│
    │Detect│  │Control│  │Policy  │   │Executor   │
    └─────┘  └─────┘  └──────┘      └─────────┘
        │         │         │             │
        └─────────┴─────────┴─────────────┘
                  │
                  ▼
        ┌──────────────────────┐
        │  Audit Trail Logger  │
        └──────────────────────┘
```

## 📁 Project Structure

```
constitutional-content-guardian/
├── src/
│   ├── agents/              # Multi-agent system
│   │   ├── phi_detection_agent.py
│   │   ├── access_control_agent.py
│   │   ├── retention_policy_agent.py
│   │   ├── remediation_agent.py
│   │   └── compliance_workflow.py    # LangGraph orchestration
│   ├── models/
│   │   └── bedrock_client.py         # AWS Bedrock wrapper ✅
│   ├── config/
│   │   └── prompts.py                # Constitutional AI prompts ✅
│   ├── utils/
│   │   ├── data_generator.py
│   │   └── audit_logger.py
│   ├── evaluation/
│   │   └── evaluator.py              # DeepEval integration
│   └── app.py                        # Streamlit dashboard
├── data/
│   ├── compliance_policies/
│   │   └── hipaa_constitution.yaml   # HIPAA constitution ✅
│   └── sample_documents/
├── tests/
├── logs/
├── requirements.txt                   # Dependencies ✅
├── .env.example                      # AWS config template ✅
├── setup_environment.sh              # Setup script ✅
└── verify_setup.py                   # Verification tool ✅
```

## 🚀 Quick Start

### 1. Prerequisites

- Python 3.10+
- AWS Account with Bedrock access
- AWS CLI configured

### 2. Setup

```bash
# Navigate to project directory
cd constitutional-content-guardian

# Install dependencies
pip install -r requirements.txt

# Configure environment (AWS credentials should already be set)
# Model ID: us.anthropic.claude-sonnet-4-5-20250929-v1:0
```

### 3. Launch Dashboard

**Windows:**
```bash
run_dashboard.bat
```

**Mac/Linux:**
```bash
chmod +x run_dashboard.sh
./run_dashboard.sh
```

**Or directly:**
```bash
streamlit run src/app.py
```

Then open your browser to: **http://localhost:8501**

### 4. Test Individual Agents

```bash
# Test PHI Detection
python src/agents/phi_detection_agent.py

# Test Access Control
python src/agents/access_control_agent.py

# Test Retention Policy
python src/agents/retention_policy_agent.py

# Test Remediation
python src/agents/remediation_agent.py

# Test Complete Workflow
python src/agents/compliance_workflow.py
```

## 🔑 Key Features

### 1. Constitutional AI Framework

Based on Anthropic's constitutional AI principles:

- **Patient Privacy First** (45 CFR §164.502(b))
- **Transparency and Explainability** (45 CFR §164.526)
- **Balance Accessibility and Security** (45 CFR §164.506)
- **Retention vs. Deletion Balance** (45 CFR §164.530(j))

### 2. Self-Healing Remediation

- **Auto-executable actions** for high-confidence, low-risk violations
- **Human-in-loop** for critical severity or ambiguous cases
- **Confidence scoring** based on RL from compliance officer feedback

### 3. Multi-Agent Orchestration (LangGraph)

Each agent specializes in one compliance domain:
- PHI Detection (NER + LLM classification)
- Access Control (role-based minimum necessary)
- Retention Policy (federal/state schedule compliance)
- Remediation (actionable fix generation)

### 4. Evaluation & Monitoring

- **Faithfulness** - Are decisions grounded in regulations?
- **Relevancy** - Are recommendations practical?
- **Constitutional Alignment** - Follow principles in priority order?
- **Confidence Calibration** - Are uncertain cases flagged?



## 🧪 Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html

# Run specific test
pytest tests/test_phi_detection.py -v
```

## 📚 References

### HIPAA Regulations

- **45 CFR §164.502(b)** - Minimum Necessary Standard
- **45 CFR §164.506** - Treatment, Payment, Healthcare Operations
- **45 CFR §164.524-528** - Patient Rights (Access, Amendment, Accounting)
- **45 CFR §164.530(j)** - Retention Requirements

### Technical

- [Anthropic Constitutional AI Paper](https://arxiv.org/abs/2212.08073)
- [LangGraph Documentation](https://python.langchain.com/docs/langgraph)
- [AWS Bedrock Developer Guide](https://docs.aws.amazon.com/bedrock/)
- [DeepEval Framework](https://docs.confident-ai.com/)

## 🤝 Contributing

This is a hackathon project. For production use, additional work needed:

- [ ] Integration with real ECM systems (OnBase, Alfresco)
- [ ] Production database for audit trail
- [ ] Advanced RL training loop
- [ ] Multi-jurisdiction support (state laws)
- [ ] Performance optimization for scale

## 👥 Authors

Built with Claude Code (Opus 4.6) + AWS Bedrock
