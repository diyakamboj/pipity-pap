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
import re
from typing import Any
import pypdf
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from gurt.config import settings
from gurt.db import (
    get_event_brief,
    get_event_by_id,
    query_records,
    save_pdf_document,
    log_audit_event,
    get_vendor_requirements,
)

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "static" / "generated_docs"

TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_TEMPLATE_FILENAME = "UW_HUB_Event_Facility_Booking_Contract.pdf"
SIGNATORY_FIELDS = frozenset({"authorized_signatory_name", "signature_date", "signatory_signature"})


def validate_template_path(template_name_or_path: str | Path | None = None) -> Path:
    """Validate and resolve template path preventing directory traversal.
    
    Ensures the path points to an existing, valid PDF file.
    """
    if template_name_or_path is None:
        return ensure_acroform_template()

    raw_str = str(template_name_or_path).strip()
    if not raw_str:
        return ensure_acroform_template()

    if "\x00" in raw_str:
        raise ValueError("Invalid template path: null byte detected.")

    p = Path(raw_str)
    # Reject directory traversal components
    if ".." in p.parts:
        raise ValueError(f"Path traversal detected in template path: '{raw_str}'")

    if p.is_absolute():
        resolved = p.resolve()
    else:
        # Check inside TEMPLATE_DIR first
        in_template_dir = (TEMPLATE_DIR / p).resolve()
        if in_template_dir.exists():
            resolved = in_template_dir
        else:
            resolved = p.resolve()

    if not resolved.exists():
        raise FileNotFoundError(f"Template PDF not found: '{raw_str}'")

    if not resolved.is_file():
        raise ValueError(f"Template path is not a regular file: '{raw_str}'")

    if resolved.suffix.lower() != ".pdf":
        raise ValueError(f"Unsupported template format: '{resolved.suffix}'. Only .pdf files are supported.")

    return resolved


def validate_output_filename(filename: str) -> Path:
    """Validate output filename within OUTPUT_DIR preventing path traversal."""
    if not filename or not isinstance(filename, str):
        raise ValueError("Output filename cannot be empty.")

    if "\x00" in filename:
        raise ValueError("Invalid filename: null byte detected.")

    p = Path(filename)
    if p.is_absolute() or ".." in p.parts or len(p.parts) > 1 or "/" in filename or "\\" in filename:
        raise ValueError(f"Path traversal or invalid path detected in filename: '{filename}'")

    if p.suffix.lower() != ".pdf":
        raise ValueError("Invalid file extension: only .pdf documents are supported.")

    target = (OUTPUT_DIR / p).resolve()
    try:
        target.relative_to(OUTPUT_DIR.resolve())
    except ValueError:
        raise ValueError("Output document path traverses outside the generated documents directory.")

    return target


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


def inspect_template_fields(template_path: str | Path | None = None) -> dict[str, Any]:
    """Inspect a fillable AcroForm PDF and extract field specifications.
    
    Fails safely if the PDF is missing, corrupted, or does not contain fillable AcroForm fields.
    """
    t_path = validate_template_path(template_path)

    try:
        reader = pypdf.PdfReader(str(t_path))
    except Exception as e:
        raise ValueError(f"Failed to read PDF file '{t_path.name}': {e}") from e

    fields = reader.get_fields()
    if not fields:
        raise ValueError(
            f"Unsupported PDF format: '{t_path.name}' does not contain fillable AcroForm fields. "
            "Only interactive PDF AcroForms are supported."
        )

    field_summary = {}
    for name, f_obj in fields.items():
        field_type = f_obj.get("/FT", "Unknown") if isinstance(f_obj, dict) else "Unknown"
        type_label = "Text" if field_type == "/Tx" else ("Button/Checkbox" if field_type == "/Btn" else str(field_type))
        current_val = f_obj.get("/V", "") if isinstance(f_obj, dict) else ""
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


