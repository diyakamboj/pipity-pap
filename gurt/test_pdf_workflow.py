"""Focused Automated Tests for Gurt PDF Document Generation Workflow.

Covers:
1. Supported PDF AcroForm template is filled from saved event facts.
2. Missing required values are identified rather than fabricated.
3. The generated document is a draft requiring organizer review.
4. Source template and output document paths are validated against traversal.
5. Generated files remain isolated to the correct event.
6. No generated contract is represented as signed, submitted, or legally finalized.
7. Repeated generation does not silently overwrite an existing document (auto-versioning).
8. Document generation and metadata are recorded persistently with audit logging.
9. Unsupported PDFs (flat/scanned) and invalid paths fail safely.
10. Synthetic event data and local fixtures only.
11. FastAPI REST API endpoints (/api/pdf/inspect, /api/pdf/fill, /api/pdf/documents, /api/pdf/download/{filename}).
"""

from __future__ import annotations

import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

# Add gurt root to sys.path
GURT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(GURT_ROOT))

import pypdf
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from fastapi.testclient import TestClient

from gurt.db import (
    get_connection,
    init_db,
    save_pdf_document,
    get_pdf_documents,
    get_pdf_document_by_id,
    get_event_by_id,
    log_audit_event,
    get_audit_logs,
)
from gurt.tools.pdf_tools import (
    ensure_acroform_template,
    validate_template_path,
    validate_output_filename,
    inspect_template_fields,
    fill_event_pdf_form,
    OUTPUT_DIR,
    TEMPLATE_DIR,
    SIGNATORY_FIELDS,
)
from gurt.api.server import app


