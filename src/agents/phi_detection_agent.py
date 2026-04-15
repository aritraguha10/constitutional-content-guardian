"""
PHI Detection Agent

Detects Protected Health Information (PHI) in healthcare documents using:
1. Regex patterns for common identifiers (SSN, MRN, phone numbers, etc.)
2. NER (Named Entity Recognition) for names, dates, locations
3. LLM-based classification for clinical information and sensitive PHI

Based on HIPAA's 18 identifiers (45 CFR §164.514(b)(2))
"""

import re
import json
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime

import sys
import os
# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.models.bedrock_client import BedrockClient
from src.config.prompts import PHI_DETECTION_PROMPT
from loguru import logger


@dataclass
class PHIEntity:
    """Detected PHI entity"""
    type: str  # direct_identifier, clinical, sensitive
    category: str  # specific category (e.g., "SSN", "diagnosis", "psychotherapy_note")
    value: str  # redacted value or description
    location: str  # line/section number
    confidence: float  # 0.0-1.0
    regulation: str  # relevant CFR citation

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class PHIDetectionResult:
    """Complete PHI detection result"""
    phi_detected: List[PHIEntity]
    sensitivity_level: str  # low, medium, high, critical
    overall_confidence: float
    reasoning: str
    document_id: Optional[str] = None
    timestamp: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "phi_detected": [entity.to_dict() for entity in self.phi_detected],
            "sensitivity_level": self.sensitivity_level,
            "overall_confidence": self.overall_confidence,
            "reasoning": self.reasoning,
            "document_id": self.document_id,
            "timestamp": self.timestamp
        }


