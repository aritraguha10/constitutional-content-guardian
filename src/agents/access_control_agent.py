"""
Access Control Agent

Evaluates whether document access controls meet HIPAA minimum necessary standards.
Checks role-based access permissions and flags violations.

Based on HIPAA Minimum Necessary Standard (45 CFR §164.502(b))
"""

import json
import sys
import os
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, asdict
from datetime import datetime, timezone

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.models.bedrock_client import BedrockClient
from src.config.prompts import ACCESS_CONTROL_PROMPT
from src.agents.phi_detection_agent import PHIDetectionResult
from loguru import logger


@dataclass
class AccessViolation:
    """Access control violation"""
    violation_type: str  # overpermissive, underpermissive, missing_controls
    current_state: str
    required_state: str
    severity: str  # critical, high, medium, low
    regulation: str
    affected_roles: List[str]

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class AccessControlResult:
    """Access control evaluation result"""
    current_access: List[str]
    required_access: List[str]
    violations: List[AccessViolation]
    confidence: float
    requires_human_review: bool
    reasoning: str
    document_id: Optional[str] = None
    timestamp: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "current_access": self.current_access,
            "required_access": self.required_access,
            "violations": [v.to_dict() for v in self.violations],
            "confidence": self.confidence,
            "requires_human_review": self.requires_human_review,
            "reasoning": self.reasoning,
            "document_id": self.document_id,
            "timestamp": self.timestamp
        }


