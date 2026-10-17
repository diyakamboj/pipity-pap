"""Seed data for the Gurt event-ops MCP server (mock backend).

Represents the DubHacks Workshop 2026 demo scenario:
- 80-person AI workshop
- Needs: 1 keynote speaker, 1 sponsor, food for 80, name badges for 80
"""

EVENT = {
    "id": "evt-001",
    "name": "DubHacks Workshop 2026",
    "type": "workshop",
    "date": "2026-11-15",
    "attendees": 80,
    "venue": "Gates Hall 106, UW Seattle",
    "theme": "AI for Social Good",
    "budget": 5000,
    "status": "planning",
}

SPEAKERS = [
    {
        "id": "spk-001",
        "name": "Dr. Alicia Chen",
        "title": "ML Research Scientist",
        "org": "Google DeepMind",
        "topic": "Responsible AI in Healthcare",
        "email": "achen@example.com",
        "past_talks": ["NeurIPS 2025 keynote", "AAAI 2026 panel"],
        "fit_notes": "Directly aligned with AI for Social Good theme. Experienced keynote speaker.",
        "status": "prospecting",
        "availability": "TBD",
    },
    {
        "id": "spk-002",
        "name": "Marcus Rivera",
        "title": "CTO",
        "org": "CivicTech Inc.",
        "topic": "AI for Civic Engagement",
        "email": "mrivera@example.com",
        "past_talks": ["Code for America Summit 2025", "OpenGov Forum 2026"],
        "fit_notes": "Practitioner perspective on civic AI. Strong storytelling track record.",
        "status": "contacted",
        "availability": "Nov 15 available, prefers afternoon",
    },
    {
        "id": "spk-003",
        "name": "Prof. Sara Kim",
        "title": "Associate Professor of CS",
        "org": "University of Washington",
        "topic": "Fairness in Machine Learning",
        "email": "skim@cs.uw.edu",
        "past_talks": ["FAccT 2025", "ICML 2026 tutorial"],
        "fit_notes": "Local UW faculty -- low travel friction. Leading researcher in ML fairness.",
        "status": "confirmed",
        "availability": "Nov 15 confirmed",
    },
]

VENDORS = [
    {
        "id": "vnd-001",
        "category": "food",
        "name": "Campus Catering Co.",
        "contact": "orders@campuscatering.uw.edu",
        "quote": 1200,
        "per_head": 15,
        "confirmed": False,
        "notes": "Quote valid 30 days. Minimum 50 pax. Setup at T-60 min.",
        "dietary": "Vegan, GF options available on request.",
    },
    {
        "id": "vnd-002",
        "category": "badges",
        "name": "PrintFast UW",
        "contact": "print@printfastuw.com",
        "quote": 240,
        "per_unit": 3,
        "confirmed": False,
        "notes": "4-day lead time for 80-badge order. Includes lanyards.",
        "dietary": None,
    },
    {
        "id": "vnd-003",
        "category": "food",
        "name": "Taste of Seoul",
        "contact": "hello@tasteofseoul.com",
        "quote": 960,
        "per_head": 12,
        "confirmed": False,
        "notes": "Available Nov 15. Dietary options: vegan, GF. Serves buffet style.",
        "dietary": "Vegan, GF, Halal.",
    },
]

SPONSORS = [
    {
        "id": "spo-001",
        "name": "Acme AI Labs",
        "tier": "gold",
        "amount": 2000,
        "status": "prospecting",
        "contact": "partnerships@acmeai.com",
        "notes": "Focus on student AI initiatives. Previous DubHacks sponsor.",
    },
    {
        "id": "spo-002",
        "name": "Northwest Tech Fund",
        "tier": "silver",
        "amount": 1000,
        "status": "contacted",
        "contact": "grants@nwtf.org",
        "notes": "Grant-style sponsorship. Requires 30-day lead time for approval.",
    },
]

TASKS = [
    {
        "id": "tsk-001",
        "title": "Confirm speaker availability",
        "owner": "Diya",
        "due": "2026-10-25",
        "status": "open",
        "depends_on": [],
        "notes": "Follow up with spk-001 and spk-002; spk-003 already confirmed.",
    },
    {
        "id": "tsk-002",
        "title": "Send vendor quote requests",
        "owner": "Team",
        "due": "2026-10-22",
        "status": "open",
        "depends_on": [],
        "notes": "Contact Campus Catering Co. and Taste of Seoul; PrintFast already quoted.",
    },
    {
        "id": "tsk-003",
        "title": "Draft sponsor outreach emails",
        "owner": "Gurt",
        "due": "2026-10-20",
        "status": "open",
        "depends_on": [],
        "notes": "Draft for Acme AI Labs and Northwest Tech Fund pending organizer approval.",
    },
    {
        "id": "tsk-004",
        "title": "Book catering vendor",
        "owner": "Team",
        "due": "2026-11-01",
        "status": "open",
        "depends_on": ["tsk-002"],
        "notes": "Compare quotes from vnd-001 and vnd-003 after receiving final numbers.",
    },
    {
        "id": "tsk-005",
        "title": "Order badges and lanyards",
        "owner": "Team",
        "due": "2026-11-11",
        "status": "open",
        "depends_on": [],
        "notes": "4-day lead time -- must place by Nov 11 for Nov 15 delivery.",
    },
    {
        "id": "tsk-006",
        "title": "Confirm final headcount with registration",
        "owner": "Diya",
        "due": "2026-11-10",
        "status": "open",
        "depends_on": [],
        "notes": "Required for catering order and badge count.",
    },
    {
        "id": "tsk-007",
        "title": "Create run-of-show document",
        "owner": "Gurt",
        "due": "2026-11-12",
        "status": "open",
        "depends_on": ["tsk-001", "tsk-004"],
        "notes": "Needs confirmed speaker schedule and catering arrival time.",
    },
]