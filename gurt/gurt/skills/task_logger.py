"""Task & Incident Logger Skill.

Attribution: Adapted from the portable prompt guidance in ClosedAI's
`.agents/skills/github-issue-creator/SKILL.md`.
Licensed / authorized for skill concept reuse.
"""

TASK_LOGGER_GUIDELINES = """
## Operations Task & Incident Logging Protocol
When organizers report chaotic feedback, floor issues, or new requirements:
1. Extract the core deliverable or operational blocker.
2. Assign a clear Owner, Category (Outreach, Vendors, Logistics, Tech), and Deadline.
3. Categorize urgency: P0 (event blocking), P1 (time sensitive), P2 (standard prep).
4. Explicitly track dependencies (e.g. badge printing depends on confirmed attendee count).
5. Never leave tasks as vague thoughts; record concrete actionable steps.
"""