class AccessControlAgent:
    """
    Access Control Agent - evaluates HIPAA minimum necessary compliance.

    Role-based access matrix:
    - Physician: Full clinical access (except psychotherapy notes without authorization)
    - Nurse: Care-related access (limited diagnosis info)
    - Billing: Insurance/billing codes only (no clinical notes)
    - Researcher: De-identified data only
    - Patient: All their own PHI
    """

    # Role-based access permissions
    ROLE_PERMISSIONS = {
        "physician": {
            "can_access": {
                "patient_demographics", "clinical_notes", "lab_results",
                "medications", "diagnoses", "vital_signs", "medical_history"
            },
            "restrictions": {
                "psychotherapy_notes": "requires explicit authorization",
                "substance_abuse_records": "requires patient consent (42 CFR Part 2)"
            },
            "regulation": "45 CFR §164.506"
        },
        "nurse": {
            "can_access": {
                "patient_demographics", "care_plans", "medication_admin_records",
                "vital_signs", "nursing_notes"
            },
            "restrictions": {
                "diagnoses": "limited to need-to-know",
                "psychotherapy_notes": "no access without authorization"
            },
            "regulation": "45 CFR §164.502(b)"
        },
        "billing_staff": {
            "can_access": {
                "patient_demographics_limited", "insurance_info",
                "diagnosis_codes", "procedure_codes", "billing_info"
            },
            "restrictions": {
                "clinical_notes": "no access",
                "treatment_details": "only billing codes"
            },
            "regulation": "45 CFR §164.502(b)"
        },
        "researcher": {
            "can_access": {
                "deidentified_data"
            },
            "restrictions": {
                "phi_identifiers": "requires IRB approval and data use agreement",
                "limited_dataset": "requires data use agreement"
            },
            "regulation": "45 CFR §164.514"
        },
        "patient": {
            "can_access": {
                "all_own_phi"
            },
            "restrictions": {
                "psychotherapy_notes": "may be denied",
                "endangerment_risk": "may be denied if endangers patient or others"
            },
            "regulation": "45 CFR §164.524"
        },
        "public": {
            "can_access": set(),
            "restrictions": {
                "all_phi": "no access"
            },
            "regulation": "45 CFR §164.502"
        }
    }

    def __init__(
        self,
        bedrock_client: Optional[BedrockClient] = None,
        enable_llm: bool = True
    ):
        """
        Initialize Access Control Agent.

        Args:
            bedrock_client: AWS Bedrock client (creates new if None)
            enable_llm: Whether to use LLM for advanced evaluation
        """
        self.bedrock_client = bedrock_client or BedrockClient()
        self.enable_llm = enable_llm
        logger.info("Access Control Agent initialized")

    def evaluate(
        self,
        current_access_roles: List[str],
        phi_result: PHIDetectionResult,
        document_type: str = "medical_record",
        document_id: Optional[str] = None
    ) -> AccessControlResult:
        """
        Evaluate access controls for a document.

        Args:
            current_access_roles: List of roles that currently have access
            phi_result: PHI detection result from PHI Detection Agent
            document_type: Type of document (medical_record, psychotherapy_notes, etc.)
            document_id: Optional document identifier

        Returns:
            AccessControlResult with violations and recommendations
        """
        logger.info(f"Evaluating access controls for document: {document_id or 'unknown'}")
        logger.debug(f"Current access: {current_access_roles}, Type: {document_type}")

        # Determine required access based on sensitivity
        required_access = self._determine_required_access(phi_result, document_type)

        # Identify violations
        violations = self._identify_violations(
            current_access_roles,
            required_access,
            phi_result,
            document_type
        )

        # Check if human review needed
        requires_human_review = self._check_human_review_needed(violations, phi_result)

        # Calculate confidence
        confidence = self._calculate_confidence(violations, phi_result)

        # Generate reasoning
        reasoning = self._generate_reasoning(
            current_access_roles,
            required_access,
            violations,
            phi_result
        )

        result = AccessControlResult(
            current_access=current_access_roles,
            required_access=required_access,
            violations=violations,
            confidence=confidence,
            requires_human_review=requires_human_review,
            reasoning=reasoning,
            document_id=document_id,
            timestamp=datetime.now(timezone.utc).isoformat()
        )

        logger.info(
            f"Access control evaluation complete: {len(violations)} violations, "
            f"confidence={confidence:.2f}, human_review={requires_human_review}"
        )

        return result

    def _determine_required_access(
        self,
        phi_result: PHIDetectionResult,
        document_type: str
    ) -> List[str]:
        """Determine which roles should have access based on document sensitivity"""
        sensitivity = phi_result.sensitivity_level

        # Special handling for psychotherapy notes
        if document_type == "psychotherapy_notes":
            return ["patient", "psychotherapist"]  # Very restricted

        # Special handling for substance abuse records
        if document_type == "substance_abuse":
            return ["patient", "treating_physician"]  # 42 CFR Part 2

        # General medical records - based on sensitivity
        if sensitivity == "critical":
            # Highly restricted - only treating providers
            return ["physician", "nurse", "patient"]
        elif sensitivity == "high":
            # Restricted - treating team
            return ["physician", "nurse", "billing_staff", "patient"]
        elif sensitivity == "medium":
            # Standard access
            return ["physician", "nurse", "billing_staff", "patient"]
        else:  # low
            # Broad access (still not public)
            return ["physician", "nurse", "billing_staff", "researcher", "patient"]

    def _identify_violations(
        self,
        current_access: List[str],
        required_access: List[str],
        phi_result: PHIDetectionResult,
        document_type: str
    ) -> List[AccessViolation]:
        """Identify access control violations"""
        violations = []

        current_set = set(current_access)
        required_set = set(required_access)

        # Check for overpermissive access
        overpermissive = current_set - required_set
        if overpermissive:
            violation = AccessViolation(
                violation_type="overpermissive",
                current_state=f"Access granted to: {', '.join(sorted(overpermissive))}",
                required_state=f"Access should be limited to: {', '.join(sorted(required_access))}",
                severity="high" if phi_result.sensitivity_level in ["critical", "high"] else "medium",
                regulation="45 CFR §164.502(b) - Minimum Necessary",
                affected_roles=list(overpermissive)
            )
            violations.append(violation)

        # Check for underpermissive access (missing required roles)
        underpermissive = required_set - current_set
        if underpermissive:
            # Only flag if critical roles are missing
            critical_missing = underpermissive.intersection({"patient", "physician"})
            if critical_missing:
                violation = AccessViolation(
                    violation_type="underpermissive",
                    current_state=f"Missing access for: {', '.join(sorted(critical_missing))}",
                    required_state=f"Must grant access to: {', '.join(sorted(critical_missing))}",
                    severity="high",
                    regulation="45 CFR §164.524 - Right to Access (for patient)",
                    affected_roles=list(critical_missing)
                )
                violations.append(violation)

        # Check for special restrictions
        if document_type == "psychotherapy_notes" and "billing_staff" in current_access:
            violation = AccessViolation(
                violation_type="overpermissive",
                current_state="Billing staff has access to psychotherapy notes",
                required_state="Psychotherapy notes should be separate from medical record",
                severity="critical",
                regulation="45 CFR §164.501 - Psychotherapy Notes Definition",
                affected_roles=["billing_staff"]
            )
            violations.append(violation)

        # Check if public access is granted (should never be)
        if "public" in current_access:
            violation = AccessViolation(
                violation_type="overpermissive",
                current_state="Public access granted to PHI",
                required_state="No public access to PHI",
                severity="critical",
                regulation="45 CFR §164.502 - Uses and Disclosures",
                affected_roles=["public"]
            )
            violations.append(violation)

        return violations

    def _check_human_review_needed(
        self,
        violations: List[AccessViolation],
        phi_result: PHIDetectionResult
    ) -> bool:
        """Determine if human compliance officer review is needed"""
        # Critical violations always need review
        if any(v.severity == "critical" for v in violations):
            return True

        # High sensitivity with violations needs review
        if phi_result.sensitivity_level == "critical" and violations:
            return True

        # Multiple high-severity violations
        high_severity_count = sum(1 for v in violations if v.severity == "high")
        if high_severity_count >= 2:
            return True

        return False

    def _calculate_confidence(
        self,
        violations: List[AccessViolation],
        phi_result: PHIDetectionResult
    ) -> float:
        """Calculate confidence in access control evaluation"""
        # Start with PHI detection confidence
        base_confidence = phi_result.overall_confidence

        # Reduce confidence if violations are ambiguous
        if len(violations) > 5:
            base_confidence *= 0.9

        # High confidence for clear violations
        if any(v.severity == "critical" for v in violations):
            base_confidence = min(base_confidence + 0.05, 1.0)

        return round(base_confidence, 2)

    def _generate_reasoning(
        self,
        current_access: List[str],
        required_access: List[str],
        violations: List[AccessViolation],
        phi_result: PHIDetectionResult
    ) -> str:
        """Generate human-readable reasoning"""
        if not violations:
            return f"Access controls comply with HIPAA minimum necessary standard. Current access ({', '.join(current_access)}) aligns with document sensitivity ({phi_result.sensitivity_level})."

        reasoning = f"Found {len(violations)} access control violation(s). "

        critical_count = sum(1 for v in violations if v.severity == "critical")
        high_count = sum(1 for v in violations if v.severity == "high")

        if critical_count > 0:
            reasoning += f"{critical_count} critical violation(s) requiring immediate remediation. "
        if high_count > 0:
            reasoning += f"{high_count} high-severity violation(s). "

        reasoning += f"Document contains {phi_result.sensitivity_level} sensitivity PHI. "

        # Summarize violation types
        overpermissive = sum(1 for v in violations if v.violation_type == "overpermissive")
        if overpermissive:
            reasoning += f"{overpermissive} overpermissive access grant(s) violate minimum necessary standard. "

        return reasoning


