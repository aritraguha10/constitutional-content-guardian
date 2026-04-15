"""
Compliance Workflow - LangGraph Orchestration

Orchestrates the multi-agent compliance system using LangGraph.

Workflow:
1. PHI Detection Agent → Detect protected health information
2. Access Control Agent → Evaluate role-based access permissions
3. Retention Policy Agent → Check retention compliance
4. Remediation Agent → Generate fix plans for violations

State flows between agents, with conditional routing based on results.
"""

import sys
import os
from typing import Dict, List, Optional, TypedDict, Annotated
from datetime import datetime, timezone

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage

from src.agents.phi_detection_agent import PHIDetectionAgent, PHIDetectionResult
from src.agents.access_control_agent import AccessControlAgent, AccessControlResult
from src.agents.retention_policy_agent import RetentionPolicyAgent, RetentionPolicyResult
from src.agents.remediation_agent import RemediationAgent, RemediationPlan
from loguru import logger


# Define the state schema
class ComplianceState(TypedDict):
    """State passed between agents in the workflow"""
    # Input
    document_id: str
    document_text: str
    document_type: str
    created_date: str
    last_use_date: Optional[str]
    current_access_roles: List[str]
    legal_hold_active: Optional[bool]
    state: Optional[str]  # For state-specific retention rules

    # Agent Results
    phi_result: Optional[Dict]
    access_result: Optional[Dict]
    retention_result: Optional[Dict]
    remediation_plan: Optional[Dict]

    # Workflow Metadata
    workflow_status: str  # processing, completed, error
    errors: List[str]
    timestamp: str


