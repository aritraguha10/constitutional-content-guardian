"""
PDF Generator for Synthetic Healthcare Documents

Converts synthetic healthcare documents into PDF format for testing the dashboard.
"""

import os
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from data_generator import SyntheticDocumentGenerator


def create_pdf(content: str, filename: str, output_dir: str = "data/sample_documents"):
    """Create a PDF from document content"""

    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)

    filepath = os.path.join(output_dir, filename)

    # Create PDF document
    doc = SimpleDocTemplate(
        filepath,
        pagesize=letter,
        rightMargin=0.75*inch,
        leftMargin=0.75*inch,
        topMargin=0.75*inch,
        bottomMargin=0.75*inch
    )

    # Define styles
    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=14,
        textColor='darkblue',
        spaceAfter=12,
        alignment=TA_CENTER
    )

    header_style = ParagraphStyle(
        'CustomHeader',
        parent=styles['Heading2'],
        fontSize=11,
        textColor='darkred',
        spaceAfter=8,
        alignment=TA_CENTER
    )

    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=10,
        spaceAfter=6,
        alignment=TA_LEFT
    )

    # Build document content
    story = []

    # Parse content and add to story
    lines = content.strip().split('\n')

    for line in lines:
        line = line.strip()

        if not line:
            story.append(Spacer(1, 0.1*inch))
            continue

        # Detect headers and special formatting
        if line.startswith('**') and line.endswith('**'):
            # Bold header
            text = line.replace('**', '')
            story.append(Paragraph(f"<b>{text}</b>", header_style))
        elif 'CONFIDENTIAL' in line.upper() or 'RESTRICTED' in line.upper() or 'CRITICAL' in line.upper():
            # Critical warnings in red
            story.append(Paragraph(f"<b><font color='red'>{line}</font></b>", normal_style))
        elif line.startswith('Patient Name:') or line.startswith('PATIENT MEDICAL RECORD'):
            # Title
            story.append(Paragraph(f"<b>{line}</b>", title_style))
        elif ':' in line and len(line.split(':')[0]) < 30:
            # Field: Value format
            parts = line.split(':', 1)
            story.append(Paragraph(f"<b>{parts[0]}:</b> {parts[1].strip()}", normal_style))
        elif line.startswith('-'):
            # Bullet point
            story.append(Paragraph(f"&bull; {line[1:].strip()}", normal_style))
        else:
            # Normal text
            story.append(Paragraph(line, normal_style))

    # Build PDF
    doc.build(story)
    print(f"[OK] Created: {filepath}")
    return filepath


def generate_all_pdfs():
    """Generate PDF versions of all synthetic documents"""

    generator = SyntheticDocumentGenerator()
    documents = generator.generate_document_set()

    print("=" * 70)
    print("GENERATING PDF DOCUMENTS FOR TESTING")
    print("=" * 70)

    pdf_files = []

    for i, doc in enumerate(documents, 1):
        filename = f"doc{i}_{doc['name'].lower().replace(' ', '_').replace('(', '').replace(')', '').replace('-', '_')}.pdf"
        filepath = create_pdf(doc['content'], filename)
        pdf_files.append({
            'filename': filename,
            'filepath': filepath,
            'name': doc['name'],
            'severity': doc['severity'],
            'document_type': doc['document_type'],
            'suggested_access': doc['suggested_access']
        })
        print(f"  Document {i}: {doc['name']}")

    print("\n" + "=" * 70)
    print(f"[SUCCESS] Generated {len(pdf_files)} PDF documents!")
    print(f"Location: {os.path.abspath('data/sample_documents')}")
    print("=" * 70)

    return pdf_files


if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
    from src.utils.data_generator import SyntheticDocumentGenerator

    generate_all_pdfs()
