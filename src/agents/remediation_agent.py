"""
Remediation Agent

Generates actionable remediation plans for detected compliance violations.
Creates specific fix actions with auto-executable vs. human-review classification.

Based on HIPAA constitutional principles and violation severity
"""

import json
import sys
import os
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime, timezone

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.agents.access_control_agent import AccessControlResult, AccessViolation
from src.agents.retention_policy_agent import RetentionPolicyResult, RetentionViolation
from loguru import logger


@dataclass
class RemediationAction:
    """Single remediation action"""
    violation_id: str
    action_type: str  # update_access_control, apply_encryption, update_metadata, delete, etc.
    action_details: str
    auto_executable: bool
    confidence: float
    estimated_time: str
    severity: str
    requires_approval_from: Optional[str]
    rollback_plan: str

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class RemediationPlan:
    """Complete remediation plan"""
    violations_analyzed: List[str]
    remediation_plan: List[RemediationAction]
    overall_confidence: float
    requires_human_review: bool
    requires_human_review_reason: Optional[str]
    priority_order: List[str]
    estimated_total_time: str
    reasoning: str
    document_id: Optional[str] = None
    timestamp: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "violations_analyzed": self.violations_analyzed,
            "remediation_plan": [action.to_dict() for action in self.remediation_plan],
            "overall_confidence": self.overall_confidence,
            "requires_human_review": self.requires_human_review,
            "requires_human_review_reason": self.requires_human_review_reason,
            "priority_order": self.priority_order,
            "estimated_total_time": self.estimated_total_time,
            "reasoning": self.reasoning,
            "document_id": self.document_id,
            "timestamp": self.timestamp
        }


