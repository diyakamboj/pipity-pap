"""Focused Automated Tests for Gurt Vendor Comparison & Proposal Workflow.

Covers:
1. Save and edit catering requirements for a specific event (headcount, dietary needs, service window, location, budget, unknowns).
2. Add and edit two organizer-supplied vendor quotes (quantities, unit prices, taxes, delivery fees, dietary coverage, source, quote status).
3. Calculate accurate total costs and per-attendee costs from saved data (never treat unknown fees as zero; never assume quote stays valid after headcount changes).
4. Compare quotes against event's current requirements and budget, explaining missing information and assumptions.
5. Allow organizer to select a preferred vendor proposal without treating selection as booking, confirmation, or purchase.
6. Persist all changes in SQLite database with reload verification.
7. Strict event boundary isolation (cross-event queries and mutations blocked).
8. FastAPI REST API endpoints (/api/vendor-requirements, /api/vendor-requirements/catering, /api/vendors, /api/vendors/compare, /api/vendors/{id}/select).
"""

from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path
from typing import Any

# Add gurt root to sys.path
GURT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(GURT_ROOT))

from gurt.db import (
    get_connection,
    init_db,
    get_vendor_by_id,
    update_vendor,
    get_vendor_requirements,
    get_vendor_requirement_by_id,
    update_vendor_requirement,
    save_vendor_requirement,
    record_vendor_selection,
    get_audit_logs
)
from gurt.tools.event_tools import (
    check_dietary_coverage,
    tool_calculate_quote_cost,
    tool_add_detailed_vendor_quote,
    tool_update_vendor_quote,
    tool_add_vendor_quote,
    tool_save_catering_requirement,
    tool_update_vendor_requirement,
    tool_compare_vendor_quotes,
    tool_select_vendor_proposal,
    tool_lookup_vendors
)
from gurt.api.server import app
from fastapi.testclient import TestClient