class TestPdfWorkflow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.client = TestClient(app)

    def test_01_inspect_template_fields_valid_acroform(self):
        """Verify inspecting a supported AcroForm template returns field specifications."""
        template_info = inspect_template_fields()
        self.assertIn("template_file", template_info)
        self.assertGreaterEqual(template_info["total_fields"], 14)
        fields = template_info["fields"]
        self.assertIn("event_name", fields)
        self.assertIn("event_date", fields)
        self.assertIn("catering_vendor", fields)
        self.assertIn("signatory_signature", fields)
        self.assertEqual(fields["event_name"]["type"], "Text")

    def test_02_fill_event_pdf_form_from_saved_facts(self):
        """Verify filling form from saved event facts without corrupting the original template."""
        orig_template = ensure_acroform_template()
        orig_mtime = orig_template.stat().st_mtime
        orig_size = orig_template.stat().st_size

        result = fill_event_pdf_form("evt-dubhacks-2026")
        self.assertEqual(result["status"], "draft_ready")
        self.assertTrue(result["original_template_preserved"])
        self.assertGreaterEqual(result["field_counts"]["mapped"], 7)

        # Confirm original template untouched
        self.assertEqual(orig_template.stat().st_size, orig_size)
        self.assertEqual(orig_template.stat().st_mtime, orig_mtime)

        # Output file exists and is valid readable PDF
        out_path = OUTPUT_DIR / result["output_file"]
        self.assertTrue(out_path.exists())
        self.assertGreater(out_path.stat().st_size, 0)

        reader = pypdf.PdfReader(str(out_path))
        self.assertGreater(len(reader.pages), 0)
        filled_fields = reader.get_fields()
        self.assertIsNotNone(filled_fields)
        self.assertEqual(filled_fields["event_name"].get("/V"), "DubHacks 2026 Agentic AI Workshop")

    def test_03_missing_required_values_identified_not_fabricated(self):
        """Verify missing values are listed as unresolved rather than fabricated."""
        result = fill_event_pdf_form("evt-dubhacks-2026")
        unresolved = result["unresolved_missing_fields"]
        unresolved_field_names = {u["field"] for u in unresolved}

        # Known missing fields in brief
        self.assertIn("organizer_phone", unresolved_field_names)
        self.assertIn("budget_code", unresolved_field_names)
        self.assertIn("insurance_policy_number", unresolved_field_names)

        # Ensure reasons and requirements are populated
        phone_item = next(u for u in unresolved if u["field"] == "organizer_phone")
        self.assertIn("reason", phone_item)
        self.assertIn("required_for", phone_item)

        # None of the unresolved fields should be in mapped_facts
        mapped_keys = set(result["mapped_facts"].keys())
        for f in unresolved_field_names:
            self.assertNotIn(f, mapped_keys)

    def test_04_generated_document_is_draft_requiring_organizer_review(self):
        """Verify the generated document is marked as draft requiring human review."""
        result = fill_event_pdf_form("evt-dubhacks-2026")
        self.assertTrue(result["is_draft"])
        self.assertTrue(result["requires_organizer_review"])
        self.assertEqual(result["status"], "draft_ready")
        self.assertIn("DRAFT ONLY", result["hitl_safety"])
        self.assertIn("Manual review required", result["hitl_safety"])

    def test_05_contract_never_represented_as_signed_or_finalized(self):
        """Verify contracts are never marked signed, submitted, or legally finalized."""
        result = fill_event_pdf_form("evt-dubhacks-2026")
        self.assertFalse(result["is_signed"])
        self.assertFalse(result["is_submitted"])
        self.assertFalse(result["is_finalized"])
        self.assertEqual(result["legal_status"], "draft_unexecuted")

        # Signature fields must NEVER be auto-filled
        for sig_field in SIGNATORY_FIELDS:
            self.assertNotIn(sig_field, result["mapped_facts"])
            self.assertTrue(any(u["field"] == sig_field for u in result["unresolved_missing_fields"]))

        # Verify on-disk PDF has empty signature fields
        out_path = OUTPUT_DIR / result["output_file"]
        reader = pypdf.PdfReader(str(out_path))
        fields = reader.get_fields() or {}
        for sig_field in SIGNATORY_FIELDS:
            val = fields.get(sig_field, {}).get("/V", "")
            self.assertEqual(val, "", f"Signature field '{sig_field}' was filled: {val}")

    def test_06_repeated_generation_prevents_silent_overwrite_versioning(self):
        """Verify repeated generation without overwrite=True generates versioned drafts."""
        res1 = fill_event_pdf_form("evt-dubhacks-2026", overwrite=False)
        res2 = fill_event_pdf_form("evt-dubhacks-2026", overwrite=False)

        self.assertNotEqual(res1["output_file"], res2["output_file"])
        self.assertGreater(res2["version"], res1["version"])
        self.assertTrue((OUTPUT_DIR / res1["output_file"]).exists())
        self.assertTrue((OUTPUT_DIR / res2["output_file"]).exists())

    def test_07_explicit_overwrite_mode(self):
        """Verify explicit overwrite=True reuses the base filename."""
        res = fill_event_pdf_form("evt-dubhacks-2026", overwrite=True)
        self.assertEqual(res["version"], 1)
        self.assertIn("_draft.pdf", res["output_file"])
        self.assertNotIn("_v2.pdf", res["output_file"])

    def test_08_path_traversal_prevention_template_and_output(self):
        """Verify path traversal attempts on template path and output filename fail safely."""
        traversal_attempts = [
            "../../etc/passwd",
            "../templates/secret.pdf",
            "/tmp/../../etc/shadow",
            "template\x00.pdf",
        ]
        for bad_path in traversal_attempts:
            with self.assertRaises((ValueError, FileNotFoundError)):
                validate_template_path(bad_path)

        output_traversal_attempts = [
            "../../../malicious.pdf",
            "subfolder/malicious.pdf",
            "malicious.txt",
            "/absolute/malicious.pdf",
            "bad\x00.pdf",
        ]
        for bad_out in output_traversal_attempts:
            with self.assertRaises(ValueError):
                validate_output_filename(bad_out)

    def test_09_unsupported_pdf_fails_safely(self):
        """Verify unsupported flat PDFs (without AcroForm fields) fail safely."""
        with tempfile.TemporaryDirectory() as tmpdir:
            flat_pdf = Path(tmpdir) / "flat_scanned.pdf"
            c = canvas.Canvas(str(flat_pdf), pagesize=letter)
            c.drawString(100, 700, "Flat scanned document with no interactive fields.")
            c.save()

            # Inspecting flat PDF raises ValueError
            with self.assertRaises(ValueError) as ctx:
                inspect_template_fields(flat_pdf)
            self.assertIn("Unsupported PDF format", str(ctx.exception))
            self.assertIn("does not contain fillable AcroForm fields", str(ctx.exception))

            # Filling flat PDF raises ValueError
            with self.assertRaises(ValueError) as ctx2:
                fill_event_pdf_form("evt-dubhacks-2026", template_name_or_path=flat_pdf)
            self.assertIn("Unsupported PDF format", str(ctx2.exception))

    def test_10_corrupted_and_non_pdf_fails_safely(self):
        """Verify corrupt and non-PDF files fail safely."""
        with tempfile.TemporaryDirectory() as tmpdir:
            txt_file = Path(tmpdir) / "not_a_pdf.txt"
            txt_file.write_text("Hello world")

            corrupt_file = Path(tmpdir) / "corrupt.pdf"
            corrupt_file.write_bytes(b"Not valid PDF header bytes at all")

            with self.assertRaises(ValueError):
                inspect_template_fields(txt_file)

            with self.assertRaises(ValueError):
                inspect_template_fields(corrupt_file)

            with self.assertRaises(FileNotFoundError):
                inspect_template_fields(Path(tmpdir) / "nonexistent.pdf")

            with self.assertRaises(ValueError):
                fill_event_pdf_form("evt-non-existent-9999")

    def test_11_persistent_document_and_audit_logging(self):
        """Verify document metadata and audit logs are recorded persistently in SQLite."""
        res = fill_event_pdf_form("evt-dubhacks-2026", actor_id="test_organizer_42")
        doc_id = res["document_id"]

        # Check SQLite pdf_documents record
        saved_doc = get_pdf_document_by_id(doc_id, event_id="evt-dubhacks-2026")
        self.assertIsNotNone(saved_doc)
        self.assertEqual(saved_doc["id"], doc_id)
        self.assertEqual(saved_doc["status"], "draft_ready")
        self.assertIn("event_name", saved_doc["mapped_fields"])
        self.assertIn("budget_code", saved_doc["unresolved_fields"])

        # Check SQLite audit_logs record
        logs = get_audit_logs(event_id="evt-dubhacks-2026", limit=20)
        matching_log = next((l for l in logs if l.get("action") == "pdf_draft_generated" and l.get("details", {}).get("document_id") == doc_id), None)
        self.assertIsNotNone(matching_log, "Audit log for PDF generation was not found")
        self.assertEqual(matching_log["actor_id"], "test_organizer_42")
        self.assertEqual(matching_log["details"]["legal_status"], "draft_unexecuted")

    def test_12_event_isolation(self):
        """Verify generated files and queries are isolated to the specific event."""
        conn = get_connection()
        c = conn.cursor()
        c.execute("""
            INSERT OR REPLACE INTO events (id, title, date, location, attendee_count, budget, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, ("evt-synthetic-isolation", "Synthetic Isolated Conference", "2026-11-20", "Seattle Center", 150, 5000.0, "planning"))
        conn.commit()
        conn.close()

        res = fill_event_pdf_form("evt-synthetic-isolation")
        self.assertIn("synthetic-isolation", res["output_file"])
        self.assertEqual(res["mapped_facts"]["event_name"], "Synthetic Isolated Conference")
        self.assertEqual(res["mapped_facts"]["expected_attendance"], "150")

        # Verify get_pdf_documents respects event isolation
        iso_docs = get_pdf_documents("evt-synthetic-isolation")
        self.assertTrue(all(d["event_id"] == "evt-synthetic-isolation" for d in iso_docs))
        self.assertTrue(any(d["id"] == res["document_id"] for d in iso_docs))

        dub_docs = get_pdf_documents("evt-dubhacks-2026")
        self.assertFalse(any(d["id"] == res["document_id"] for d in dub_docs))

    def test_13_api_endpoints_integration(self):
        """Verify FastAPI REST endpoints for PDF inspect, fill, documents, and download."""
        # 1. Inspect endpoint
        insp_resp = self.client.get("/api/pdf/inspect")
        self.assertEqual(insp_resp.status_code, 200)
        self.assertGreaterEqual(insp_resp.json()["total_fields"], 14)

        # 2. Fill endpoint
        fill_resp = self.client.post("/api/pdf/fill?event_id=evt-dubhacks-2026")
        self.assertEqual(fill_resp.status_code, 200)
        data = fill_resp.json()
        self.assertEqual(data["status"], "draft_ready")
        self.assertTrue(data["is_draft"])
        out_filename = data["output_file"]

        # 3. Documents list endpoint
        docs_resp = self.client.get("/api/pdf/documents?event_id=evt-dubhacks-2026")
        self.assertEqual(docs_resp.status_code, 200)
        self.assertIsInstance(docs_resp.json(), list)

        # 4. Download endpoint valid
        dl_resp = self.client.get(f"/api/pdf/download/{out_filename}")
        self.assertEqual(dl_resp.status_code, 200)
        self.assertEqual(dl_resp.headers["content-type"], "application/pdf")
        self.assertGreater(len(dl_resp.content), 0)

        # 5. Download path traversal blocked
        bad_dl = self.client.get("/api/pdf/download/..%2F..%2Fetc%2Fpasswd")
        self.assertEqual(bad_dl.status_code, 400)

        # 6. Download non-pdf blocked
        non_pdf = self.client.get("/api/pdf/download/secret.txt")
        self.assertEqual(non_pdf.status_code, 400)

        # 7. Download non-existent file returns 404
        not_found_dl = self.client.get("/api/pdf/download/nonexistent_file_99999.pdf")
        self.assertEqual(not_found_dl.status_code, 404)


if __name__ == "__main__":
    unittest.main()
