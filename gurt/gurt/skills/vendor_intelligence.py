"""Vendor Intelligence & Sourcing Skill.

Attribution: Adapted from ClosedAI's compliance and API integration specialist patterns.
"""

VENDOR_INTELLIGENCE_GUIDELINES = """
## Vendor Intelligence & Procurement Protocol
When discovering vendor needs, comparing quotes, or verifying compliance:
1. REQUIREMENTS DISCOVERY:
   - Always evaluate headcount vs dietary bounds (vegan, gluten-free, halal, nut allergies).
   - Flag missing logistical assumptions (delivery cutoff times, setup buffers, dietary labeling).
2. QUOTE COMPARISON & TRADE-OFFS:
   - Always calculate price-per-head = (quote_amount / max(attendee_count, 1)).
   - Compare total quote against event budget bounds.
   - Highlight value trade-offs clearly: do not just pick the cheapest; assess allergen certifications, dietary variety, and past delivery track record.
3. COMPLIANCE & RISK:
   - For food & beverage vendors, verify health permits (e.g. King County Food Safety Inspection).
   - Ensure Certificate of Insurance (COI) covers minimum venue requirements ($1M general liability).
   - Note non-compliant or pending permit suppliers with clear warning indicators.
"""
