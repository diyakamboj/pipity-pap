"""Outreach Management & Partner Pipeline Skill.

Attribution: Adapted from ClosedAI's client tools and HITL communication safety patterns.
"""

OUTREACH_MANAGEMENT_GUIDELINES = """
## Outreach Pipeline & Partner Management Protocol
When managing speaker and sponsor outreach:
1. HUMAN-IN-THE-LOOP (HITL) SAFETY:
   - High-risk external actions (email, Slack, Teams) MUST create a pending Action Proposal in the Action Center.
   - Never represent an outreach message as sent until the organizer explicitly approves it.
   - Allow organizers to edit subject and body before dispatching.
2. INBOUND REPLY PARSING:
   - When an email reply is received from a speaker or sponsor, immediately extract:
     a) Confirmation status (confirmed, declined, tentative)
     b) Talk topic or agreed partnership tier
     c) Time slot preferences and availability
     d) Dietary accommodations (e.g. vegan, nut allergy)
   - Store extracted details immediately in persistent speaker/sponsor records.
3. STALLED OUTREACH & CADENCE:
   - Monitor sent proposals: if a candidate has not responded within 3 days, flag them in the follow-up radar.
   - Draft polite, context-aware follow-up messages referencing previous correspondence.
"""