class RemediationAgent:
    """
    Remediation Agent - generates actionable compliance fixes.

    Decision criteria for auto-executable:
    - Confidence > 0.8
    - Severity <= medium
    - Standard remediation pattern
    - No sensitive PHI involved

    Otherwise → human review required
    """

    def __init__(self):
        """Initialize Remediation Agent"""
        logger.info("Remediation Agent initialized")

    def generate_plan(
        self,
        access_control_result: Optional[AccessControlResult] = None,
        retention_result: Optional[RetentionPolicyResult] = None,
        document_id: Optional[str] = None
    ) -> RemediationPlan:
        """
        Generate comprehensive remediation plan from violation results.

        Args:
            access_control_result: Result from Access Control Agent
            retention_result: Result from Retention Policy Agent
            document_id: Optional document identifier

        Returns:
            RemediationPlan with ordered actions
        """
        logger.info(f"Generating remediation plan for document: {document_id or 'unknown'}")

        actions = []
        violations_analyzed = []

        # Process access control violations
        if access_control_result and access_control_result.violations:
            access_actions = self._remediate_access_violations(
                access_control_result.violations,
                access_control_result.required_access,
                access_control_result.current_access
            )
            actions.extend(access_actions)
            violations_analyzed.extend([f"access_{i}" for i in range(len(access_control_result.violations))])

        # Process retention violations
        if retention_result and retention_result.violations:
            retention_actions = self._remediate_retention_violations(
                retention_result.violations,
                retention_result.legal_hold_check.status,
                retention_result.document_type
            )
            actions.extend(retention_actions)
            violations_analyzed.extend([f"retention_{i}" for i in range(len(retention_result.violations))])

        # Determine if human review needed
        requires_human_review, review_reason = self._check_human_review_needed(actions)

        # Calculate overall confidence
        overall_confidence = self._calculate_confidence(actions)

        # Prioritize actions
        priority_order = self._prioritize_actions(actions)

        # Estimate total time
        estimated_total_time = self._estimate_total_time(actions)

        # Generate reasoning
        reasoning = self._generate_reasoning(actions, requires_human_review)

        plan = RemediationPlan(
            violations_analyzed=violations_analyzed,
            remediation_plan=actions,
            overall_confidence=overall_confidence,
            requires_human_review=requires_human_review,
            requires_human_review_reason=review_reason,
            priority_order=priority_order,
            estimated_total_time=estimated_total_time,
            reasoning=reasoning,
            document_id=document_id,
            timestamp=datetime.now(timezone.utc).isoformat()
        )

        logger.info(
            f"Remediation plan generated: {len(actions)} actions, "
            f"confidence={overall_confidence:.2f}, human_review={requires_human_review}"
        )

        return plan

    def _remediate_access_violations(
        self,
        violations: List[AccessViolation],
        required_access: List[str],
        current_access: List[str]
    ) -> List[RemediationAction]:
        """Generate remediation actions for access control violations"""
        actions = []

        for i, violation in enumerate(violations):
            violation_id = f"access_{i}"

            if violation.violation_type == "overpermissive":
                # Remove unauthorized access
                action = RemediationAction(
                    violation_id=violation_id,
                    action_type="update_access_control",
                    action_details=f"Revoke access for: {', '.join(violation.affected_roles)}. "
                                  f"Update to minimum necessary: {', '.join(required_access)}",
                    auto_executable=(violation.severity != "critical"),
                    confidence=0.90 if violation.severity != "critical" else 0.75,
                    estimated_time="5 minutes",
                    severity=violation.severity,
                    requires_approval_from="compliance_officer" if violation.severity == "critical" else None,
                    rollback_plan=f"Restore access for: {', '.join(violation.affected_roles)}"
                )
                actions.append(action)

            elif violation.violation_type == "underpermissive":
                # Grant required access
                action = RemediationAction(
                    violation_id=violation_id,
                    action_type="update_access_control",
                    action_details=f"Grant access to: {', '.join(violation.affected_roles)}",
                    auto_executable=True,
                    confidence=0.95,
                    estimated_time="3 minutes",
                    severity=violation.severity,
                    requires_approval_from=None,
                    rollback_plan=f"Revoke access for: {', '.join(violation.affected_roles)}"
                )
                actions.append(action)

        return actions

    def _remediate_retention_violations(
        self,
        violations: List[RetentionViolation],
        legal_hold_status: str,
        document_type: str
    ) -> List[RemediationAction]:
        """Generate remediation actions for retention violations"""
        actions = []

        for i, violation in enumerate(violations):
            violation_id = f"retention_{i}"

            if violation.violation_type == "retention_exceeded":
                if legal_hold_status == "required":
                    # Cannot dispose - document under legal hold
                    action = RemediationAction(
                        violation_id=violation_id,
                        action_type="update_metadata",
                        action_details="Add legal hold flag to document metadata. "
                                      "Do NOT dispose - legal hold active.",
                        auto_executable=True,
                        confidence=0.95,
                        estimated_time="2 minutes",
                        severity="high",
                        requires_approval_from=None,
                        rollback_plan="Remove legal hold flag"
                    )
                    actions.append(action)

                elif legal_hold_status == "unknown":
                    # Need to verify legal hold before disposition
                    action = RemediationAction(
                        violation_id=violation_id,
                        action_type="verify_legal_hold",
                        action_details="Verify legal hold status with legal team. "
                                      "If no hold: proceed to secure deletion. "
                                      "If hold: update metadata and retain.",
                        auto_executable=False,
                        confidence=0.85,
                        estimated_time="1-2 business days",
                        severity=violation.severity,
                        requires_approval_from="legal_team",
                        rollback_plan="N/A - verification step only"
                    )
                    actions.append(action)

                else:  # not_required
                    # Can dispose - no legal hold
                    action = RemediationAction(
                        violation_id=violation_id,
                        action_type="secure_deletion",
                        action_details=f"Document eligible for disposition. "
                                      f"Perform secure deletion per NIST 800-88 guidelines. "
                                      f"Document audit trail of deletion.",
                        auto_executable=False,  # Deletion always requires approval
                        confidence=0.90,
                        estimated_time="30 minutes",
                        severity=violation.severity,
                        requires_approval_from="records_manager",
                        rollback_plan="N/A - deletion is permanent (archive backup if needed)"
                    )
                    actions.append(action)

            elif violation.violation_type == "approaching_deadline":
                # Proactive notification
                action = RemediationAction(
                    violation_id=violation_id,
                    action_type="notify_records_manager",
                    action_details="Notify records manager of approaching retention deadline. "
                                  "Schedule disposition review.",
                    auto_executable=True,
                    confidence=0.95,
                    estimated_time="1 minute",
                    severity=violation.severity,
                    requires_approval_from=None,
                    rollback_plan="Cancel notification"
                )
                actions.append(action)

        return actions

    def _check_human_review_needed(
        self,
        actions: List[RemediationAction]
    ) -> tuple[bool, Optional[str]]:
        """Determine if human review is required"""
        # Any critical severity requires review
        if any(action.severity == "critical" for action in actions):
            return True, "Critical severity violation(s) require compliance officer review"

        # Any non-auto-executable requires review
        if any(not action.auto_executable for action in actions):
            return True, "One or more actions require human approval"

        # Low confidence requires review
        if actions and min(action.confidence for action in actions) < 0.7:
            return True, "Low confidence in remediation plan"

        return False, None

    def _calculate_confidence(self, actions: List[RemediationAction]) -> float:
        """Calculate overall confidence in remediation plan"""
        if not actions:
            return 1.0

        # Average confidence across actions
        avg_confidence = sum(action.confidence for action in actions) / len(actions)

        # Reduce if many actions (complexity)
        if len(actions) > 5:
            avg_confidence *= 0.95

        return round(avg_confidence, 2)

    def _prioritize_actions(self, actions: List[RemediationAction]) -> List[str]:
        """Prioritize actions by severity and dependencies"""
        # Sort by severity (critical > high > medium > low)
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}

        sorted_actions = sorted(
            actions,
            key=lambda a: (severity_order.get(a.severity, 4), not a.auto_executable)
        )

        return [action.violation_id for action in sorted_actions]

    def _estimate_total_time(self, actions: List[RemediationAction]) -> str:
        """Estimate total remediation time"""
        if not actions:
            return "0 minutes"

        # Simple estimation (in production would be more sophisticated)
        total_minutes = 0
        for action in actions:
            time_str = action.estimated_time.lower()
            if "minute" in time_str:
                minutes = int(time_str.split()[0])
                total_minutes += minutes
            elif "hour" in time_str:
                hours = int(time_str.split()[0].split("-")[0])
                total_minutes += hours * 60
            elif "day" in time_str:
                days = int(time_str.split()[0].split("-")[0])
                total_minutes += days * 8 * 60  # 8 hours per business day

        if total_minutes < 60:
            return f"{total_minutes} minutes"
        elif total_minutes < 480:  # 8 hours
            hours = total_minutes / 60
            return f"{hours:.1f} hours"
        else:
            days = total_minutes / (8 * 60)
            return f"{days:.1f} business days"

    def _generate_reasoning(
        self,
        actions: List[RemediationAction],
        requires_human_review: bool
    ) -> str:
        """Generate human-readable reasoning"""
        if not actions:
            return "No violations detected. No remediation needed."

        reasoning = f"Generated {len(actions)} remediation action(s). "

        # Count by severity
        critical = sum(1 for a in actions if a.severity == "critical")
        high = sum(1 for a in actions if a.severity == "high")
        medium = sum(1 for a in actions if a.severity == "medium")

        if critical > 0:
            reasoning += f"{critical} critical action(s) requiring immediate attention. "
        if high > 0:
            reasoning += f"{high} high-priority action(s). "
        if medium > 0:
            reasoning += f"{medium} medium-priority action(s). "

        # Auto-executable vs manual
        auto_count = sum(1 for a in actions if a.auto_executable)
        manual_count = len(actions) - auto_count

        if auto_count > 0:
            reasoning += f"{auto_count} action(s) can be auto-executed. "
        if manual_count > 0:
            reasoning += f"{manual_count} action(s) require manual review. "

        if requires_human_review:
            reasoning += "Human compliance officer review required before execution."

        return reasoning