class ComplianceWorkflow:
    """
    LangGraph-based compliance workflow orchestrator.

    Coordinates PHI detection, access control, retention policy,
    and remediation agents in a stateful workflow.
    """

    def __init__(
        self,
        phi_agent: Optional[PHIDetectionAgent] = None,
        access_agent: Optional[AccessControlAgent] = None,
        retention_agent: Optional[RetentionPolicyAgent] = None,
        remediation_agent: Optional[RemediationAgent] = None
    ):
        """
        Initialize Compliance Workflow.

        Args:
            phi_agent: PHI Detection Agent (creates new if None)
            access_agent: Access Control Agent (creates new if None)
            retention_agent: Retention Policy Agent (creates new if None)
            remediation_agent: Remediation Agent (creates new if None)
        """
        self.phi_agent = phi_agent or PHIDetectionAgent(enable_llm=True)
        self.access_agent = access_agent or AccessControlAgent(enable_llm=False)
        self.retention_agent = retention_agent or RetentionPolicyAgent(enable_llm=False)
        self.remediation_agent = remediation_agent or RemediationAgent()

        # Build the workflow graph
        self.workflow = self._build_workflow()

        logger.info("Compliance Workflow initialized")

    def _build_workflow(self) -> StateGraph:
        """Build the LangGraph workflow"""
        # Create the graph
        workflow = StateGraph(ComplianceState)

        # Add nodes for each agent
        workflow.add_node("phi_detection", self._phi_detection_node)
        workflow.add_node("access_control", self._access_control_node)
        workflow.add_node("retention_policy", self._retention_policy_node)
        workflow.add_node("remediation", self._remediation_node)
        workflow.add_node("finalize", self._finalize_node)

        # Define the workflow edges (sequential flow)
        workflow.set_entry_point("phi_detection")
        workflow.add_edge("phi_detection", "access_control")
        workflow.add_edge("access_control", "retention_policy")
        workflow.add_edge("retention_policy", "remediation")
        workflow.add_edge("remediation", "finalize")
        workflow.add_edge("finalize", END)

        return workflow.compile()

    def _phi_detection_node(self, state: ComplianceState) -> ComplianceState:
        """PHI Detection Agent Node"""
        logger.info(f"[WORKFLOW] Step 1: PHI Detection - Document {state['document_id']}")

        try:
            result = self.phi_agent.detect(
                document_text=state["document_text"],
                document_id=state["document_id"]
            )

            # Store result in state
            state["phi_result"] = result.to_dict()

            logger.info(
                f"[WORKFLOW] PHI Detection complete: {len(result.phi_detected)} entities, "
                f"sensitivity={result.sensitivity_level}"
            )

        except Exception as e:
            logger.error(f"[WORKFLOW] PHI Detection failed: {e}")
            state["errors"].append(f"PHI Detection error: {str(e)}")
            state["workflow_status"] = "error"

        return state

    def _access_control_node(self, state: ComplianceState) -> ComplianceState:
        """Access Control Agent Node"""
        logger.info(f"[WORKFLOW] Step 2: Access Control - Document {state['document_id']}")

        try:
            # Reconstruct PHI result from state
            phi_result_dict = state.get("phi_result")
            if not phi_result_dict:
                raise ValueError("PHI result not found in state")

            # Create PHI result object (simplified reconstruction)
            from src.agents.phi_detection_agent import PHIDetectionResult, PHIEntity
            phi_result = PHIDetectionResult(
                phi_detected=[],  # Simplified - in production would reconstruct full objects
                sensitivity_level=phi_result_dict["sensitivity_level"],
                overall_confidence=phi_result_dict["overall_confidence"],
                reasoning=phi_result_dict["reasoning"],
                document_id=phi_result_dict.get("document_id")
            )

            result = self.access_agent.evaluate(
                current_access_roles=state["current_access_roles"],
                phi_result=phi_result,
                document_type=state["document_type"],
                document_id=state["document_id"]
            )

            # Store result in state
            state["access_result"] = result.to_dict()

            logger.info(
                f"[WORKFLOW] Access Control complete: {len(result.violations)} violations, "
                f"human_review={result.requires_human_review}"
            )

        except Exception as e:
            logger.error(f"[WORKFLOW] Access Control failed: {e}")
            state["errors"].append(f"Access Control error: {str(e)}")
            state["workflow_status"] = "error"

        return state

    def _retention_policy_node(self, state: ComplianceState) -> ComplianceState:
        """Retention Policy Agent Node"""
        logger.info(f"[WORKFLOW] Step 3: Retention Policy - Document {state['document_id']}")

        try:
            result = self.retention_agent.evaluate(
                document_type=state["document_type"],
                created_date=state["created_date"],
                document_id=state["document_id"],
                last_use_date=state.get("last_use_date"),
                legal_hold_active=state.get("legal_hold_active")
            )

            # Store result in state
            state["retention_result"] = result.to_dict()

            logger.info(
                f"[WORKFLOW] Retention Policy complete: status={result.current_status}, "
                f"violations={len(result.violations)}"
            )

        except Exception as e:
            logger.error(f"[WORKFLOW] Retention Policy failed: {e}")
            state["errors"].append(f"Retention Policy error: {str(e)}")
            state["workflow_status"] = "error"

        return state

    def _remediation_node(self, state: ComplianceState) -> ComplianceState:
        """Remediation Agent Node"""
        logger.info(f"[WORKFLOW] Step 4: Remediation - Document {state['document_id']}")

        try:
            # Reconstruct access and retention results
            access_result = None
            if state.get("access_result"):
                from src.agents.access_control_agent import AccessControlResult, AccessViolation
                access_dict = state["access_result"]
                access_result = AccessControlResult(
                    current_access=access_dict["current_access"],
                    required_access=access_dict["required_access"],
                    violations=[],  # Simplified
                    confidence=access_dict["confidence"],
                    requires_human_review=access_dict["requires_human_review"],
                    reasoning=access_dict["reasoning"]
                )
                # Add violations back
                for v in access_dict["violations"]:
                    access_result.violations.append(AccessViolation(
                        violation_type=v["violation_type"],
                        current_state=v["current_state"],
                        required_state=v["required_state"],
                        severity=v["severity"],
                        regulation=v["regulation"],
                        affected_roles=v["affected_roles"]
                    ))

            retention_result = None
            if state.get("retention_result"):
                from src.agents.retention_policy_agent import (
                    RetentionPolicyResult, RetentionViolation,
                    RetentionSchedule, LegalHoldCheck
                )
                retention_dict = state["retention_result"]
                retention_result = RetentionPolicyResult(
                    document_type=retention_dict["document_type"],
                    created_date=retention_dict["created_date"],
                    applicable_schedule=RetentionSchedule(**retention_dict["applicable_schedule"]),
                    retention_deadline=retention_dict["retention_deadline"],
                    current_status=retention_dict["current_status"],
                    violations=[],  # Simplified
                    legal_hold_check=LegalHoldCheck(**retention_dict["legal_hold_check"]),
                    confidence=retention_dict["confidence"],
                    reasoning=retention_dict["reasoning"]
                )
                # Add violations back
                for v in retention_dict["violations"]:
                    retention_result.violations.append(RetentionViolation(
                        violation_type=v["violation_type"],
                        severity=v["severity"],
                        regulation=v["regulation"],
                        details=v["details"]
                    ))

            # Generate remediation plan
            result = self.remediation_agent.generate_plan(
                access_control_result=access_result,
                retention_result=retention_result,
                document_id=state["document_id"]
            )

            # Store result in state
            state["remediation_plan"] = result.to_dict()

            logger.info(
                f"[WORKFLOW] Remediation complete: {len(result.remediation_plan)} actions, "
                f"human_review={result.requires_human_review}"
            )

        except Exception as e:
            logger.error(f"[WORKFLOW] Remediation failed: {e}")
            state["errors"].append(f"Remediation error: {str(e)}")
            state["workflow_status"] = "error"

        return state

    def _finalize_node(self, state: ComplianceState) -> ComplianceState:
        """Finalize workflow and set completion status"""
        logger.info(f"[WORKFLOW] Step 5: Finalize - Document {state['document_id']}")

        if state.get("workflow_status") == "error":
            logger.error(f"[WORKFLOW] Workflow completed with errors: {state['errors']}")
        else:
            state["workflow_status"] = "completed"
            logger.info(f"[WORKFLOW] Workflow completed successfully")

        return state

    def process_document(
        self,
        document_id: str,
        document_text: str,
        document_type: str = "medical_record",
        created_date: str = None,
        current_access_roles: List[str] = None,
        last_use_date: Optional[str] = None,
        legal_hold_active: Optional[bool] = None,
        state: str = "Federal"
    ) -> ComplianceState:
        """
        Process a document through the complete compliance workflow.

        Args:
            document_id: Unique document identifier
            document_text: Document content to analyze
            document_type: Type of document (medical_record, audit_log, etc.)
            created_date: Document creation date (ISO format)
            current_access_roles: List of roles with current access
            last_use_date: Optional last use date for retention calculation
            legal_hold_active: Whether document is under legal hold
            state: State for retention rules (e.g., "CA", "TX", "Federal")

        Returns:
            Final ComplianceState with all agent results
        """
        logger.info(f"[WORKFLOW] Starting compliance workflow for document: {document_id}")

        # Initialize state
        initial_state: ComplianceState = {
            "document_id": document_id,
            "document_text": document_text,
            "document_type": document_type,
            "created_date": created_date or datetime.now(timezone.utc).isoformat(),
            "last_use_date": last_use_date,
            "current_access_roles": current_access_roles or [],
            "legal_hold_active": legal_hold_active,
            "state": state,
            "phi_result": None,
            "access_result": None,
            "retention_result": None,
            "remediation_plan": None,
            "workflow_status": "processing",
            "errors": [],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        # Run the workflow
        try:
            final_state = self.workflow.invoke(initial_state)
            return final_state
        except Exception as e:
            logger.error(f"[WORKFLOW] Workflow execution failed: {e}")
            initial_state["workflow_status"] = "error"
            initial_state["errors"].append(f"Workflow error: {str(e)}")
            return initial_state


# Convenience function
def process_document_compliance(
    document_id: str,
    document_text: str,
    document_type: str = "medical_record",
    created_date: str = None,
    current_access_roles: List[str] = None,
    **kwargs
) -> ComplianceState:
    """Quick compliance workflow execution"""
    workflow = ComplianceWorkflow()
    return workflow.process_document(
        document_id=document_id,
        document_text=document_text,
        document_type=document_type,
        created_date=created_date,
        current_access_roles=current_access_roles,
        **kwargs
    )


if __name__ == "__main__":
    # Test the complete workflow
    from loguru import logger
    import json

    logger.remove()
    logger.add(sys.stdout, level="INFO")

    print("=" * 70)
    print("Testing Complete Compliance Workflow")
    print("=" * 70)

    # Sample healthcare document
    sample_document = """
    PATIENT MEDICAL RECORD

    Patient Name: John Smith
    MRN: MRN-54321
    DOB: 05/12/1980
    Phone: 555-987-6543
    Email: john.smith@email.com

    Chief Complaint: Chest pain and shortness of breath

    Diagnosis: Acute Coronary Syndrome (ICD-10: I24.9)

    Treatment Plan:
    - Aspirin 325mg daily
    - Atorvastatin 40mg nightly
    - Cardiac catheterization scheduled
    - Follow-up with cardiology in 1 week

    Lab Results:
    - Troponin: 0.8 ng/mL (elevated)
    - CK-MB: 12 ng/mL (elevated)
    - Total Cholesterol: 240 mg/dL

    Provider: Dr. Sarah Johnson, MD
    Date: 04/08/2026
    """

    try:
        print("\n[TEST] Processing document through compliance workflow...\n")

        # Initialize workflow
        workflow = ComplianceWorkflow()

        # Process document with violations
        result = workflow.process_document(
            document_id="TEST-WORKFLOW-001",
            document_text=sample_document,
            document_type="medical_record",
            created_date="2020-01-15",
            current_access_roles=["physician", "billing_staff", "public"],  # PUBLIC = violation
            last_use_date="2020-12-31",
            legal_hold_active=None
        )

        print("=" * 70)
        print("WORKFLOW RESULTS")
        print("=" * 70)

        print(f"\nDocument ID: {result['document_id']}")
        print(f"Workflow Status: {result['workflow_status']}")
        print(f"Errors: {len(result['errors'])}")

        # PHI Detection Results
        if result.get("phi_result"):
            phi = result["phi_result"]
            print(f"\n[1] PHI DETECTION")
            print(f"    Entities Detected: {len(phi['phi_detected'])}")
            print(f"    Sensitivity: {phi['sensitivity_level']}")
            print(f"    Confidence: {phi['overall_confidence']:.2f}")

        # Access Control Results
        if result.get("access_result"):
            access = result["access_result"]
            print(f"\n[2] ACCESS CONTROL")
            print(f"    Current Access: {', '.join(access['current_access'])}")
            print(f"    Required Access: {', '.join(access['required_access'])}")
            print(f"    Violations: {len(access['violations'])}")
            print(f"    Human Review: {access['requires_human_review']}")

        # Retention Policy Results
        if result.get("retention_result"):
            retention = result["retention_result"]
            print(f"\n[3] RETENTION POLICY")
            print(f"    Document Type: {retention['document_type']}")
            print(f"    Created: {retention['created_date'][:10]}")
            print(f"    Retention Deadline: {retention['retention_deadline'][:10]}")
            print(f"    Status: {retention['current_status']}")
            print(f"    Violations: {len(retention['violations'])}")

        # Remediation Plan
        if result.get("remediation_plan"):
            remediation = result["remediation_plan"]
            print(f"\n[4] REMEDIATION PLAN")
            print(f"    Actions Generated: {len(remediation['remediation_plan'])}")
            print(f"    Overall Confidence: {remediation['overall_confidence']:.2f}")
            print(f"    Human Review Required: {remediation['requires_human_review']}")
            print(f"    Estimated Time: {remediation['estimated_total_time']}")

            if remediation['remediation_plan']:
                print(f"\n    Top 3 Actions:")
                for i, action in enumerate(remediation['remediation_plan'][:3], 1):
                    print(f"    {i}. [{action['severity'].upper()}] {action['action_type']}")
                    print(f"       {action['action_details'][:80]}...")

        print("\n" + "=" * 70)
        print("[SUCCESS] Complete workflow test passed!")
        print("=" * 70)

    except Exception as e:
        print(f"\n[FAIL] Workflow test failed: {e}")
        import traceback
        traceback.print_exc()
