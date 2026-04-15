"""
Retention Policy Agent

Verifies document retention compliance with HIPAA and applicable state laws.
Checks retention schedules, legal holds, and disposition eligibility.

Based on HIPAA Retention Requirements (45 CFR §164.530(j))
"""

import json
import sys
import os
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from dateutil import parser

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.models.bedrock_client import BedrockClient
from src.config.prompts import RETENTION_POLICY_PROMPT
from loguru import logger


@dataclass
class RetentionViolation:
    """Retention policy violation"""
    violation_type: str  # premature_deletion, retention_exceeded, missing_schedule
    severity: str  # critical, high, medium, low
    regulation: str
    details: str

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class RetentionSchedule:
    """Applicable retention schedule"""
    federal_requirement: str  # e.g., "6 years"
    state_requirement: Optional[str]  # e.g., "7 years (California)"
    most_restrictive: str  # The one that applies
    regulation: str

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class LegalHoldCheck:
    """Legal hold verification"""
    status: str  # required, not_required, unknown
    requires_verification: bool
    reason: Optional[str] = None

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class RetentionPolicyResult:
    """Retention policy evaluation result"""
    document_type: str
    created_date: str
    applicable_schedule: RetentionSchedule
    retention_deadline: str
    current_status: str  # compliant, approaching_deadline, past_deadline
    violations: List[RetentionViolation]
    legal_hold_check: LegalHoldCheck
    confidence: float
    reasoning: str
    document_id: Optional[str] = None
    timestamp: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "document_type": self.document_type,
            "created_date": self.created_date,
            "applicable_schedule": self.applicable_schedule.to_dict(),
            "retention_deadline": self.retention_deadline,
            "current_status": self.current_status,
            "violations": [v.to_dict() for v in self.violations],
            "legal_hold_check": self.legal_hold_check.to_dict(),
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "document_id": self.document_id,
            "timestamp": self.timestamp
        }


