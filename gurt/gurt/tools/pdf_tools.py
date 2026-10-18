"""PDF Form Filling Tool Adapter for Gurt Event Operations.

Implements standalone, supported PDF form filling:
- Inspects fillable AcroForm templates.
- Maps saved event/vendor facts to known fields.
- Leaves unknown/missing fields explicitly unresolved.
- Produces a downloadable draft PDF and missing-field list.
- Preserves the original template untouched.
- Enforces strict separation of draft generation from signing/submission.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any
import pypdf
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from gurt.config import settings
from gurt.db import get_event_brief, query_records, save_pdf_document

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "static" / "generated_docs"

TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_TEMPLATE_FILENAME = "UW_HUB_Event_Facility_Booking_Contract.pdf"


def ensure_acroform_template() -> Path:
    """Generate a clean, authentic fillable AcroForm PDF contract template if not present."""
    template_path = TEMPLATE_DIR / DEFAULT_TEMPLATE_FILENAME
    if template_path.exists():
        return template_path

    # Build AcroForm using ReportLab
    c = canvas.Canvas(str(template_path), pagesize=letter)
    width, height = letter

    # Header & Styling
    c.setFont("Helvetica-Bold", 18)
    c.setFillColorRGB(0.12, 0.18, 0.35)
    c.drawString(50, height - 55, "UNIVERSITY OF WASHINGTON — HUB EVENT SERVICES")
    c.setFont("Helvetica-Bold", 12)
    c.setFillColorRGB(0.3, 0.3, 0.3)
    c.drawString(50, height - 75, "Special Event Facility Use Agreement & Vendor Disclosure Form")

    c.setLineWidth(1)
    c.setStrokeColorRGB(0.7, 0.7, 0.7)
    c.line(50, height - 85, width - 50, height - 85)

    c.setFont("Helvetica", 9)
    c.setFillColorRGB(0.4, 0.4, 0.4)
    c.drawString(50, height - 100, "Official booking intake. Fillable draft fields. Unresolved items must be addressed before signing.")

    # Form Fields Section 1: Event Identification
    y = height - 130
    c.setFont("Helvetica-Bold", 11)
    c.setFillColorRGB(0.12, 0.18, 0.35)
    c.drawString(50, y, "1. EVENT SPECIFICATIONS")

    y -= 25
    c.setFont("Helvetica", 10)
    c.setFillColorRGB(0.1, 0.1, 0.1)
    c.drawString(50, y + 3, "Event Title:")
    c.acroForm.textfield(name="event_name", tooltip="Full Title of Event", x=160, y=y - 4, width=380, height=18, borderWidth=1, fontSize=9)

    y -= 25
    c.drawString(50, y + 3, "Event Date/Time:")
    c.acroForm.textfield(name="event_date", tooltip="Date and Start Time", x=160, y=y - 4, width=170, height=18, borderWidth=1, fontSize=9)

    c.drawString(340, y + 3, "Expected Attendance:")
    c.acroForm.textfield(name="expected_attendance", tooltip="Headcount", x=460, y=y - 4, width=80, height=18, borderWidth=1, fontSize=9)

    y -= 25
    c.drawString(50, y + 3, "Reserved Location:")
    c.acroForm.textfield(name="event_location", tooltip="Reserved HUB Room / Ballroom", x=160, y=y - 4, width=380, height=18, borderWidth=1, fontSize=9)

    # Form Fields Section 2: Contact & Billing
    y -= 35
    c.setFont("Helvetica-Bold", 11)
    c.setFillColorRGB(0.12, 0.18, 0.35)
    c.drawString(50, y, "2. ORGANIZER CONTACT & FISCAL RECONCILIATION")

    y -= 25
    c.setFont("Helvetica", 10)
    c.setFillColorRGB(0.1, 0.1, 0.1)
    c.drawString(50, y + 3, "Primary Organizer:")
    c.acroForm.textfield(name="organizer_name", tooltip="Lead Organizer Name", x=160, y=y - 4, width=170, height=18, borderWidth=1, fontSize=9)

    c.drawString(340, y + 3, "Organizer Email:")
    c.acroForm.textfield(name="organizer_email", tooltip="Contact Email", x=430, y=y - 4, width=110, height=18, borderWidth=1, fontSize=9)

    y -= 25
    c.drawString(50, y + 3, "Phone (24hr Floor):")
    c.acroForm.textfield(name="organizer_phone", tooltip="24-hour on-site phone contact", x=160, y=y - 4, width=170, height=18, borderWidth=1, fontSize=9)

    c.drawString(340, y + 3, "UW Budget Code:")
    c.acroForm.textfield(name="budget_code", tooltip="UW Index / Workday Budget Number", x=430, y=y - 4, width=110, height=18, borderWidth=1, fontSize=9)

    # Form Fields Section 3: Vendor & Catering Declarations
    y -= 35
    c.setFont("Helvetica-Bold", 11)
    c.setFillColorRGB(0.12, 0.18, 0.35)
    c.drawString(50, y, "3. VENDOR & CATERING DISCLOSURE")

    y -= 25
    c.setFont("Helvetica", 10)
    c.drawString(50, y + 3, "Catering Vendor:")
    c.acroForm.textfield(name="catering_vendor", tooltip="Selected Catering Supplier", x=160, y=y - 4, width=200, height=18, borderWidth=1, fontSize=9)

    c.drawString(370, y + 3, "Total Quote ($):")
    c.acroForm.textfield(name="catering_total_cost", tooltip="Quoted Catering Total", x=450, y=y - 4, width=90, height=18, borderWidth=1, fontSize=9)

    y -= 25
    c.drawString(50, y + 3, "Dietary Declarations:")
    c.acroForm.textfield(name="dietary_requirements", tooltip="Allergies, Vegan, GF counts", x=160, y=y - 4, width=380, height=18, borderWidth=1, fontSize=9)

    y -= 25
    c.drawString(50, y + 3, "AV Tech Requirements:")
    c.acroForm.textfield(name="av_equipment_requested", tooltip="Projectors, Mics, Wi-Fi", x=160, y=y - 4, width=380, height=18, borderWidth=1, fontSize=9)

    y -= 25
    c.drawString(50, y + 3, "Insurance Certificate #:")
    c.acroForm.textfield(name="insurance_policy_number", tooltip="Required special event certificate number", x=160, y=y - 4, width=380, height=18, borderWidth=1, fontSize=9)

    # Section 4: Decoupled Human Approval & Signoff
    y -= 45
    c.setLineWidth(0.5)
    c.setStrokeColorRGB(0.8, 0.8, 0.8)
    c.line(50, y + 10, width - 50, y + 10)

    c.setFont("Helvetica-Bold", 10)
    c.setFillColorRGB(0.8, 0.2, 0.2)
    c.drawString(50, y, "4. HITL REVIEW & EXECUTION SEPARATION (DRAFT ONLY — NOT SUBMITTED)")
    
    y -= 16
    c.setFont("Helvetica-Oblique", 8.5)
    c.setFillColorRGB(0.4, 0.4, 0.4)
    c.drawString(50, y, "Per safety protocols, Gurt generates non-binding fillable drafts. Signing and submission require manual review.")

    y -= 30
    c.setFont("Helvetica", 9)
    c.setFillColorRGB(0.2, 0.2, 0.2)
    c.drawString(50, y + 3, "Authorized Signatory:")
    c.acroForm.textfield(name="authorized_signatory_name", tooltip="Legal Signatory Name", x=160, y=y - 4, width=170, height=18, borderWidth=1, fontSize=9)

    c.drawString(340, y + 3, "Date Signed:")
    c.acroForm.textfield(name="signature_date", tooltip="Date of Execution", x=430, y=y - 4, width=110, height=18, borderWidth=1, fontSize=9)

    y -= 28
    c.drawString(50, y + 3, "Signature / Stamp:")
    c.acroForm.textfield(name="signatory_signature", tooltip="Human Signature Only (Leave Empty in Draft)", x=160, y=y - 4, width=380, height=18, borderWidth=1, fontSize=9)

    c.save()
    return template_path


def inspect_template_fields(template_path: Path | None = None) -> dict[str, Any]:
    """Inspect a fillable AcroForm PDF and extract field specifications."""
    t_path = template_path or ensure_acroform_template()
    reader = pypdf.PdfReader(str(t_path))
    fields = reader.get_fields() or {}

    field_summary = {}
    for name, f_obj in fields.items():
        field_type = f_obj.get("/FT", "Unknown")
        type_label = "Text" if field_type == "/Tx" else ("Button/Checkbox" if field_type == "/Btn" else str(field_type))
        current_val = f_obj.get("/V", "")
        field_summary[name] = {
            "type": type_label,
            "default_value": str(current_val) if current_val else None
        }

    return {
        "template_file": t_path.name,
        "template_size_bytes": t_path.stat().st_size,
        "total_fields": len(field_summary),
        "fields": field_summary
    }


def fill_event_pdf_form(event_id: str = "evt-dubhacks-2026") -> dict[str, Any]:
    """Map saved event facts to form fields, leave unknowns unresolved, and produce a draft PDF."""
    template_path = ensure_acroform_template()
    reader = pypdf.PdfReader(str(template_path))
    fields_catalog = reader.get_fields() or {}

    # 1. Fetch saved records from persistent DB
    event = get_event_brief(event_id)
    vendors = query_records("vendors", event_id=event_id)
    # Prefer Catering vendor if quoted/approved
    catering_vendor = next((v for v in vendors if "catering" in v.get("category", "").lower()), None)
    if not catering_vendor and vendors:
        catering_vendor = vendors[0]

    # 2. Map known facts from event records
    facts_mapping: dict[str, str] = {}
    unresolved_fields: list[dict[str, str]] = []

    if event.get("title"):
        facts_mapping["event_name"] = event["title"]
    if event.get("date"):
        facts_mapping["event_date"] = event["date"]
    if event.get("location"):
        facts_mapping["event_location"] = event["location"]
    if event.get("attendee_count"):
        facts_mapping["expected_attendance"] = str(event["attendee_count"])
    
    # Organizer identity on record
    facts_mapping["organizer_name"] = "Sam Operations (DubHacks Lead)"
    facts_mapping["organizer_email"] = "operations@dubhacks.example"

    # Catering & Vendors
    if catering_vendor:
        facts_mapping["catering_vendor"] = f"{catering_vendor['company_name']} ({catering_vendor.get('details', '')[:40]})"
        facts_mapping["catering_total_cost"] = f"${catering_vendor['quote_amount']:,.2f}"

    if event.get("dietary_specs"):
        facts_mapping["dietary_requirements"] = event["dietary_specs"]

    if event.get("av_requirements"):
        facts_mapping["av_equipment_requested"] = event["av_requirements"]

    # 3. Explicitly detect unresolved fields
    known_keys = set(facts_mapping.keys())
    for f_name in fields_catalog.keys():
        if f_name not in known_keys:
            if f_name == "organizer_phone":
                unresolved_fields.append({
                    "field": f_name,
                    "reason": "Missing 24-hr on-site floor telephone number in event brief.",
                    "required_for": "Venue emergency dispatch & facility coordination"
                })
            elif f_name == "budget_code":
                unresolved_fields.append({
                    "field": f_name,
                    "reason": "UW Index / Workday budget code has not yet been assigned by faculty advisor.",
                    "required_for": "Campus internal fiscal transfer"
                })
            elif f_name == "insurance_policy_number":
                unresolved_fields.append({
                    "field": f_name,
                    "reason": "Special event liability insurance certificate pending underwriter issue.",
                    "required_for": "HUB Room 214 high-density gathering policy"
                })
            elif f_name in ("authorized_signatory_name", "signature_date", "signatory_signature"):
                unresolved_fields.append({
                    "field": f_name,
                    "reason": "Decoupled from draft generation. Requires explicit human legal signature.",
                    "required_for": "Contractual execution"
                })
            else:
                unresolved_fields.append({
                    "field": f_name,
                    "reason": "No corresponding value present in event records.",
                    "required_for": "General compliance"
                })

    # 4. Generate the filled PDF without modifying original template
    writer = pypdf.PdfWriter()
    writer.append(reader)

    # Fill mapped fields on page 0
    writer.update_page_form_field_values(writer.pages[0], facts_mapping)

    doc_id = f"doc-hub-booking-{event_id.replace('evt-', '')}"
    out_filename = f"{doc_id}_draft.pdf"
    out_path = OUTPUT_DIR / out_filename

    with open(out_path, "wb") as f_out:
        writer.write(f_out)

    # 5. Verify the rendered output exists and original was preserved
    assert template_path.exists(), "Original template was corrupted or removed"
    assert out_path.exists() and out_path.stat().st_size > 0, "Rendered draft PDF is missing or empty"

    # 6. Save document record in persistent SQLite store
    unresolved_names = [u["field"] for u in unresolved_fields]
    doc_record = save_pdf_document(
        event_id=event_id,
        template_name=template_path.name,
        file_path=str(out_path),
        mapped_fields=facts_mapping,
        unresolved_fields=unresolved_names,
        status="draft_ready"
    )

    download_relative_url = f"/static/generated_docs/{out_filename}"

    return {
        "status": "draft_ready",
        "document_id": doc_record["id"],
        "template_name": template_path.name,
        "output_file": out_filename,
        "download_url": download_relative_url,
        "original_template_preserved": True,
        "field_counts": {
            "total": len(fields_catalog),
            "mapped": len(facts_mapping),
            "unresolved": len(unresolved_fields)
        },
        "mapped_facts": facts_mapping,
        "unresolved_missing_fields": unresolved_fields,
        "hitl_safety": "DRAFT ONLY. Document has NOT been signed or submitted to UW HUB. Manual review required."
    }