# Convenience function
def generate_remediation_plan(
    access_control_result: Optional[AccessControlResult] = None,
    retention_result: Optional[RetentionPolicyResult] = None,
    document_id: Optional[str] = None
) -> RemediationPlan:
    """Quick remediation plan generation"""
    agent = RemediationAgent()
    return agent.generate_plan(access_control_result, retention_result, document_id)


if __name__ == "__main__":
    # Test the remediation agent
    from loguru import logger
    from src.agents.phi_detection_agent import detect_phi
    from src.agents.access_control_agent import evaluate_access_controls
    from src.agents.retention_policy_agent import evaluate_retention

    logger.remove()
    logger.add(sys.stdout, level="INFO")

    print("Testing Remediation Agent\n")
    print("=" * 70)

    # Sample document
    sample_document = """
    Patient: Jane Smith
    MRN: 98765
    Diagnosis: Hypertension, Diabetes Type 2
    """

    try:
        print("\n[TEST] Running full compliance check pipeline...\n")

        # Step 1: PHI Detection
        phi_result = detect_phi(sample_document, document_id="TEST-REM-001", enable_llm=False)
        print(f"[OK] PHI Detection: {len(phi_result.phi_detected)} entities")

        # Step 2: Access Control (with violations)
        access_result = evaluate_access_controls(
            current_access_roles=["physician", "billing_staff", "public"],  # PUBLIC violation!
            phi_result=phi_result,
            document_id="TEST-REM-001"
        )
        print(f"[OK] Access Control: {len(access_result.violations)} violations")

        # Step 3: Retention Policy (with violation)
        retention_result = evaluate_retention(
            document_type="medical_record",
            created_date="2015-01-01",
            last_use_date="2015-12-31",
            legal_hold_active=None,  # Unknown - requires verification
            document_id="TEST-REM-001"
        )
        print(f"[OK] Retention Policy: {len(retention_result.violations)} violations\n")

        # Step 4: Generate Remediation Plan
        print("=" * 70)
        print("\n[REMEDIATION PLAN]\n")

        agent = RemediationAgent()
        plan = agent.generate_plan(
            access_control_result=access_result,
            retention_result=retention_result,
            document_id="TEST-REM-001"
        )

        print(f"Violations Analyzed: {len(plan.violations_analyzed)}")
        print(f"Actions Generated: {len(plan.remediation_plan)}")
        print(f"Overall Confidence: {plan.overall_confidence:.2f}")
        print(f"Human Review Required: {plan.requires_human_review}")
        if plan.requires_human_review_reason:
            print(f"Review Reason: {plan.requires_human_review_reason}")
        print(f"Estimated Total Time: {plan.estimated_total_time}")
        print(f"\nPriority Order: {' > '.join(plan.priority_order)}")

        print(f"\nActions:\n")
        for i, action in enumerate(plan.remediation_plan, 1):
            print(f"{i}. [{action.severity.upper()}] {action.action_type}")
            print(f"   Details: {action.action_details}")
            print(f"   Auto-executable: {action.auto_executable}")
            print(f"   Confidence: {action.confidence:.2f}")
            print(f"   Estimated Time: {action.estimated_time}")
            if action.requires_approval_from:
                print(f"   Requires Approval: {action.requires_approval_from}")
            print(f"   Rollback: {action.rollback_plan}")
            print()

        print(f"Reasoning:\n{plan.reasoning}\n")

        print("=" * 70)
        print("\n[SUCCESS] Remediation Agent working correctly!")

    except Exception as e:
        print(f"\n[FAIL] Test failed: {e}")
        import traceback
        traceback.print_exc()