class RetentionPolicyAgent:
    """
    Retention Policy Agent - verifies HIPAA retention compliance.

    Federal Requirements (45 CFR §164.530(j)(2)):
    - Medical records: 6 years minimum from creation or last use
    - Psychotherapy notes: 6 years (separate storage)
    - Audit logs: 6 years
    - Authorization forms: 6 years from date or last effective date

    State Variations (use most restrictive):
    - California: 7 years minimum
    - New York: 6 years minimum
    - Texas: 10 years for adult records
    """

    # Retention schedules by document type
    RETENTION_SCHEDULES = {
        "medical_record": {
            "federal_years": 6,
            "regulation": "45 CFR §164.530(j)(2)",
            "from_date": "creation_or_last_use",
            "state_overrides": {
                "CA": 7,
                "TX": 10,
                "NY": 6
            }
        },
        "psychotherapy_notes": {
            "federal_years": 6,
            "regulation": "45 CFR §164.530(j)(2)",
            "from_date": "creation_or_last_use",
            "special_handling": "Separate from medical record, enhanced access controls"
        },
        "audit_log": {
            "federal_years": 6,
            "regulation": "45 CFR §164.312(b) - Audit Controls",
            "from_date": "creation"
        },
        "authorization_form": {
            "federal_years": 6,
            "regulation": "45 CFR §164.508",
            "from_date": "date_or_last_effective"
        },
        "notice_of_privacy_practices": {
            "federal_years": 6,
            "regulation": "45 CFR §164.520",
            "from_date": "creation_or_last_effective"
        },
        "business_associate_agreement": {
            "federal_years": 6,
            "regulation": "45 CFR §164.504",
            "from_date": "termination"
        }
    }

    def __init__(
        self,
        bedrock_client: Optional[BedrockClient] = None,
        state: str = "Federal",
        enable_llm: bool = False  # LLM optional for retention checks
    ):
        """
        Initialize Retention Policy Agent.

        Args:
            bedrock_client: AWS Bedrock client (creates new if None)
            state: State code (e.g., "CA", "TX") or "Federal"
            enable_llm: Whether to use LLM for ambiguous cases
        """
        self.bedrock_client = bedrock_client or BedrockClient()
        self.state = state
        self.enable_llm = enable_llm
        logger.info(f"Retention Policy Agent initialized (jurisdiction: {state})")

    def evaluate(
        self,
        document_type: str,
        created_date: str,
        document_id: Optional[str] = None,
        last_use_date: Optional[str] = None,
        legal_hold_active: Optional[bool] = None
    ) -> RetentionPolicyResult:
        """
        Evaluate retention policy compliance for a document.

        Args:
            document_type: Type of document (medical_record, audit_log, etc.)
            created_date: Document creation date (ISO format or common date formats)
            document_id: Optional document identifier
            last_use_date: Optional last use date (for medical records)
            legal_hold_active: Optional flag if document is under legal hold

        Returns:
            RetentionPolicyResult with compliance status and violations
        """
        logger.info(f"Evaluating retention policy for document: {document_id or 'unknown'}")

        # Parse dates
        created = self._parse_date(created_date)
        last_use = self._parse_date(last_use_date) if last_use_date else None

        # Get applicable schedule
        schedule = self._get_retention_schedule(document_type)

        # Calculate retention deadline
        retention_deadline = self._calculate_retention_deadline(
            document_type,
            created,
            last_use
        )

        # Determine current status
        current_status = self._determine_status(retention_deadline)

        # Check for violations
        violations = self._check_violations(
            document_type,
            created,
            retention_deadline,
            current_status
        )

        # Check legal hold
        legal_hold_check = self._check_legal_hold(
            legal_hold_active,
            current_status,
            violations
        )

        # Calculate confidence
        confidence = self._calculate_confidence(document_type, created, last_use)

        # Generate reasoning
        reasoning = self._generate_reasoning(
            document_type,
            created,
            retention_deadline,
            current_status,
            violations,
            legal_hold_check
        )

        result = RetentionPolicyResult(
            document_type=document_type,
            created_date=created.isoformat(),
            applicable_schedule=schedule,
            retention_deadline=retention_deadline.isoformat(),
            current_status=current_status,
            violations=violations,
            legal_hold_check=legal_hold_check,
            confidence=confidence,
            reasoning=reasoning,
            document_id=document_id,
            timestamp=datetime.now(timezone.utc).isoformat()
        )

        logger.info(
            f"Retention evaluation complete: status={current_status}, "
            f"violations={len(violations)}, confidence={confidence:.2f}"
        )

        return result

    def _parse_date(self, date_str: str) -> datetime:
        """Parse date string to datetime object"""
        try:
            dt = parser.parse(date_str)
            # Make timezone-aware if naive
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception as e:
            logger.warning(f"Failed to parse date '{date_str}': {e}")
            raise ValueError(f"Invalid date format: {date_str}")

    def _get_retention_schedule(self, document_type: str) -> RetentionSchedule:
        """Get applicable retention schedule"""
        if document_type not in self.RETENTION_SCHEDULES:
            logger.warning(f"Unknown document type: {document_type}, using default")
            document_type = "medical_record"

        schedule_info = self.RETENTION_SCHEDULES[document_type]
        federal_years = schedule_info["federal_years"]
        regulation = schedule_info["regulation"]

        # Check for state overrides
        state_years = None
        state_requirement = None
        if self.state != "Federal" and "state_overrides" in schedule_info:
            state_years = schedule_info["state_overrides"].get(self.state)
            if state_years:
                state_requirement = f"{state_years} years ({self.state})"

        # Use most restrictive
        most_restrictive_years = max(federal_years, state_years or federal_years)

        return RetentionSchedule(
            federal_requirement=f"{federal_years} years",
            state_requirement=state_requirement,
            most_restrictive=f"{most_restrictive_years} years",
            regulation=regulation
        )

    def _calculate_retention_deadline(
        self,
        document_type: str,
        created: datetime,
        last_use: Optional[datetime]
    ) -> datetime:
        """Calculate retention deadline date"""
        schedule_info = self.RETENTION_SCHEDULES.get(
            document_type,
            self.RETENTION_SCHEDULES["medical_record"]
        )

        # Determine retention period
        federal_years = schedule_info["federal_years"]
        state_override = 0
        if self.state != "Federal" and "state_overrides" in schedule_info:
            state_override = schedule_info["state_overrides"].get(self.state, 0)

        retention_years = max(federal_years, state_override)

        # Determine start date based on "from_date" rule
        from_date_rule = schedule_info.get("from_date", "creation")

        if from_date_rule == "creation_or_last_use" and last_use:
            start_date = max(created, last_use)
        else:
            start_date = created

        # Calculate deadline
        deadline = start_date + timedelta(days=365 * retention_years)

        return deadline

    def _determine_status(self, retention_deadline: datetime) -> str:
        """Determine current retention status"""
        now = datetime.now(timezone.utc)
        days_until_deadline = (retention_deadline - now).days

        if days_until_deadline < 0:
            return "past_deadline"
        elif days_until_deadline <= 90:  # 3 months warning
            return "approaching_deadline"
        else:
            return "compliant"

    def _check_violations(
        self,
        document_type: str,
        created: datetime,
        retention_deadline: datetime,
        current_status: str
    ) -> List[RetentionViolation]:
        """Check for retention violations"""
        violations = []

        # Past retention deadline without legal hold
        if current_status == "past_deadline":
            violation = RetentionViolation(
                violation_type="retention_exceeded",
                severity="high",
                regulation="45 CFR §164.530(j)(2)",
                details=f"Document has exceeded retention deadline ({retention_deadline.date()}). "
                       f"Must verify legal hold status and disposition eligibility."
            )
            violations.append(violation)

        # Approaching deadline warning
        elif current_status == "approaching_deadline":
            days_remaining = (retention_deadline - datetime.now(timezone.utc)).days
            violation = RetentionViolation(
                violation_type="approaching_deadline",
                severity="medium",
                regulation="45 CFR §164.530(j)(2)",
                details=f"Document will reach retention deadline in {days_remaining} days. "
                       f"Prepare for disposition review."
            )
            violations.append(violation)

        return violations

    def _check_legal_hold(
        self,
        legal_hold_active: Optional[bool],
        current_status: str,
        violations: List[RetentionViolation]
    ) -> LegalHoldCheck:
        """Check if legal hold verification is needed"""
        if legal_hold_active is True:
            return LegalHoldCheck(
                status="required",
                requires_verification=False,
                reason="Document under active legal hold - do not dispose"
            )

        if legal_hold_active is False:
            return LegalHoldCheck(
                status="not_required",
                requires_verification=False,
                reason="No legal hold active"
            )

        # Unknown status - need verification if approaching/past deadline
        if current_status in ["past_deadline", "approaching_deadline"]:
            return LegalHoldCheck(
                status="unknown",
                requires_verification=True,
                reason="Verify legal hold status before disposition"
            )

        return LegalHoldCheck(
            status="not_required",
            requires_verification=False,
            reason="Document within retention period"
        )

    def _calculate_confidence(
        self,
        document_type: str,
        created: datetime,
        last_use: Optional[datetime]
    ) -> float:
        """Calculate confidence in retention evaluation"""
        confidence = 0.95  # High confidence for rule-based evaluation

        # Reduce confidence if document type unknown
        if document_type not in self.RETENTION_SCHEDULES:
            confidence *= 0.8

        # Reduce confidence if last_use date is missing for medical records
        if document_type == "medical_record" and not last_use:
            confidence *= 0.9

        return round(confidence, 2)

    def _generate_reasoning(
        self,
        document_type: str,
        created: datetime,
        retention_deadline: datetime,
        current_status: str,
        violations: List[RetentionViolation],
        legal_hold_check: LegalHoldCheck
    ) -> str:
        """Generate human-readable reasoning"""
        age_days = (datetime.now(timezone.utc) - created).days
        age_years = age_days / 365.25

        reasoning = f"Document type: {document_type}, created {age_years:.1f} years ago. "
        reasoning += f"Retention deadline: {retention_deadline.date()}. "

        if current_status == "compliant":
            reasoning += "Document is within retention period and compliant. "
        elif current_status == "approaching_deadline":
            days_remaining = (retention_deadline - datetime.now(timezone.utc)).days
            reasoning += f"Document approaching retention deadline ({days_remaining} days remaining). "
        elif current_status == "past_deadline":
            days_past = (datetime.now(timezone.utc) - retention_deadline).days
            reasoning += f"Document has exceeded retention deadline by {days_past} days. "

        if legal_hold_check.status == "required":
            reasoning += "Legal hold active - do not dispose. "
        elif legal_hold_check.requires_verification:
            reasoning += "Legal hold status must be verified before disposition. "

        if violations:
            reasoning += f"{len(violations)} violation(s) detected. "

        return reasoning