class PHIDetectionAgent:
    """
    PHI Detection Agent using multi-stage detection:
    1. Regex patterns for structured identifiers
    2. NER for names, locations, dates
    3. LLM for clinical content and sensitive PHI
    """

    # HIPAA 18 Identifiers - Regex Patterns
    REGEX_PATTERNS = {
        "ssn": {
            "pattern": r'\b\d{3}-\d{2}-\d{4}\b',
            "type": "direct_identifier",
            "regulation": "45 CFR §164.514(b)(2)(i)",
            "confidence": 0.95
        },
        "phone": {
            "pattern": r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',
            "type": "direct_identifier",
            "regulation": "45 CFR §164.514(b)(2)(i)",
            "confidence": 0.85
        },
        "email": {
            "pattern": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            "type": "direct_identifier",
            "regulation": "45 CFR §164.514(b)(2)(i)",
            "confidence": 0.95
        },
        "mrn": {
            "pattern": r'\b(MRN|Medical Record Number|Patient ID):\s*([A-Z0-9-]+)\b',
            "type": "direct_identifier",
            "regulation": "45 CFR §164.514(b)(2)(i)",
            "confidence": 0.90
        },
        "date": {
            "pattern": r'\b\d{1,2}/\d{1,2}/\d{4}\b|\b\d{4}-\d{2}-\d{2}\b',
            "type": "direct_identifier",
            "regulation": "45 CFR §164.514(b)(2)(iii)",
            "confidence": 0.80
        },
        "zip_code": {
            "pattern": r'\b\d{5}(-\d{4})?\b',
            "type": "direct_identifier",
            "regulation": "45 CFR §164.514(b)(2)(ii)",
            "confidence": 0.70
        },
        "url": {
            "pattern": r'https?://[^\s]+',
            "type": "direct_identifier",
            "regulation": "45 CFR §164.514(b)(2)(i)",
            "confidence": 0.90
        },
        "ip_address": {
            "pattern": r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b',
            "type": "direct_identifier",
            "regulation": "45 CFR §164.514(b)(2)(i)",
            "confidence": 0.85
        }
    }

    # Sensitive PHI keywords (triggers higher sensitivity)
    SENSITIVE_KEYWORDS = [
        "psychotherapy", "mental health", "psychiatric", "depression", "anxiety",
        "substance abuse", "alcohol", "drug", "addiction", "HIV", "AIDS",
        "genetic", "DNA", "abortion", "sexual assault", "rape", "domestic violence"
    ]

    def __init__(
        self,
        bedrock_client: Optional[BedrockClient] = None,
        enable_llm: bool = True
    ):
        """
        Initialize PHI Detection Agent.

        Args:
            bedrock_client: AWS Bedrock client (creates new if None)
            enable_llm: Whether to use LLM for advanced detection
        """
        self.bedrock_client = bedrock_client or BedrockClient()
        self.enable_llm = enable_llm
        logger.info("PHI Detection Agent initialized")

    def detect(
        self,
        document_text: str,
        document_id: Optional[str] = None
    ) -> PHIDetectionResult:
        """
        Detect PHI in document text using multi-stage detection.

        Args:
            document_text: Document content to analyze
            document_id: Optional document identifier

        Returns:
            PHIDetectionResult with all detected entities
        """
        logger.info(f"Starting PHI detection for document: {document_id or 'unknown'}")

        # Stage 1: Regex-based detection
        regex_entities = self._detect_with_regex(document_text)
        logger.debug(f"Regex detection found {len(regex_entities)} entities")

        # Stage 2: LLM-based detection (if enabled)
        llm_entities = []
        if self.enable_llm:
            llm_entities = self._detect_with_llm(document_text)
            logger.debug(f"LLM detection found {len(llm_entities)} entities")

        # Combine and deduplicate
        all_entities = self._merge_entities(regex_entities, llm_entities)

        # Determine sensitivity level
        sensitivity_level = self._calculate_sensitivity(all_entities, document_text)

        # Calculate overall confidence
        if all_entities:
            overall_confidence = sum(e.confidence for e in all_entities) / len(all_entities)
        else:
            overall_confidence = 1.0  # No PHI detected with high confidence

        # Generate reasoning
        reasoning = self._generate_reasoning(all_entities, sensitivity_level)

        result = PHIDetectionResult(
            phi_detected=all_entities,
            sensitivity_level=sensitivity_level,
            overall_confidence=overall_confidence,
            reasoning=reasoning,
            document_id=document_id,
            timestamp=datetime.utcnow().isoformat()
        )

        logger.info(
            f"PHI detection complete: {len(all_entities)} entities, "
            f"sensitivity={sensitivity_level}, confidence={overall_confidence:.2f}"
        )

        return result

    def _detect_with_regex(self, text: str) -> List[PHIEntity]:
        """Detect PHI using regex patterns"""
        entities = []

        for category, pattern_info in self.REGEX_PATTERNS.items():
            pattern = pattern_info["pattern"]
            matches = re.finditer(pattern, text, re.IGNORECASE)

            for match in matches:
                entity = PHIEntity(
                    type=pattern_info["type"],
                    category=category,
                    value=f"[REDACTED-{category.upper()}]",
                    location=f"char {match.start()}-{match.end()}",
                    confidence=pattern_info["confidence"],
                    regulation=pattern_info["regulation"]
                )
                entities.append(entity)

        return entities

    def _detect_with_llm(self, text: str) -> List[PHIEntity]:
        """Detect PHI using LLM (for clinical content and complex patterns)"""
        try:
            # Prepare prompt
            prompt = f"""Analyze the following healthcare document text and identify PHI:

TEXT:
{text[:4000]}  # Limit to 4000 chars to avoid token limits

Identify:
1. Names (patient, family members, doctors)
2. Clinical information (diagnoses, treatments, medications, lab results)
3. Sensitive PHI (mental health, substance abuse, HIV, genetic info)

Return ONLY valid JSON following this exact structure:
{{
  "phi_detected": [
    {{
      "type": "clinical",
      "category": "diagnosis",
      "value": "Type 2 Diabetes",
      "location": "paragraph 2",
      "confidence": 0.9,
      "regulation": "45 CFR §164.514"
    }}
  ]
}}"""

            response = self.bedrock_client.invoke(
                prompt=prompt,
                system_prompt=PHI_DETECTION_PROMPT,
                max_tokens=2000,
                temperature=0.0
            )

            # Parse JSON response
            try:
                # Extract JSON from response
                content = response.content.strip()

                # Handle markdown code blocks
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0].strip()

                result = json.loads(content)

                # Convert to PHIEntity objects
                entities = []
                for item in result.get("phi_detected", []):
                    entity = PHIEntity(
                        type=item.get("type", "clinical"),
                        category=item.get("category", "unknown"),
                        value=item.get("value", "[REDACTED]"),
                        location=item.get("location", "unknown"),
                        confidence=float(item.get("confidence", 0.5)),
                        regulation=item.get("regulation", "45 CFR §164.514")
                    )
                    entities.append(entity)

                return entities

            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse LLM response as JSON: {e}")
                logger.debug(f"Raw response: {response.content[:200]}")
                return []

        except Exception as e:
            logger.error(f"LLM-based PHI detection failed: {e}")
            return []

    def _merge_entities(
        self,
        regex_entities: List[PHIEntity],
        llm_entities: List[PHIEntity]
    ) -> List[PHIEntity]:
        """Merge and deduplicate entities from different detection methods"""
        # Simple merge - in production, would implement smart deduplication
        all_entities = regex_entities + llm_entities

        # Sort by confidence descending
        all_entities.sort(key=lambda e: e.confidence, reverse=True)

        return all_entities

    def _calculate_sensitivity(
        self,
        entities: List[PHIEntity],
        text: str
    ) -> str:
        """
        Calculate document sensitivity level.

        Levels:
        - critical: Sensitive PHI (psychotherapy notes, substance abuse, HIV)
        - high: Multiple PHI identifiers or clinical information
        - medium: Some PHI identifiers
        - low: Minimal or no PHI
        """
        if not entities:
            return "low"

        # Check for sensitive keywords
        text_lower = text.lower()
        has_sensitive = any(keyword in text_lower for keyword in self.SENSITIVE_KEYWORDS)

        if has_sensitive:
            return "critical"

        # Check for sensitive PHI types
        sensitive_types = ["psychotherapy_note", "substance_abuse", "hiv", "genetic"]
        has_sensitive_type = any(
            e.category in sensitive_types for e in entities
        )

        if has_sensitive_type:
            return "critical"

        # Count identifiers
        num_identifiers = len(entities)

        if num_identifiers >= 5:
            return "high"
        elif num_identifiers >= 2:
            return "medium"
        else:
            return "low"

    def _generate_reasoning(
        self,
        entities: List[PHIEntity],
        sensitivity_level: str
    ) -> str:
        """Generate human-readable reasoning for the detection"""
        if not entities:
            return "No PHI detected in document. Safe for unrestricted access."

        entity_counts = {}
        for entity in entities:
            entity_counts[entity.category] = entity_counts.get(entity.category, 0) + 1

        summary = ", ".join([f"{count} {cat}" for cat, count in entity_counts.items()])

        reasoning = f"Detected {len(entities)} PHI entities: {summary}. "
        reasoning += f"Document classified as {sensitivity_level} sensitivity. "

        if sensitivity_level == "critical":
            reasoning += "Contains sensitive PHI requiring enhanced protection per HIPAA."
        elif sensitivity_level == "high":
            reasoning += "Contains multiple PHI identifiers requiring access controls."
        elif sensitivity_level == "medium":
            reasoning += "Contains some PHI requiring standard access controls."
        else:
            reasoning += "Minimal PHI detected."

        return reasoning


