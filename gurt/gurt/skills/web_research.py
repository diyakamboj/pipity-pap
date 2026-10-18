"""Web Research Skill.

Attribution: Adapted from the portable prompt guidance in ClosedAI's
`web-researcher.md` (HRAgent_Main/tools/preset/subagents/web_researcher.md).
Licensed / authorized for skill concept reuse.
"""

WEB_RESEARCH_GUIDELINES = """
## Web Research Protocol
When searching for speakers, sponsors, or vendors:
1. Formulate specific, query-bounded searches (e.g. "Seattle university AI professors multi-agent systems" or "Seattle catering box lunches under $15").
2. Validate findings across at least 2 indicators (e.g. official bio, recent publications or public talks).
3. Do not invent email addresses or rates; if an exact rate is not published, clearly label it as an estimate.
4. Extract structured facts: Organization, Current Role, Notable Projects/Topics, Public Links.
"""