# Convenience function
def evaluate_access_controls(
    current_access_roles: List[str],
    phi_result: PHIDetectionResult,
    document_type: str = "medical_record",
    document_id: Optional[str] = None
) -> AccessControlResult:
    """Quick access control evaluation"""
    agent = AccessControlAgent()
    return agent.evaluate(current_access_roles, phi_result, document_type, document_id)


if __name__ == "__main__":
    # Test the access control agent
    from loguru import logger
    from src.agents.phi_detection_agent import detect_phi

    logger.remove()
    logger.add(sys.stdout, level="INFO")

    print("Testing Access Control Agent\n")
    print("=" * 70)

    # Sample document
    sample_document = """
    Patient: John Doe
    MRN: 12345
    Diagnosis: Type 2 Diabetes, Hypertension
    Medications: Metformin 500mg BID, Lisinopril 10mg daily
    """

    # Test scenarios
    test_scenarios = [
        {
            "name": "Scenario 1: Overpermissive Access",
            "current_access": ["physician", "nurse", "billing_staff", "public", "researcher"],
            "document_type": "medical_record"
        },
        {
            "name": "Scenario 2: Compliant Access",
            "current_access": ["physician", "nurse", "billing_staff", "patient"],
            "document_type": "medical_record"
        },
        {
            "name": "Scenario 3: Psychotherapy Notes Violation",
            "current_access": ["physician", "billing_staff"],
            "document_type": "psychotherapy_notes"
        }
    ]

    try:
        # First, detect PHI
        print("\n[TEST] Detecting PHI in sample document...\n")
        phi_result = detect_phi(sample_document, document_id="TEST-ACCESS-001", enable_llm=False)
        print(f"PHI Detection: {len(phi_result.phi_detected)} entities, sensitivity={phi_result.sensitivity_level}\n")

        # Test each scenario
        agent = AccessControlAgent()

        for scenario in test_scenarios:
            print("=" * 70)
            print(f"\n{scenario['name']}\n")
            print(f"Current Access: {', '.join(scenario['current_access'])}")
            print(f"Document Type: {scenario['document_type']}\n")

            result = agent.evaluate(
                current_access_roles=scenario['current_access'],
                phi_result=phi_result,
                document_type=scenario['document_type'],
                document_id="TEST-ACCESS-001"
            )

            print(f"Required Access: {', '.join(result.required_access)}")
            print(f"Violations: {len(result.violations)}")
            print(f"Confidence: {result.confidence:.2f}")
            print(f"Human Review Needed: {result.requires_human_review}")

            if result.violations:
                print(f"\nViolations Detected:")
                for i, violation in enumerate(result.violations, 1):
                    print(f"\n{i}. Type: {violation.violation_type}")
                    print(f"   Severity: {violation.severity}")
                    print(f"   Current: {violation.current_state}")
                    print(f"   Required: {violation.required_state}")
                    print(f"   Regulation: {violation.regulation}")

            print(f"\nReasoning:\n{result.reasoning}\n")

        print("=" * 70)
        print("\n[SUCCESS] Access Control Agent working correctly!")

    except Exception as e:
        print(f"\n[FAIL] Test failed: {e}")
        import traceback
        traceback.print_exc()