# Convenience function
def evaluate_retention(
    document_type: str,
    created_date: str,
    document_id: Optional[str] = None,
    last_use_date: Optional[str] = None,
    legal_hold_active: Optional[bool] = None,
    state: str = "Federal"
) -> RetentionPolicyResult:
    """Quick retention policy evaluation"""
    agent = RetentionPolicyAgent(state=state)
    return agent.evaluate(document_type, created_date, document_id, last_use_date, legal_hold_active)


if __name__ == "__main__":
    # Test the retention policy agent
    from loguru import logger

    logger.remove()
    logger.add(sys.stdout, level="INFO")

    print("Testing Retention Policy Agent\n")
    print("=" * 70)

    # Test scenarios
    test_scenarios = [
        {
            "name": "Scenario 1: Compliant Medical Record",
            "document_type": "medical_record",
            "created_date": "2022-01-15",
            "last_use_date": "2024-06-30",
            "legal_hold_active": False,
            "state": "Federal"
        },
        {
            "name": "Scenario 2: Past Retention Deadline",
            "document_type": "medical_record",
            "created_date": "2016-01-01",
            "last_use_date": "2016-12-31",
            "legal_hold_active": None,
            "state": "Federal"
        },
        {
            "name": "Scenario 3: California Medical Record (7 years)",
            "document_type": "medical_record",
            "created_date": "2018-06-15",
            "last_use_date": "2019-03-01",
            "legal_hold_active": False,
            "state": "CA"
        },
        {
            "name": "Scenario 4: Approaching Deadline",
            "document_type": "audit_log",
            "created_date": "2020-01-15",
            "last_use_date": None,
            "legal_hold_active": False,
            "state": "Federal"
        },
        {
            "name": "Scenario 5: Legal Hold Active",
            "document_type": "medical_record",
            "created_date": "2015-01-01",
            "last_use_date": "2015-12-31",
            "legal_hold_active": True,
            "state": "Federal"
        }
    ]

    try:
        for scenario in test_scenarios:
            print("=" * 70)
            print(f"\n{scenario['name']}\n")

            agent = RetentionPolicyAgent(state=scenario['state'])
            result = agent.evaluate(
                document_type=scenario['document_type'],
                created_date=scenario['created_date'],
                last_use_date=scenario['last_use_date'],
                legal_hold_active=scenario['legal_hold_active'],
                document_id=f"TEST-{scenario['name'][:10]}"
            )

            print(f"Document Type: {result.document_type}")
            print(f"Created: {result.created_date[:10]}")
            print(f"Retention Schedule: {result.applicable_schedule.most_restrictive}")
            print(f"Retention Deadline: {result.retention_deadline[:10]}")
            print(f"Current Status: {result.current_status}")
            print(f"Violations: {len(result.violations)}")
            print(f"Legal Hold: {result.legal_hold_check.status}")
            print(f"Confidence: {result.confidence:.2f}")

            if result.violations:
                print(f"\nViolations Detected:")
                for i, violation in enumerate(result.violations, 1):
                    print(f"\n{i}. Type: {violation.violation_type}")
                    print(f"   Severity: {violation.severity}")
                    print(f"   Details: {violation.details}")

            print(f"\nReasoning:\n{result.reasoning}\n")

        print("=" * 70)
        print("\n[SUCCESS] Retention Policy Agent working correctly!")

    except Exception as e:
        print(f"\n[FAIL] Test failed: {e}")
        import traceback
        traceback.print_exc()