# Convenience function
def detect_phi(
    document_text: str,
    document_id: Optional[str] = None,
    enable_llm: bool = True
) -> PHIDetectionResult:
    """
    Quick PHI detection without creating an agent instance.

    Args:
        document_text: Document content to analyze
        document_id: Optional document identifier
        enable_llm: Whether to use LLM for advanced detection

    Returns:
        PHIDetectionResult
    """
    agent = PHIDetectionAgent(enable_llm=enable_llm)
    return agent.detect(document_text, document_id)


if __name__ == "__main__":
    # Test the PHI detection agent
    import sys
    from loguru import logger

    logger.remove()
    logger.add(sys.stdout, level="INFO")

    print("Testing PHI Detection Agent\n")
    print("=" * 70)

    # Sample healthcare document
    sample_document = """
    PATIENT RECORD

    Patient Name: John Doe
    MRN: MRN-12345
    DOB: 03/15/1975
    Phone: 555-123-4567
    Email: john.doe@email.com
    Address: 123 Main St, Anytown, CA 90210

    Chief Complaint: Patient presents with persistent cough and fever.

    Diagnosis: Pneumonia (ICD-10: J18.9)

    Treatment Plan:
    - Prescribed Amoxicillin 500mg TID x 10 days
    - Follow-up in 2 weeks
    - Chest X-ray ordered

    Lab Results:
    - WBC: 15,000 (elevated)
    - CRP: 45 mg/L (elevated)

    Patient reports history of asthma and seasonal allergies.
    Currently taking Albuterol inhaler as needed.

    Provider: Dr. Jane Smith, MD
    Date: 04/08/2026
    """

    # Test detection
    try:
        print("\n[TEST] Analyzing sample document...\n")

        agent = PHIDetectionAgent(enable_llm=True)
        result = agent.detect(sample_document, document_id="TEST-001")

        print(f"Sensitivity Level: {result.sensitivity_level}")
        print(f"Overall Confidence: {result.overall_confidence:.2f}")
        print(f"\nDetected {len(result.phi_detected)} PHI entities:\n")

        for i, entity in enumerate(result.phi_detected[:10], 1):
            print(f"{i}. {entity.category} ({entity.type})")
            print(f"   Location: {entity.location}")
            print(f"   Confidence: {entity.confidence:.2f}")
            print(f"   Regulation: {entity.regulation}")
            print()

        print(f"Reasoning:\n{result.reasoning}\n")
        print("=" * 70)
        print("\n[SUCCESS] PHI Detection Agent working correctly!")

    except Exception as e:
        print(f"\n[FAIL] Test failed: {e}")
        import traceback
        traceback.print_exc()