class TestVendorWorkflow(unittest.TestCase):
    """Test suite for the persistent backend vendor comparison and selection workflow."""

    @classmethod
    def setUpClass(cls):
        init_db()
        cls.client = TestClient(app)

    def setUp(self):
        """Set up isolated test events."""
        self.test_event_a = "evt-test-vendor-alpha"
        self.test_event_b = "evt-test-vendor-beta"

        # Clean up any leftover test data for these event IDs
        conn = get_connection()
        c = conn.cursor()
        c.execute("DELETE FROM vendors WHERE event_id IN (?, ?)", (self.test_event_a, self.test_event_b))
        c.execute("DELETE FROM vendor_requirements WHERE event_id IN (?, ?)", (self.test_event_a, self.test_event_b))
        c.execute("DELETE FROM audit_logs WHERE event_id IN (?, ?)", (self.test_event_a, self.test_event_b))
        conn.commit()
        conn.close()

    def tearDown(self):
        """Clean up test events."""
        conn = get_connection()
        c = conn.cursor()
        c.execute("DELETE FROM vendors WHERE event_id IN (?, ?)", (self.test_event_a, self.test_event_b))
        c.execute("DELETE FROM vendor_requirements WHERE event_id IN (?, ?)", (self.test_event_a, self.test_event_b))
        c.execute("DELETE FROM audit_logs WHERE event_id IN (?, ?)", (self.test_event_a, self.test_event_b))
        conn.commit()
        conn.close()

    def test_01_save_and_edit_catering_requirements(self):
        """Save and edit catering requirements with headcount, dietary needs, window, and unknowns."""
        # 1. Save initial catering requirement
        saved = tool_save_catering_requirement(
            event_id=self.test_event_a,
            headcount=80,
            budget=1250.0,
            dietary_needs="15 vegan, 10 gluten-free, 5 halal, 100% nut-free",
            service_window="11:30 AM - 1:00 PM",
            location="UW HUB Ballroom Foyer",
            unknowns=["Final dietary tally cutoff date", "Loading dock parking permit"],
            specification="Custom organic boxed lunch buffet for attendees"
        )

        req_id = saved["requirement_id"]
        self.assertEqual(saved["headcount"], 80)
        self.assertEqual(saved["budget_allocated"], 1250.0)
        self.assertIn("Final dietary tally cutoff date", saved["unknowns"])

        # Verify persisted in database
        loaded = get_vendor_requirement_by_id(req_id, event_id=self.test_event_a)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["headcount"], 80)
        self.assertEqual(loaded["budget_allocated"], 1250.0)
        self.assertEqual(loaded["dietary_needs"], "15 vegan, 10 gluten-free, 5 halal, 100% nut-free")
        self.assertEqual(loaded["service_window"], "11:30 AM - 1:00 PM")
        self.assertEqual(loaded["location"], "UW HUB Ballroom Foyer")

        # 2. Edit catering requirement (increase budget to 1400.0, add unknown, change headcount to 90)
        updated = tool_update_vendor_requirement(
            req_id=req_id,
            event_id=self.test_event_a,
            headcount=90,
            budget_allocated=1400.0,
            unknowns=["Final dietary tally cutoff date", "Loading dock parking permit", "Trash bin rental fee"],
            dietary_needs="18 vegan, 12 gluten-free, 6 halal, 100% nut-free"
        )

        self.assertEqual(updated["headcount"], 90)
        self.assertEqual(updated["budget_allocated"], 1400.0)
        self.assertIn("Trash bin rental fee", updated["unknowns"])
        self.assertEqual(updated["dietary_needs"], "18 vegan, 12 gluten-free, 6 halal, 100% nut-free")

        # Verify DB reload
        reloaded = get_vendor_requirement_by_id(req_id, event_id=self.test_event_a)
        self.assertEqual(reloaded["headcount"], 90)
        self.assertEqual(reloaded["budget_allocated"], 1400.0)
        self.assertIn("Trash bin rental fee", reloaded["unknowns"])

    def test_02_add_and_edit_two_vendor_quotes(self):
        """Add and edit two organizer-supplied vendor quotes with itemized pricing, fees, and dietary coverage."""
        # 1. Add Quote 1: Olympic Catering Co
        q1 = tool_add_detailed_vendor_quote(
            company_name="Olympic Catering Co",
            category="Catering",
            quantities=80,
            unit_price=14.0,
            tax=112.0,
            tax_is_unknown=False,
            delivery_fee=50.0,
            delivery_fee_is_unknown=False,
            dietary_coverage=["vegan", "gluten-free", "nut-free"],
            source="Email quote from sales manager David",
            quote_status="quoted",
            event_id=self.test_event_a
        )
        self.assertEqual(q1["status"], "added")
        vnd_1_id = q1["vendor_id"]

        # Expected: subtotal = 80 * 14 = 1120.0, tax = 112.0, delivery = 50.0 -> total = 1282.0
        self.assertEqual(q1["quote_amount"], 1282.0)
        self.assertEqual(q1["price_per_head"], round(1282.0 / 80, 2))

        # 2. Edit Quote 1: negotiate unit price to 13.50 and delivery fee to 40.0
        edited_q1 = tool_update_vendor_quote(
            vendor_id=vnd_1_id,
            event_id=self.test_event_a,
            unit_price=13.50,
            delivery_fee=40.0,
            tax=108.0
        )
        self.assertEqual(edited_q1["status"], "updated")
        # New total: 80 * 13.50 = 1080 + 108 (tax) + 40 (deliv) = 1228.0
        self.assertEqual(edited_q1["quote_amount"], 1228.0)
        self.assertEqual(edited_q1["price_per_head"], round(1228.0 / 80, 2))

        # 3. Add Quote 2: Cascade Artisan Deli (has unknown tax)
        q2 = tool_add_detailed_vendor_quote(
            company_name="Cascade Artisan Deli",
            category="Catering",
            quantities=80,
            unit_price=15.0,
            tax=None,
            tax_is_unknown=True,
            delivery_fee=45.0,
            delivery_fee_is_unknown=False,
            dietary_coverage=["vegan", "nut-free", "halal"],
            source="Website menu pricing sheet",
            quote_status="quoted",
            event_id=self.test_event_a
        )
        self.assertEqual(q2["status"], "added")
        vnd_2_id = q2["vendor_id"]

        # Expected: subtotal = 1200.0, delivery = 45.0, tax is UNKNOWN (not treated as 0)
        # Base known cost = 1245.0, is_total_definite = False, has_unknown_fees = True
        self.assertEqual(q2["quote_amount"], 1245.0)
        self.assertTrue(q2["quote_data"]["has_unknown_fees"])
        self.assertIn("tax", q2["quote_data"]["unknown_fees"])

        # Verify both persisted in DB with rich quote_data
        v1_db = get_vendor_by_id(vnd_1_id, event_id=self.test_event_a)
        v2_db = get_vendor_by_id(vnd_2_id, event_id=self.test_event_a)
        self.assertIsNotNone(v1_db)
        self.assertIsNotNone(v2_db)
        self.assertEqual(v1_db["quote_amount"], 1228.0)
        self.assertEqual(v2_db["quote_amount"], 1245.0)
        self.assertTrue(v2_db["quote_data"]["has_unknown_fees"])

    def test_03_accurate_cost_calculation_and_unknown_fees(self):
        """Accurate cost math: Never treat unknown fees as zero."""
        # Case A: Fully known quote
        calc_known = tool_calculate_quote_cost(
            quantities=80,
            unit_price=12.50,
            tax=100.0,
            tax_is_unknown=False,
            delivery_fee=35.0,
            delivery_fee_is_unknown=False,
            other_fees=15.0
        )
        # subtotal: 1000.0, known fees: 150.0, base_cost: 1150.0, per_attendee: 14.38
        self.assertEqual(calc_known["subtotal"], 1000.0)
        self.assertEqual(calc_known["base_cost"], 1150.0)
        self.assertEqual(calc_known["per_attendee_cost"], 14.38)
        self.assertTrue(calc_known["is_total_definite"])
        self.assertFalse(calc_known["has_unknown_fees"])
        self.assertEqual(calc_known["unknown_fees"], [])
        self.assertIsNone(calc_known["unknown_fees_warning"])

        # Case B: Unknown tax and delivery fee
        calc_unknown = tool_calculate_quote_cost(
            quantities=80,
            unit_price=12.50,
            tax=None,
            tax_is_unknown=True,
            delivery_fee=None,
            delivery_fee_is_unknown=True,
            other_fees=0.0
        )
        # Base subtotal: 1000.0, but total is NOT definite
        self.assertEqual(calc_unknown["subtotal"], 1000.0)
        self.assertEqual(calc_unknown["base_cost"], 1000.0)
        self.assertFalse(calc_unknown["is_total_definite"])
        self.assertTrue(calc_unknown["has_unknown_fees"])
        self.assertIn("tax", calc_unknown["unknown_fees"])
        self.assertIn("delivery_fee", calc_unknown["unknown_fees"])
        self.assertIsNotNone(calc_unknown["unknown_fees_warning"])
        self.assertTrue(calc_unknown["per_attendee_is_provisional"])
        # Warning explicitly states not to treat missing fees as 0
        self.assertIn("NEVER be treated as $0.00", calc_unknown["unknown_fees_warning"])

    def test_04_attendance_headcount_changes_invalidate_quotes(self):
        """Headcount change rule: Never assume a quote stays valid after headcount changes."""
        # Quote given for 50 attendees
        calc_mismatch = tool_calculate_quote_cost(
            quantities=50,
            unit_price=16.0,
            tax=80.0,
            delivery_fee=40.0,
            quoted_headcount=50,
            target_headcount=80
        )
        self.assertTrue(calc_mismatch["headcount_mismatch"])
        self.assertFalse(calc_mismatch["is_valid_for_headcount"])
        self.assertIsNotNone(calc_mismatch["headcount_warning"])
        self.assertIn("Quote cannot be assumed valid after headcount change", calc_mismatch["headcount_warning"])

        # Matching headcount
        calc_match = tool_calculate_quote_cost(
            quantities=80,
            unit_price=16.0,
            tax=128.0,
            delivery_fee=40.0,
            quoted_headcount=80,
            target_headcount=80
        )
        self.assertFalse(calc_match["headcount_mismatch"])
        self.assertTrue(calc_match["is_valid_for_headcount"])
        self.assertIsNone(calc_match["headcount_warning"])

    def test_05_compare_vendor_quotes_against_budget_and_requirements(self):
        """Compare quotes against current requirements and budget, explaining missing info and assumptions."""
        # 1. Establish catering requirement: 80 attendees, budget $1300.0, dietary "vegan, gluten-free, halal, nut-free"
        tool_save_catering_requirement(
            event_id=self.test_event_a,
            headcount=80,
            budget=1300.0,
            dietary_needs="15 vegan, 10 gluten-free, 5 halal, strict nut-free",
            service_window="11:30 AM - 1:00 PM",
            location="UW HUB Ballroom"
        )

        # 2. Vendor 1: Olympic Catering Co (definite total $1228.0, covers vegan/GF/nut-free, missing halal)
        tool_add_detailed_vendor_quote(
            company_name="Olympic Catering Co",
            category="Catering",
            quantities=80,
            unit_price=13.50,
            tax=108.0,
            delivery_fee=40.0,
            dietary_coverage=["vegan", "gluten-free", "nut-free"],
            event_id=self.test_event_a
        )

        # 3. Vendor 2: Cascade Artisan Deli (base $1245.0, unknown tax, covers vegan/halal/nut-free, missing GF)
        tool_add_detailed_vendor_quote(
            company_name="Cascade Artisan Deli",
            category="Catering",
            quantities=80,
            unit_price=15.0,
            tax=None,
            tax_is_unknown=True,
            delivery_fee=45.0,
            dietary_coverage=["vegan", "halal", "nut-free"],
            event_id=self.test_event_a
        )

        # 4. Vendor 3: Stale Scale Quote (priced for only 40 attendees, mismatch!)
        tool_add_detailed_vendor_quote(
            company_name="QuickBites Boxed Meals",
            category="Catering",
            quantities=40,
            unit_price=12.0,
            tax=48.0,
            delivery_fee=30.0,
            quoted_headcount=40,
            dietary_coverage=["vegan", "gluten-free", "halal", "nut-free"],
            event_id=self.test_event_a
        )

        # 5. Run comparison
        res = tool_compare_vendor_quotes(category="Catering", event_id=self.test_event_a)
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["quotes_evaluated"], 3)
        self.assertEqual(res["attendee_count"], 80)
        self.assertEqual(res["event_budget"], 1300.0)

        # Verify matrix items
        matrix = {c["company_name"]: c for c in res["comparison_matrix"]}
        self.assertIn("Olympic Catering Co", matrix)
        self.assertIn("Cascade Artisan Deli", matrix)
        self.assertIn("QuickBites Boxed Meals", matrix)

        # Olympic Catering check
        ol = matrix["Olympic Catering Co"]
        self.assertTrue(ol["is_within_budget"])
        self.assertTrue(ol["is_valid_for_headcount"])
        self.assertTrue(ol["is_total_definite"])
        self.assertIn("halal", ol["uncovered_dietary_needs"])

        # Cascade Deli check: unknown fee flagged
        cas = matrix["Cascade Artisan Deli"]
        self.assertTrue(cas["has_unknown_fees"])
        self.assertIn("tax", cas["unknown_fees"])
        self.assertIn("gluten-free", cas["uncovered_dietary_needs"])

        # QuickBites check: headcount mismatch flagged
        qb = matrix["QuickBites Boxed Meals"]
        self.assertTrue(qb["headcount_mismatch"])
        self.assertFalse(qb["is_valid_for_headcount"])
        self.assertIn("Headcount mismatch", qb["headcount_warning"])

        # Recommendation should choose Olympic Catering Co over QuickBites (mismatched) and Cascade (unknown tax)
        self.assertEqual(res["recommended_vendor"], "Olympic Catering Co")
        self.assertIn("margin", res["recommendation_reason"])

    def test_06_select_preferred_vendor_proposal(self):
        """Select preferred vendor proposal without booking, purchasing, or contract commitment."""
        # Create quote
        q = tool_add_detailed_vendor_quote(
            company_name="Olympic Catering Co",
            category="Catering",
            quantities=80,
            unit_price=13.50,
            tax=108.0,
            delivery_fee=40.0,
            event_id=self.test_event_a
        )
        vendor_id = q["vendor_id"]

        # Select preferred proposal
        sel = tool_select_vendor_proposal(
            vendor_id=vendor_id,
            event_id=self.test_event_a,
            selection_notes="Preferred vendor selected based on price and dietary options. Final contract to be signed manually.",
            actor_id="Sam Operations"
        )

        self.assertEqual(sel["status"], "selected")
        self.assertEqual(sel["quote_status"], "selected")
        self.assertTrue(sel["is_preferred"])
        # CRITICAL HITL SAFETY CHECKS:
        self.assertFalse(sel["is_booked"])
        self.assertFalse(sel["is_confirmed"])
        self.assertFalse(sel["is_actual_purchase"])
        self.assertTrue(sel["requires_manual_booking"])
        self.assertIn("DOES NOT book, confirm, purchase", sel["booking_disclaimer"])
        self.assertTrue(len(sel["next_steps"]) >= 3)

        # Check DB vendor status
        v_db = get_vendor_by_id(vendor_id, event_id=self.test_event_a)
        self.assertEqual(v_db["status"], "selected")
        self.assertEqual(v_db["selection_notes"], "Preferred vendor selected based on price and dietary options. Final contract to be signed manually.")

        # Check audit log
        logs = get_audit_logs(self.test_event_a)
        sel_logs = [l for l in logs if l["action"] == "select_preferred_vendor"]
        self.assertEqual(len(sel_logs), 1)
        log_entry = sel_logs[0]
        self.assertEqual(log_entry["target_id"], vendor_id)
        self.assertEqual(log_entry["actor_id"], "Sam Operations")
        details = json.loads(log_entry["details_json"])
        self.assertFalse(details["is_booked"])
        self.assertFalse(details["is_purchase"])

    def test_07_persistence_across_connection_reload(self):
        """All vendor requirements, quotes, and selections survive database connection reload."""
        # 1. Save requirement
        req = tool_save_catering_requirement(
            event_id=self.test_event_a,
            headcount=85,
            budget=1500.0,
            dietary_needs="20 vegan, 10 GF",
            service_window="12:00 PM - 1:30 PM",
            location="Room 214"
        )
        req_id = req["requirement_id"]

        # 2. Add and select vendor
        v = tool_add_detailed_vendor_quote(
            company_name="Reload Verification Catering",
            category="Catering",
            quantities=85,
            unit_price=14.0,
            tax=119.0,
            delivery_fee=50.0,
            event_id=self.test_event_a
        )
        v_id = v["vendor_id"]
        tool_select_vendor_proposal(v_id, event_id=self.test_event_a, selection_notes="Reload test")

        # 3. Simulate fresh reload via brand new connection
        fresh_conn = get_connection()
        fresh_c = fresh_conn.cursor()
        fresh_c.execute("SELECT * FROM vendor_requirements WHERE id = ?", (req_id,))
        fresh_req_row = dict(fresh_c.fetchone())
        fresh_c.execute("SELECT * FROM vendors WHERE id = ?", (v_id,))
        fresh_v_row = dict(fresh_c.fetchone())
        fresh_conn.close()

        self.assertEqual(fresh_req_row["headcount"], 85)
        self.assertEqual(fresh_req_row["budget_allocated"], 1500.0)
        self.assertEqual(fresh_v_row["status"], "selected")
        self.assertEqual(fresh_v_row["company_name"], "Reload Verification Catering")
        quote_data = json.loads(fresh_v_row["quote_data"])
        self.assertEqual(quote_data["unit_price"], 14.0)
        self.assertEqual(quote_data["tax"], 119.0)

    def test_08_event_boundary_isolation(self):
        """Vendor requirements and quotes must be strictly isolated between events."""
        # Create quote in Event A
        v_a = tool_add_detailed_vendor_quote(
            company_name="Event A Only Caterer",
            category="Catering",
            quantities=50,
            unit_price=10.0,
            tax=50.0,
            event_id=self.test_event_a
        )
        v_a_id = v_a["vendor_id"]

        # Create quote in Event B
        v_b = tool_add_detailed_vendor_quote(
            company_name="Event B Only Caterer",
            category="Catering",
            quantities=50,
            unit_price=12.0,
            tax=60.0,
            event_id=self.test_event_b
        )
        v_b_id = v_b["vendor_id"]

        # Comparison in Event A must NOT see Event B vendor
        comp_a = tool_compare_vendor_quotes(category="Catering", event_id=self.test_event_a)
        comp_a_names = [c["company_name"] for c in comp_a["comparison_matrix"]]
        self.assertIn("Event A Only Caterer", comp_a_names)
        self.assertNotIn("Event B Only Caterer", comp_a_names)

        # Cross-event selection must fail
        with self.assertRaises(ValueError):
            tool_select_vendor_proposal(v_a_id, event_id=self.test_event_b)

        # Cross-event update must fail
        with self.assertRaises(ValueError):
            tool_update_vendor_quote(v_a_id, event_id=self.test_event_b, unit_price=99.0)

    def test_09_fastapi_rest_endpoints(self):
        """FastAPI REST API routes work end-to-end for requirements, quotes, comparison, and selection."""
        # 1. POST /api/vendor-requirements/catering
        r_req = self.client.post("/api/vendor-requirements/catering", json={
            "event_id": self.test_event_a,
            "headcount": 80,
            "budget": 1200.0,
            "dietary_needs": "15 vegan, 10 GF",
            "service_window": "11:30 AM - 1:00 PM",
            "location": "HUB Ballroom",
            "unknowns": ["Cutoff date", "Linen rental"]
        })
        self.assertEqual(r_req.status_code, 200)
        req_data = r_req.json()
        req_id = req_data["requirement_id"]
        self.assertEqual(req_data["headcount"], 80)

        # 2. PUT /api/vendor-requirements/{req_id}
        r_put_req = self.client.put(f"/api/vendor-requirements/{req_id}", json={
            "event_id": self.test_event_a,
            "budget_allocated": 1350.0
        })
        self.assertEqual(r_put_req.status_code, 200)
        self.assertEqual(r_put_req.json()["budget_allocated"], 1350.0)

        # 3. GET /api/vendor-requirements/{req_id}
        r_get_req = self.client.get(f"/api/vendor-requirements/{req_id}?event_id={self.test_event_a}")
        self.assertEqual(r_get_req.status_code, 200)
        self.assertEqual(r_get_req.json()["budget_allocated"], 1350.0)

        # 4. POST /api/vendors
        r_vnd = self.client.post("/api/vendors", json={
            "company_name": "API Test Bistro",
            "category": "Catering",
            "quantities": 80,
            "unit_price": 13.0,
            "tax": 104.0,
            "delivery_fee": 35.0,
            "dietary_coverage": ["vegan", "gluten-free"],
            "source": "FastAPI client quote",
            "event_id": self.test_event_a
        })
        self.assertEqual(r_vnd.status_code, 200)
        vnd_data = r_vnd.json()
        vendor_id = vnd_data["vendor_id"]
        self.assertEqual(vnd_data["quote_amount"], 80 * 13.0 + 104.0 + 35.0)

        # 5. PATCH /api/vendors/{vendor_id}
        r_patch_vnd = self.client.patch(f"/api/vendors/{vendor_id}", json={
            "event_id": self.test_event_a,
            "unit_price": 12.50
        })
        self.assertEqual(r_patch_vnd.status_code, 200)
        self.assertEqual(r_patch_vnd.json()["quote_data"]["unit_price"], 12.50)

        # 6. GET /api/vendors/compare
        r_comp = self.client.get(f"/api/vendors/compare?category=Catering&event_id={self.test_event_a}")
        self.assertEqual(r_comp.status_code, 200)
        comp_data = r_comp.json()
        self.assertEqual(comp_data["status"], "success")
        self.assertTrue(len(comp_data["comparison_matrix"]) >= 1)

        # 7. POST /api/vendors/{vendor_id}/select
        r_sel = self.client.post(f"/api/vendors/{vendor_id}/select", json={
            "event_id": self.test_event_a,
            "selection_notes": "Selected via REST API",
            "actor_id": "API Organizer"
        })
        self.assertEqual(r_sel.status_code, 200)
        sel_data = r_sel.json()
        self.assertEqual(sel_data["status"], "selected")
        self.assertFalse(sel_data["is_booked"])
        self.assertFalse(sel_data["is_purchase"])
        # 8. GET /api/vendor-requirements/catering
        r_get_cater = self.client.get(f"/api/vendor-requirements/catering?event_id={self.test_event_a}")
        self.assertEqual(r_get_cater.status_code, 200)
        self.assertEqual(r_get_cater.json()["id"], req_id)

    def test_10_fastapi_rest_edge_cases_and_security(self):
        """Test REST API for missing IDs, cross-event isolation, invalid input (422), route ordering, and unknown fee labeling."""
        # 1. Missing IDs return 404
        r_missing_v = self.client.get(f"/api/vendors/vnd-does-not-exist?event_id={self.test_event_a}")
        self.assertEqual(r_missing_v.status_code, 404)

        r_missing_v_patch = self.client.patch("/api/vendors/vnd-does-not-exist", json={
            "event_id": self.test_event_a,
            "unit_price": 20.0
        })
        self.assertEqual(r_missing_v_patch.status_code, 404)

        r_missing_v_sel = self.client.post("/api/vendors/vnd-does-not-exist/select", json={
            "event_id": self.test_event_a,
            "selection_notes": "Attempting to select nonexistent vendor"
        })
        self.assertEqual(r_missing_v_sel.status_code, 404)

        r_missing_req = self.client.get(f"/api/vendor-requirements/req-does-not-exist?event_id={self.test_event_a}")
        self.assertEqual(r_missing_req.status_code, 404)

        r_missing_req_put = self.client.put("/api/vendor-requirements/req-does-not-exist", json={
            "event_id": self.test_event_a,
            "budget_allocated": 999.0
        })
        self.assertEqual(r_missing_req_put.status_code, 404)

        r_missing_cater = self.client.get("/api/vendor-requirements/catering?event_id=evt-empty-test")
        self.assertEqual(r_missing_cater.status_code, 404)

        # 2. Cross-event access via REST is strictly blocked (returns 404)
        # Create vendor and requirement in Event A
        v_res = self.client.post("/api/vendors", json={
            "company_name": "Event A Caterer",
            "category": "Catering",
            "quantities": 80,
            "unit_price": 15.0,
            "tax": 120.0,
            "event_id": self.test_event_a
        })
        self.assertEqual(v_res.status_code, 200)
        v_a_id = v_res.json()["vendor_id"]

        req_res = self.client.post("/api/vendor-requirements/catering", json={
            "event_id": self.test_event_a,
            "headcount": 80,
            "budget": 2000.0,
            "dietary_needs": "vegan"
        })
        self.assertEqual(req_res.status_code, 200)
        req_a_id = req_res.json()["requirement_id"]

        # Attempt to access Event A records while specifying Event B -> 404
        r_cross_v_get = self.client.get(f"/api/vendors/{v_a_id}?event_id={self.test_event_b}")
        self.assertEqual(r_cross_v_get.status_code, 404)

        r_cross_v_patch = self.client.patch(f"/api/vendors/{v_a_id}", json={
            "event_id": self.test_event_b,
            "unit_price": 99.0
        })
        self.assertEqual(r_cross_v_patch.status_code, 404)

        r_cross_v_sel = self.client.post(f"/api/vendors/{v_a_id}/select", json={
            "event_id": self.test_event_b,
            "selection_notes": "Cross-event attack"
        })
        self.assertEqual(r_cross_v_sel.status_code, 404)

        r_cross_req_get = self.client.get(f"/api/vendor-requirements/{req_a_id}?event_id={self.test_event_b}")
        self.assertEqual(r_cross_req_get.status_code, 404)

        r_cross_req_put = self.client.put(f"/api/vendor-requirements/{req_a_id}", json={
            "event_id": self.test_event_b,
            "budget_allocated": 9999.0
        })
        self.assertEqual(r_cross_req_put.status_code, 404)

        # 3. Route ordering: static routes are never shadowed by parameterized patterns
        # /api/vendors/compare is NOT shadowed by /api/vendors/{vendor_id}
        r_comp = self.client.get(f"/api/vendors/compare?category=Catering&event_id={self.test_event_a}")
        self.assertEqual(r_comp.status_code, 200)
        self.assertEqual(r_comp.json()["status"], "success")

        # /api/vendor-requirements/catering is NOT shadowed by /api/vendor-requirements/{req_id}
        r_cater = self.client.get(f"/api/vendor-requirements/catering?event_id={self.test_event_a}")
        self.assertEqual(r_cater.status_code, 200)
        self.assertEqual(r_cater.json()["id"], req_a_id)

        # 4. Invalid input validation: FastAPI returns 422 Unprocessable Entity
        r_invalid_qty = self.client.post("/api/vendors", json={
            "company_name": "Invalid Qty Vendor",
            "quantities": "not-a-number",
            "unit_price": 15.0
        })
        self.assertEqual(r_invalid_qty.status_code, 422)

        r_invalid_hc = self.client.post("/api/vendor-requirements/catering", json={
            "event_id": self.test_event_a,
            "headcount": "not-an-integer",
            "budget": 1000.0
        })
        self.assertEqual(r_invalid_hc.status_code, 422)

        # 5. Unknown fee representation and estimate labeling in comparison response
        r_unknown_v = self.client.post("/api/vendors", json={
            "company_name": "Unknown Tax Diner",
            "category": "Catering",
            "quantities": 80,
            "unit_price": 10.0,
            "tax": None,
            "tax_is_unknown": True,
            "delivery_fee": None,
            "delivery_fee_is_unknown": True,
            "event_id": self.test_event_a
        })
        self.assertEqual(r_unknown_v.status_code, 200)

        r_comp_unknown = self.client.get(f"/api/vendors/compare?category=Catering&event_id={self.test_event_a}")
        self.assertEqual(r_comp_unknown.status_code, 200)
        comp_res = r_comp_unknown.json()
        matrix = {c["company_name"]: c for c in comp_res["comparison_matrix"]}
        self.assertIn("Unknown Tax Diner", matrix)
        utd = matrix["Unknown Tax Diner"]

        # Verify tax and delivery_fee are null (None in Python), NOT confirmed zero
        self.assertIsNone(utd["tax"])
        self.assertEqual(utd["tax_status"], "unknown")
        self.assertIsNone(utd["delivery_fee"])
        self.assertEqual(utd["delivery_fee_status"], "unknown")

        # Verify clearly labeled as estimate / known-cost subtotal
        self.assertTrue(utd["has_unknown_fees"])
        self.assertFalse(utd["is_total_definite"])
        self.assertTrue(utd["is_estimate"])
        self.assertEqual(utd["cost_classification"], "known_cost_subtotal_estimate")
        self.assertIn("estimate", utd["total_label"].lower())
        self.assertIn("excludes tax, delivery_fee", utd["total_label"])


if __name__ == "__main__":
    unittest.main()