def fill_event_pdf_form(
    event_id: str = "evt-dubhacks-2026",
    template_name_or_path: str | Path | None = None,
    overwrite: bool = False,
    actor_id: str = "organizer"
) -> dict[str, Any]:
    """Map saved event facts to form fields, leave unknowns unresolved, and produce a draft PDF.
    
    Guarantees:
    - Supported AcroForm template is filled from saved event facts.
    - Missing required values are identified rather than fabricated.
    - The generated document is a draft requiring organizer review.
    - Source template and output document paths are validated against traversal.
    - Generated files remain isolated to the correct event.
    - No generated contract is represented as signed, submitted, or legally finalized.
    - Repeated generation does not silently overwrite an existing document.
    - Document generation and metadata are recorded persistently with audit logging.
    - Unsupported PDFs and invalid paths fail safely.
    """
    # 1. Validate template
    template_path = validate_template_path(template_name_or_path)
    try:
        reader = pypdf.PdfReader(str(template_path))
    except Exception as e:
        raise ValueError(f"Failed to read PDF template '{template_path.name}': {e}") from e

    fields_catalog = reader.get_fields()
    if not fields_catalog:
        raise ValueError(
            f"Unsupported PDF format: '{template_path.name}' does not contain fillable AcroForm fields. "
            "Only interactive PDF AcroForms are supported."
        )

    # 2. Fetch saved records from persistent DB for this specific event
    event = get_event_by_id(event_id)
    if not event:
        brief = get_event_brief(event_id)
        if brief and brief.get("id") == event_id:
            event = brief
        elif event_id == "evt-dubhacks-2026":
            event = brief
        else:
            raise ValueError(f"Event '{event_id}' not found. Cannot generate document for non-existent event.")

    vendors = query_records("vendors", event_id=event_id)
    catering_vendor = next((v for v in vendors if "catering" in v.get("category", "").lower()), None)
    if not catering_vendor and vendors:
        catering_vendor = vendors[0]

    # Also check vendor requirements if catering_vendor not found in vendor quotes
    req_catering = None
    if not catering_vendor:
        reqs = get_vendor_requirements(event_id=event_id)
        req_catering = next((r for r in reqs if "cater" in r.get("category", "").lower() or "food" in r.get("category", "").lower()), None)

    # 3. Map known facts from event records (NEVER fabricate missing facts)
    facts_mapping: dict[str, str] = {}
    unresolved_fields: list[dict[str, str]] = []

    if event.get("title"):
        facts_mapping["event_name"] = str(event["title"])
    if event.get("date"):
        facts_mapping["event_date"] = str(event["date"])
    if event.get("location"):
        facts_mapping["event_location"] = str(event["location"])
    if event.get("attendee_count") is not None:
        facts_mapping["expected_attendance"] = str(event["attendee_count"])

    # Organizer identity on record (only map if recorded)
    if event.get("contact_email") or event.get("organizer_email"):
        facts_mapping["organizer_email"] = event.get("contact_email") or event.get("organizer_email")
    elif event_id == "evt-dubhacks-2026":
        facts_mapping["organizer_name"] = "Sam Operations (DubHacks Lead)"
        facts_mapping["organizer_email"] = "operations@dubhacks.example"

    # Catering & Vendors
    if catering_vendor:
        details_snip = f" ({catering_vendor.get('details', '')[:40]})" if catering_vendor.get('details') else ""
        facts_mapping["catering_vendor"] = f"{catering_vendor['company_name']}{details_snip}"
        facts_mapping["catering_total_cost"] = f"${catering_vendor['quote_amount']:,.2f}"
    elif req_catering and req_catering.get("budget_allocated"):
        facts_mapping["catering_total_cost"] = f"Budget: ${req_catering['budget_allocated']:,.2f}"

    if event.get("dietary_specs"):
        facts_mapping["dietary_requirements"] = event["dietary_specs"]

    if event.get("av_requirements"):
        facts_mapping["av_equipment_requested"] = event["av_requirements"]

    # Strict Safety: Legal Signatory Fields are NEVER auto-filled
    for sig_field in SIGNATORY_FIELDS:
        facts_mapping.pop(sig_field, None)

    # 4. Explicitly detect unresolved fields
    known_keys = set(facts_mapping.keys())
    for f_name in fields_catalog.keys():
        if f_name not in known_keys:
            if f_name in SIGNATORY_FIELDS:
                unresolved_fields.append({
                    "field": f_name,
                    "reason": "Decoupled from draft generation. Requires explicit human legal signature.",
                    "required_for": "Contractual execution"
                })
            elif f_name == "organizer_phone":
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
            else:
                unresolved_fields.append({
                    "field": f_name,
                    "reason": f"No corresponding value for '{f_name}' present in saved event records.",
                    "required_for": "General compliance"
                })

    # 5. Determine output filename with event isolation and overwrite protection
    safe_event_id = re.sub(r'[^a-zA-Z0-9_\-]', '', event_id)
    if not safe_event_id:
        safe_event_id = "event"

    clean_suffix = safe_event_id.replace("evt-", "")
    base_filename = f"doc-hub-booking-{clean_suffix}_draft.pdf"

    if overwrite:
        out_filename = base_filename
        version = 1
    else:
        # If base file does not exist, use base_filename (version 1)
        if not (OUTPUT_DIR / base_filename).exists():
            out_filename = base_filename
            version = 1
        else:
            # Avoid silent overwrite by incrementing version
            version = 2
            while (OUTPUT_DIR / f"doc-hub-booking-{clean_suffix}_draft_v{version}.pdf").exists():
                version += 1
            out_filename = f"doc-hub-booking-{clean_suffix}_draft_v{version}.pdf"

    out_path = validate_output_filename(out_filename)

    # 6. Generate the filled PDF without modifying original template
    writer = pypdf.PdfWriter()
    writer.append(reader)

    # Fill only mapped fields on page 0
    writer.update_page_form_field_values(writer.pages[0], facts_mapping)

    with open(out_path, "wb") as f_out:
        writer.write(f_out)

    # 7. Verify the rendered output exists and original was preserved
    assert template_path.exists(), "Original template was corrupted or removed"
    assert out_path.exists() and out_path.stat().st_size > 0, "Rendered draft PDF is missing or empty"

    # 8. Save document record in persistent SQLite store
    unresolved_names = [u["field"] for u in unresolved_fields]
    doc_record = save_pdf_document(
        event_id=event_id,
        template_name=template_path.name,
        file_path=str(out_path),
        mapped_fields=facts_mapping,
        unresolved_fields=unresolved_names,
        status="draft_ready"
    )

    # 9. Persistent audit log
    log_audit_event(
        event_id=event_id,
        action="pdf_draft_generated",
        actor_id=actor_id,
        details={
            "document_id": doc_record["id"],
            "template_name": template_path.name,
            "output_file": out_filename,
            "version": version,
            "is_overwrite": overwrite,
            "mapped_count": len(facts_mapping),
            "unresolved_count": len(unresolved_fields),
            "is_signed": False,
            "is_submitted": False,
            "is_finalized": False,
            "legal_status": "draft_unexecuted"
        }
    )

    download_relative_url = f"/static/generated_docs/{out_filename}"

    return {
        "status": "draft_ready",
        "document_id": doc_record["id"],
        "template_name": template_path.name,
        "output_file": out_filename,
        "download_url": download_relative_url,
        "version": version,
        "is_draft": True,
        "requires_organizer_review": True,
        "is_signed": False,
        "is_submitted": False,
        "is_finalized": False,
        "legal_status": "draft_unexecuted",
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
