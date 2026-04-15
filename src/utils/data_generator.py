"""
Synthetic Healthcare Document Generator

Creates realistic synthetic healthcare documents for testing the compliance system.
All data is completely fictional and safe for demos.
"""

import random
from datetime import datetime, timedelta
from typing import List, Dict


class SyntheticDocumentGenerator:
    """Generate synthetic healthcare documents with configurable violations"""

    # Synthetic patient data
    FIRST_NAMES = [
        "James", "Mary", "John", "Patricia", "Robert", "Jennifer", "Michael", "Linda",
        "William", "Elizabeth", "David", "Barbara", "Richard", "Susan", "Joseph", "Jessica"
    ]

    LAST_NAMES = [
        "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
        "Rodriguez", "Martinez", "Hernandez", "Lopez", "Wilson", "Anderson", "Thomas"
    ]

    DIAGNOSES = [
        ("Type 2 Diabetes", "E11.9"),
        ("Hypertension", "I10"),
        ("Hyperlipidemia", "E78.5"),
        ("Coronary Artery Disease", "I25.10"),
        ("Atrial Fibrillation", "I48.91"),
        ("Chronic Kidney Disease", "N18.3"),
        ("COPD", "J44.9"),
        ("Pneumonia", "J18.9"),
        ("Heart Failure", "I50.9"),
        ("Osteoarthritis", "M19.90")
    ]

    SENSITIVE_DIAGNOSES = [
        ("Major Depressive Disorder", "F33.2"),
        ("Generalized Anxiety Disorder", "F41.1"),
        ("Bipolar Disorder", "F31.9"),
        ("PTSD", "F43.10"),
        ("Alcohol Use Disorder", "F10.20"),
        ("Opioid Dependence", "F11.20"),
        ("Cocaine Abuse", "F14.10"),
        ("HIV Infection", "B20"),
        ("Hepatitis C", "B18.2")
    ]

    MEDICATIONS = [
        "Metformin 500mg BID",
        "Lisinopril 10mg daily",
        "Atorvastatin 40mg nightly",
        "Aspirin 81mg daily",
        "Levothyroxine 50mcg daily",
        "Omeprazole 20mg daily",
        "Gabapentin 300mg TID",
        "Amoxicillin 500mg TID x10 days"
    ]

    CITIES = ["Los Angeles", "Chicago", "Houston", "Phoenix", "Philadelphia", "San Antonio"]
    STATES = ["CA", "TX", "NY", "FL", "IL", "PA"]
    STREETS = ["Main St", "Oak Ave", "Elm Street", "Maple Drive", "Cedar Lane", "Pine Road"]

    def __init__(self):
        random.seed(42)  # For reproducible results

    def generate_patient_name(self) -> str:
        """Generate random patient name"""
        first = random.choice(self.FIRST_NAMES)
        last = random.choice(self.LAST_NAMES)
        return f"{first} {last}"

    def generate_mrn(self) -> str:
        """Generate medical record number"""
        return f"MRN-{random.randint(10000, 99999)}"

    def generate_ssn(self) -> str:
        """Generate synthetic SSN"""
        return f"{random.randint(100, 999)}-{random.randint(10, 99)}-{random.randint(1000, 9999)}"

    def generate_phone(self) -> str:
        """Generate phone number"""
        return f"555-{random.randint(100, 999)}-{random.randint(1000, 9999)}"

    def generate_email(self, name: str) -> str:
        """Generate email from name"""
        name_parts = name.lower().split()
        return f"{name_parts[0]}.{name_parts[1]}@email.com"

    def generate_address(self) -> Dict[str, str]:
        """Generate synthetic address"""
        number = random.randint(100, 9999)
        street = random.choice(self.STREETS)
        city = random.choice(self.CITIES)
        state = random.choice(self.STATES)
        zip_code = random.randint(10000, 99999)

        return {
            "street": f"{number} {street}",
            "city": city,
            "state": state,
            "zip": str(zip_code)
        }

    def generate_dob(self, min_age: int = 18, max_age: int = 85) -> str:
        """Generate date of birth"""
        days_old = random.randint(min_age * 365, max_age * 365)
        dob = datetime.now() - timedelta(days=days_old)
        return dob.strftime("%m/%d/%Y")

    def generate_standard_medical_record(
        self,
        include_sensitive: bool = False,
        include_ssn: bool = False
    ) -> str:
        """Generate standard medical record"""
        name = self.generate_patient_name()
        mrn = self.generate_mrn()
        dob = self.generate_dob()
        phone = self.generate_phone()
        email = self.generate_email(name)
        address = self.generate_address()

        # Select diagnosis
        if include_sensitive:
            diagnosis, icd = random.choice(self.SENSITIVE_DIAGNOSES)
        else:
            diagnosis, icd = random.choice(self.DIAGNOSES)

        medications = random.sample(self.MEDICATIONS, k=random.randint(2, 4))

        doc = f"""PATIENT MEDICAL RECORD

Patient Name: {name}
MRN: {mrn}
DOB: {dob}
Phone: {phone}
Email: {email}
Address: {address['street']}, {address['city']}, {address['state']} {address['zip']}
"""

        if include_ssn:
            doc += f"SSN: {self.generate_ssn()}\n"

        doc += f"""
Chief Complaint: {"Persistent symptoms requiring evaluation" if not include_sensitive else "Mental health concerns"}

Diagnosis: {diagnosis} (ICD-10: {icd})

Treatment Plan:
"""
        for med in medications:
            doc += f"- {med}\n"

        doc += f"""
Lab Results:
- CBC: Within normal limits
- BMP: Within normal limits
- HbA1c: {random.uniform(5.5, 7.5):.1f}%

Follow-up: {"2 weeks" if include_sensitive else "3 months"}

Provider: Dr. {random.choice(self.LAST_NAMES)}, MD
Date: {datetime.now().strftime("%m/%d/%Y")}
"""
        return doc

    def generate_psychotherapy_notes(self) -> str:
        """Generate psychotherapy notes (critical PHI)"""
        name = self.generate_patient_name()
        mrn = self.generate_mrn()
        dob = self.generate_dob(min_age=25, max_age=60)

        scenarios = [
            "severe depression and suicidal ideation",
            "trauma from domestic violence",
            "substance abuse and addiction recovery",
            "sexual assault trauma",
            "bipolar disorder with manic episodes"
        ]

        scenario = random.choice(scenarios)

        doc = f"""CONFIDENTIAL PSYCHOTHERAPY NOTES
** RESTRICTED ACCESS - MENTAL HEALTH PROVIDER ONLY **

Patient Name: {name}
MRN: {mrn}
DOB: {dob}
Session Date: {datetime.now().strftime("%m/%d/%Y")}

PRIVATE NOTES - NOT PART OF MEDICAL RECORD

Chief Complaint: Patient presents with {scenario}

Detailed Session Notes:
Patient discussed traumatic experiences in detail. High emotional distress observed.
Patient expressed feelings of hopelessness and discussed self-harm thoughts.
Safety plan reviewed and updated.

Risk Assessment: MODERATE TO HIGH RISK

Treatment Plan:
- Continue weekly therapy sessions
- Psychiatric medication management referral
- Crisis hotline information provided
- Follow-up in 1 week (sooner if crisis)

Therapist: Dr. {random.choice(self.LAST_NAMES)}, LMFT
License: MFT-{random.randint(10000, 99999)}

CRITICAL: These notes are protected under 45 CFR §164.508.
Separate authorization required for release.
"""
        return doc

    def generate_substance_abuse_record(self) -> str:
        """Generate substance abuse treatment record (42 CFR Part 2)"""
        name = self.generate_patient_name()
        mrn = self.generate_mrn()
        dob = self.generate_dob(min_age=21, max_age=65)

        substances = [
            "alcohol",
            "opioids (prescription painkillers)",
            "cocaine",
            "methamphetamine",
            "heroin"
        ]

        substance = random.choice(substances)

        doc = f"""SUBSTANCE ABUSE TREATMENT RECORD
** 42 CFR PART 2 PROTECTED **

Patient Name: {name}
MRN: {mrn}
DOB: {dob}
Admission Date: {(datetime.now() - timedelta(days=30)).strftime("%m/%d/%Y")}

Primary Substance: {substance.upper()}
Duration of Use: {random.randint(2, 15)} years
Last Use: {random.randint(1, 30)} days ago

Treatment Program: Intensive Outpatient Program (IOP)

Progress Notes:
- Patient attending group therapy 3x weekly
- Individual counseling sessions ongoing
- Urine drug screens: {"POSITIVE" if random.random() > 0.7 else "NEGATIVE"}
- Patient showing {"good" if random.random() > 0.5 else "variable"} engagement

Discharge Plan:
- Continue outpatient counseling
- Attend AA/NA meetings
- Relapse prevention planning
- Sober living referral

Counselor: {random.choice(self.FIRST_NAMES)} {random.choice(self.LAST_NAMES)}, CADC
Date: {datetime.now().strftime("%m/%d/%Y")}

NOTICE: Federal law (42 CFR Part 2) protects the confidentiality of substance abuse
treatment records. Unauthorized disclosure is a federal crime.
"""
        return doc

    def generate_hiv_test_result(self) -> str:
        """Generate HIV test result (highly sensitive PHI)"""
        name = self.generate_patient_name()
        mrn = self.generate_mrn()
        dob = self.generate_dob(min_age=18, max_age=70)

        doc = f"""CONFIDENTIAL LAB RESULTS - HIV TESTING

Patient Name: {name}
MRN: {mrn}
DOB: {dob}
SSN: {self.generate_ssn()}
Test Date: {datetime.now().strftime("%m/%d/%Y")}

Test Ordered: HIV-1/HIV-2 Antibody Screen with Reflex

RESULTS:
- HIV-1/2 Antibody Screen: {"REACTIVE" if random.random() > 0.9 else "NON-REACTIVE"}
- CD4 Count: {random.randint(200, 800)} cells/µL
{"- Viral Load: " + str(random.randint(20, 100000)) + " copies/mL" if random.random() > 0.9 else ""}

Clinical Interpretation:
{"Patient counseled on positive result. Referred to infectious disease specialist." if random.random() > 0.9 else "Negative result. Continue preventive measures."}

Ordering Provider: Dr. {random.choice(self.LAST_NAMES)}, MD
Lab: Quest Diagnostics

CONFIDENTIAL: HIV test results are protected by state and federal law.
Unauthorized disclosure may result in legal penalties.
"""
        return doc

    def generate_simple_visit_note(self) -> str:
        """Generate simple visit note (minimal PHI)"""
        name = self.generate_patient_name()
        mrn = self.generate_mrn()

        doc = f"""VISIT SUMMARY

Patient: {name}
MRN: {mrn}
Visit Date: {datetime.now().strftime("%m/%d/%Y")}

Reason: Annual physical examination

Vitals:
- BP: {random.randint(110, 140)}/{random.randint(70, 90)} mmHg
- HR: {random.randint(60, 90)} bpm
- Temp: 98.6°F
- Weight: {random.randint(120, 220)} lbs

Assessment: Overall good health. Continue current care plan.

Plan:
- Continue current medications
- Follow-up in 12 months

Dr. {random.choice(self.LAST_NAMES)}, MD
"""
        return doc

    def generate_document_set(self) -> List[Dict]:
        """Generate a set of documents for testing"""
        return [
            {
                "name": "Standard Medical Record (Low Severity)",
                "content": self.generate_standard_medical_record(),
                "suggested_access": ["physician", "nurse", "billing_staff", "patient"],
                "document_type": "medical_record",
                "severity": "low"
            },
            {
                "name": "Medical Record with SSN (Medium Severity)",
                "content": self.generate_standard_medical_record(include_ssn=True),
                "suggested_access": ["physician", "nurse", "patient"],
                "document_type": "medical_record",
                "severity": "medium"
            },
            {
                "name": "Mental Health Record (High Severity)",
                "content": self.generate_standard_medical_record(include_sensitive=True, include_ssn=True),
                "suggested_access": ["physician", "nurse", "patient"],
                "document_type": "medical_record",
                "severity": "high"
            },
            {
                "name": "Psychotherapy Notes (CRITICAL)",
                "content": self.generate_psychotherapy_notes(),
                "suggested_access": ["psychotherapist", "patient"],
                "document_type": "psychotherapy_notes",
                "severity": "critical"
            },
            {
                "name": "Substance Abuse Record (CRITICAL - 42 CFR Part 2)",
                "content": self.generate_substance_abuse_record(),
                "suggested_access": ["treating_physician", "patient"],
                "document_type": "medical_record",
                "severity": "critical"
            },
            {
                "name": "HIV Test Results (CRITICAL)",
                "content": self.generate_hiv_test_result(),
                "suggested_access": ["physician", "patient"],
                "document_type": "medical_record",
                "severity": "critical"
            },
            {
                "name": "Simple Visit Note (Minimal PHI)",
                "content": self.generate_simple_visit_note(),
                "suggested_access": ["physician", "nurse", "billing_staff", "patient"],
                "document_type": "medical_record",
                "severity": "low"
            }
        ]


if __name__ == "__main__":
    generator = SyntheticDocumentGenerator()
    documents = generator.generate_document_set()

    print("=" * 70)
    print("SYNTHETIC HEALTHCARE DOCUMENTS FOR TESTING")
    print("=" * 70)

    for i, doc in enumerate(documents, 1):
        print(f"\n\n{'='*70}")
        print(f"DOCUMENT {i}: {doc['name']}")
        print(f"Severity: {doc['severity'].upper()}")
        print(f"Type: {doc['document_type']}")
        print(f"Suggested Access: {', '.join(doc['suggested_access'])}")
        print(f"{'='*70}\n")
        print(doc['content'])
        print("\n" + "-"*70)

    print("\n\n[SUCCESS] Generated 7 synthetic documents for testing!")
