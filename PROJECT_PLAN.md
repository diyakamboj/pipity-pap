Event Operations Agent

Complete product and implementation handoff

Version: 1.0
Prepared: October 17, 2026
Audience: The four-person DubHacks team and any developer or LLM joining without prior context
Working name: Event Operations Agent; final branding is undecided
Hackathon window: October 17 at 12:30 p.m. to October 18 at 12:30 p.m. Pacific, assuming a 24-hour window; official submission cutoff must be confirmed
Planning checkpoint: Approximately 1:03 p.m. Pacific on October 17
Implementation status: No application repository, code, deployment, credentials, or working integrations have been inspected or verified for this handoff.

This document records the latest product direction and provides a recommended implementation blueprint. It supersedes the earlier food-focused plan as the working scope reference. Proposed technical details are not claims that the team has already implemented or explicitly selected them.

1. Read this first

We are building an event operations agent for small organizing teams. An organizer describes an event, and the agent helps identify overlooked needs, research people and suppliers, prepare outreach, process replies, handle documents, and coordinate execution.

The product has three focus areas:





Outreach: Speakers, keynote presenters, workshop hosts, sponsors, correspondence, availability, and commitments.



Vendors: Food, lanyards, badges, printing, shirts, equipment, quotes, supplier documents, and applications.



Logistics: Event plans, venue requirements, task ownership, participant instructions, schedules, dependencies, and changes.

The recommended architecture is one orchestrating agent with modular skills and a shared event database. Three product areas do not require three autonomous agents. Developers can build separate skill modules in parallel while the application runtime uses one agent.

The initial target is one complete skill per area, connected through one workspace. Plan up to three skills per area, but add second and third skills only after the connected workflow works. Permissions, approvals, spending controls, and activity history are shared infrastructure.

The differentiation hypothesis combines useful execution skills with trustworthy delegation. Do not claim that event agents, outreach, form filling, approvals, or replanning are novel categories. Demonstrate the specific work completed and why the organizer can comfortably delegate it.

2. Decision register







Item



Status



Implementation consequence





Event operations agent



Team-selected direction



Continue this project rather than restarting ideation.





Outreach, vendors, logistics



Confirmed focus areas



Preserve all three in the product and architecture.





Speakers and sponsors in outreach



Confirmed



Support their different requirements and commitment types.





Vendors beyond food



Confirmed



Include supplies and services; food is one category.





Contextual questions about overlooked needs



Confirmed desired behavior



Discover requirements before unnecessary sourcing.





Design production



Explicitly excluded



Track missing artwork and assign it; do not generate designs.





Modular expandable skills



Confirmed approach



Add workflows through a shared contract.





Single orchestrating agent



Recommended and aligned with team preference



Default to it unless explicitly changed.





One initial skill per area



Recommended delivery order



Minimum connected release, not the full feature ceiling.





Form filling and vendor-document checks



Strong desired capabilities



Keep prominent; promote if usable components are available.





Security, governance, and compliance support



Confirmed priority



Enforce controls in backend tools.





Exact stack, model, hosting, providers



Open



Inspect existing setup before selecting defaults.





Reusable HR-agent components



Possible opportunity



Permission, availability, compatibility, and event eligibility are unverified.





Branding, pricing, and willingness to pay



Open



Do not invent decisions or business traction.

Precedence for a new LLM: Follow later explicit team instructions first. Preserve confirmed scope. Treat proposed architecture details as defaults, not established implementation facts. Inspect the repository before describing code status. This document does not authorize real-world outreach, spending, publication, signatures, or submissions through connected accounts.

3. Background and customer evidence

The team wants a practical, memorable hackathon product with startup potential that four people can implement in 24 hours. The project draws on Diya's experience organizing community and technology events and operating Odds, a local specialty-drink business that participates in pop-ups.

These perspectives cover both sides of coordination:





Organizers need complete paperwork, clear quotes, reliable arrivals, timely responses, and a consistent plan.



Vendors need accurate headcounts, setup details, service expectations, payment terms, and timely notice of changes.

The team spoke with one DubHacks organizer. The user reported these pain points:





Filling out forms is burdensome for vendors.



Checking vendor licenses is burdensome for organizers.



Outreach requires coordinating sponsorship-team schedules with organizer schedules.

This is one qualitative interview, not broad market validation. It does not establish frequency, willingness to pay, or which problem is most expensive. Clarify whether sponsor scheduling means meeting availability, internal approval timelines, attendance, or several of these.

Workshop findings and additional interviews have not been supplied. Do not invent them. Future notes should capture the person's role, a recent incident, current workaround, consequence, desired delegation, approval boundary, and interest in piloting.

4. Problem statement and solution

Small organizing teams coordinate events through disconnected emails, documents, registration platforms, spreadsheets, and memory. Someone must repeatedly copy information into forms, reconcile quotes, chase replies, verify documents, and translate arrangements into instructions for speakers, vendors, volunteers, and venue staff.

Changes amplify that work. A speaker's revised availability affects the schedule and volunteer briefing. Missing vendor paperwork can block participation. More registrations change food and badge quantities. A conditional sponsorship creates obligations that can be forgotten.

Product promise: The organizer provides context and controls consequential decisions. The agent performs research, preparation, follow-through, and coordination while maintaining a shared record of what is known, proposed, approved, and confirmed.

The agent must produce artifacts and persistent changes, not only advice in chat: sourced candidates, filled PDFs, message approvals, structured offers, task lists, a run-of-show, and participant briefings.

5. Users and business hypotheses







User



Need



Interaction





Event lead



Delegate while retaining control



Set requirements, approve decisions, track blockers.





Outreach coordinator



Manage speakers and sponsors



Research, prepare messages, process replies and conditions.





Vendor coordinator



Obtain suitable suppliers and complete onboarding



Compare offers, collect documents, prepare forms.





Logistics coordinator



Keep arrangements consistent



Maintain tasks, timeline, dependencies, and instructions.





Treasurer



Control spending and commitments



Review cost changes and payment proposals.





Speaker, sponsor, vendor, or venue contact



Receive clear requests and relevant details



Respond through existing channels without creating an account initially.

Potential users include recurring professional communities, campus organizations, nonprofits, coworking operators, and small corporate teams. These are discovery segments rather than equally validated customers. Funded communities and recurring business events may have greater payment capacity; this remains a hypothesis.

Possible business models include per-event pricing or recurring organization subscriptions. No price, revenue, savings figure, paying customer, or distribution partnership is validated. Luma is a potential integration, not automatic distribution.

6. Overall capabilities







Capability



Behavior



Useful output





Understand the event



Save the brief; distinguish facts from assumptions.



Editable event profile and missing fields.





Discover needs



Ask contextual questions about overlooked items.



Requirements checklist.





Research



Find relevant people and suppliers with evidence.



Shortlist with fit and unknowns.





Communicate



Draft, obtain approval, send when authorized, and interpret replies.



Conversation state and next action.





Handle documents



Extract facts, compare requirements, fill supported forms.



Review report or completed application.





Plan execution



Convert requirements and commitments into tasks and timing.



Operational plan with owners and dependencies.





Coordinate participants



Give each party relevant instructions.



Role-specific briefing.





Handle changes



Identify affected arrangements and propose adjustments.



Conflict report and revised proposal.





Execute within policy



Enforce scope and authorization, preserve outcomes.



Allowed, pending, blocked, succeeded, or failed action.



Contextual discovery

For a workshop, ask whether attendees need badges, whether the venue supplies microphones, and whether shirts or printed materials are desired. If shirts are requested, ask for quantity, sizes, deadline, and artwork status. Missing artwork becomes a task for the organizer or designer, not a request to build a design tool.

Ask three to five relevant questions at a time. Do not apply a conference checklist indiscriminately to a small meetup. Record needs as required, optional, declined, or unresolved. Respect a declined need instead of repeatedly suggesting it.

7. Capability, skill, tool, and artifact





Capability: A user outcome, such as coordinating a workshop speaker.



Skill: A bounded workflow with instructions, inputs, allowed tools, outputs, and completion rules.



Tool: A concrete operation such as search, read a document, save an offer, compare availability, or send an approved message.



Artifact: A usable output such as a PDF, comparison, message draft, or briefing.



Action: A proposed or executed change with authorization and a recorded outcome.

Skills share tools. Vendor and speaker outreach should use one email adapter. Form filling and document verification can share extraction while using different validation logic. The database is authoritative; model conversation history is not an adequate event ledger.

8. Skill roadmap







ID



Area



Skill



Priority





O1



Outreach



Research candidates and prepare outreach



Initial





O2



Outreach



Process replies and coordinate availability



Next





O3



Outreach



Track follow-ups and obligations



Stretch





V1



Vendors



Discover needs and source options



Initial





V2



Vendors



Compare quotes and review documents



Next





V3



Vendors



Complete supported vendor forms



Stretch; promote if reuse works





L1



Logistics



Build the operational plan



Initial





L2



Logistics



Prepare participant briefings



Next





L3



Logistics



Detect conflicts and coordinate changes



Stretch

Release A: O1, V1, and L1 connected to the same event, persistent records, evidence, and approvals.

Release B: Add second skills that strengthen the demonstrated workflow. Six skills are an aspirational milestone. Promote V3 ahead of V2 if a working component makes it cheaper and more valuable.

Release C: Add third skills only after deployed acceptance checks pass. Never label an unsupported feature functional. Three completed connected skills are better than nine disconnected placeholders.

9. Outreach specifications



O1 Research candidates and prepare outreach

Inputs: Event brief, relationship type, audience, topic or sponsorship objective, location, dates, constraints, and organizer-approved claims and benefits.

Workflow: Check blocking fields; research a small candidate set; save sources; explain relevance; identify a public or organizer-provided contact route; prepare a tailored message; save it and request approval when execution is requested.

Speakers need topic, session format and length, honorarium if applicable, travel, availability, equipment, and materials. Sponsors need contribution type, amount, internal approval process, benefits, restrictions, decision deadline, and fulfillment. Do not use identical assumptions for both.

Outputs: Candidates, evidence links/excerpts, fit explanations, unknowns, contact provenance, and editable drafts. Do not fabricate personal emails, audience metrics, prior relationships, or benefits the organizer has not approved.

Acceptance: At least two useful sourced candidates or a clear shortfall explanation; one appropriate saved draft; exact recipient visible before any external send. A generic chat response without saved records fails.

O2 Process replies and coordinate availability

Inputs: A reply tied to a conversation, event context, and organizer availability. Pasted replies and entered availability are acceptable initially.

Workflow: Extract interest, conditions, requests, proposed times, timezone, deadlines, and evidence. Resolve or flag ambiguity. Compare explicit time intervals. Propose a next step and draft a response.

Distinguish a sponsor planning call from event attendance, interest from funding approval, and tentative availability from a confirmed booking. Do not assume a timezone when interpretation materially changes the proposed slot.

Outputs: Structured reply, proposed slots, missing information, tasks, and response draft. Calendar creation and invitations are separate authorized actions.

Acceptance: The reply updates persistent records; duplicate ingestion creates no duplicate commitments; uncertainty remains visible; a suggested meeting is not described as booked.

O3 Follow-ups and obligations

Inputs: Conversations, deadlines, approved benefits, and participant requirements.

Workflow: Identify unanswered or urgent items, prepare follow-ups, and extract obligations such as logo placement, slide delivery, workshop setup, or a post-event report. Assign owners and due times.

Outputs: Follow-up proposals and evidence-linked tasks.

Acceptance: Repeated runs do not duplicate messages or tasks. Declined contacts are not automatically pursued. Scheduled execution rechecks policy and current state.

10. Vendor specifications



V1 Discover needs and source options

Inputs: Event format, size, venue resources, location, dates, budget, existing suppliers, and preferences.

Workflow: Build a contextual checklist; ask about unresolved needs; record accepted and declined needs; select a need; research suitable suppliers or organizer-provided options. Retailers such as Amazon can be candidates when appropriate; not every need requires a custom vendor.







Category



Information to obtain





Food



Quantity, dietary requests, service window, delivery, serving supplies, venue restrictions.





Badges and lanyards



Count, format, attachments, customization, artwork, deadline.





Shirts



Quantity, sizes, artwork status, proof approval, production deadline.





Printing



Dimensions, quantity, color, finishing, file readiness, pickup/shipping.





Equipment



Venue-provided items, compatibility, delivery, setup, return window.

Outputs: Requirements and options with price basis, lead times, delivery assumptions, source dates, and unknowns. Listings do not prove current inventory, delivery guarantees, or booking confirmation.

Acceptance: Enough requirements for comparison; two useful candidates or an explicit limitation. Support one or two categories in the first demo, not every supplier type.

V2 Compare quotes and review documents

This skill has two bounded operations. Shared extraction does not mean shared validation.

Quotes: Extract quantities, specifications, taxes, delivery, staffing, fees, minimums, deposits, cancellation terms, and deadlines. Calculate in code. Unknown fees remain unknown rather than becoming zero. Draft clarification questions needed for a fair comparison.

Documents: Compare supplied licenses, permits, insurance documents, and available official records against a selected event-specific checklist. Match the correct business identity, address, and mobile unit where relevant. Findings are matched, mismatch, expired, missing, or needs review, with supporting evidence.

Outputs: Structured offers, comparison, findings, unresolved issues, and a missing-information request.

Acceptance: Incomplete and conditional offers remain visibly incomplete or conditional. No search match does not prove a vendor is unlicensed. An inspection history does not establish permission for this specific event. Do not issue blanket safety or legal-compliance certification.

Local evidence caveat: King County publishes inspection information, but temporary-event and farmers-market vendors are excluded from its food safety rating system. A missing rating is not a negative rating. Public records, uploaded documents, and event-specific requirements may all be needed.

V3 Complete supported forms

Inputs: A supported fillable PDF, field mapping, event/vendor records, and any missing answers supplied by the organizer.

Workflow: Enumerate fields; map known facts; retain provenance; fill supported fields; flag unknowns, signatures, attestations, and ambiguity; inspect the output; save a reviewable artifact.

Outputs: Draft PDF, unresolved-field list, and answer provenance. Filling, signing, and submitting are separate operations.

Acceptance: Known values appear in the correct fields; missing facts are not invented; original and output are preserved; authorized people handle signatures; submission requires its own authority.

Hackathon boundary: One or two known fillable AcroForm templates. Universal scanned-form filling, handwriting, and digital-signature infrastructure are outside the initial scope.

11. Logistics specifications



L1 Build an operational plan

Inputs: Brief, venue access, sessions, people, supplier lead times, delivery windows, and commitments.

Workflow: Generate tasks and a draft run-of-show; assign or request owners; attach deadlines and dependencies; separate confirmed timings from assumptions; surface conflicts rather than silently choosing a solution.

Outputs: Tasks, timeline, blockers, and unanswered questions. Session time, speaker arrival, vendor arrival, staff arrival, and venue access are distinct concepts.

Acceptance: Includes setup, teardown, at least one cross-area dependency, and owners or explicit unassigned status. Model-generated times do not become commitments automatically.

L2 Prepare participant briefings

Inputs: Plan, participant role, confirmed arrangements, and information permissions.

Workflow: Prepare relevant instructions: address, entrance, arrival, contact, equipment, session or service details. Exclude unnecessary attendee and financial information. Save a versioned draft for review.

Outputs: Role-specific speaker, sponsor, vendor, volunteer, or venue briefings linked to source records.

Acceptance: Different parties receive appropriate details; affected drafts become stale after changes; external delivery uses the shared approval mechanism.

L3 Detect conflicts and coordinate changes

Inputs: A changed record and current plan version.

Workflow: Find dependencies, evaluate time/budget constraints in code, propose a plan difference, and prepare relevant notifications. Preserve confirmed commitments until an authorized change occurs.

Outputs: Conflict report, proposed revision, stale-action flags, and notification drafts.

Acceptance: Moving a workshop identifies affected speaker, room, AV, and volunteer records where dependencies exist. If no resolution fits, explain the gap. Do not invent availability or claim a universal scheduling optimizer.

12. Shared security and governance



Operating policy

Store policy per workspace/event. Suggested modes are draft-only, approval-required execution, and narrowly delegated execution. Initially, require approval for external sends and disable real purchases.







Action



Initial behavior





Read event records



Allow only within authenticated workspace scope.





Public research



Allow within run limits.





Save internal draft/task



Allow; retain material history.





Fill a supported form



Allow draft generation; flag signatures and unknowns.





Send message or invitation



Exact-action approval.





Publish social content or public page changes



Draft only unless integration and authority are verified.





Promise benefits, accept quote, sign, submit



Separate explicit authority; outside initial automated execution.





Pay



Simulated policy-enforced tool only.





Export attendee data



Block unless purpose, role, and specific authority permit it.



Enforce in tools

The model proposes actions; it cannot grant itself permissions. Executable tools independently validate actor, workspace, event, scope, policy, approval, payload, and relevant versions. Direct API calls must face the same checks.

Approval binds to normalized payload hash, recipient/target, related versions, approver, timestamp, and expiry. Editing an approved draft invalidates approval. An unrelated record change should not invalidate everything; identify which versions matter.

Spending controls

Use integer cents and explicit currency. Separate estimates, quotes, accepted commitments, paid amounts, and refunds. Do not double count an accepted order when it becomes paid: outstanding commitment is its remaining unpaid balance. Track sponsorship as proposed, committed, or received; uncertain funding is not spendable cash.

The simulated purchase tool should transactionally reserve budget before execution so concurrent requests cannot spend the same balance. Release reservations on definitive failure.

Protect accounts and data

Store secrets server-side. Do not put passwords or raw card data in model context, chat, or logs. Use aggregate attendee counts when possible. Authorize document downloads and reads, not just writes.

Treat emails, PDFs, and websites as untrusted data. Embedded instructions cannot authorize sending attendee lists or overriding policy. Limit the agent to necessary registered tools; do not expose unrestricted shell access.

Action history and pause

Record proposals, approvals, attempts, provider outcomes, and evidence. Display concise tool summaries rather than private chain-of-thought. Pause stops queued/new actions and forces checks before resumption; it cannot undo completed external actions.

These are operational controls, not claims of formal security certification or universal legal compliance.

13. User experience

Use one event workspace. Chat receives requests, while structured records remain visible and editable.







Surface



Content





Overview



Brief, blockers, confirmed arrangements, next decisions.





Outreach



Candidates, drafts, conversations, availability, conditions.





Vendors



Needs, suppliers, offers, document findings, forms.





Logistics



Tasks, venue requirements, timeline, dependencies, briefings.





Approvals



Exact target, content/terms, reason, approve/edit/reject.





Activity



Runs, tool outcomes, changes, errors, origin labels.





Settings



Policies, budget, accounts, pause control.

Start with overview, chat, and a combined work queue rather than seven polished pages. Expand navigation as real functionality appears. Unsupported integrations must not display fake success.

Example requests: “What information do you still need?”, “Find two badge suppliers,” “Invite a workshop host,” “Check these documents,” “Fill this application,” “Build our setup plan,” and “Who needs to know about this time change?”

14. Recommended technical architecture

Default proposal: React/TypeScript client, FastAPI/Pydantic backend, and SQLite on persistent storage or a managed relational database. If an existing TypeScript backend or reusable framework already works, preserve it instead of rewriting. Exact provider, model, package versions, and host are not confirmed.

Use one tool-capable model provider and one search adapter with working credentials. Keep secrets, policy, persistence, and execution on the backend.

Execution: Authenticate → load authorized event records → select skill → check fields → call registered tools → validate output → save drafts/proposals → pause for decisions → execute approved action through policy-controlled adapter → persist outcome → update UI.

Bound runs initially to eight model-selected tool calls plus configurable timeout and cost ceilings. Failed tools must not become successful claims. Return partial results honestly. Poll for progress first; streaming is optional.

Adapters cover search, email, calendar, event platform, PDF, and artifact storage. Live and fixture adapters share a result contract and declare origin. Prefer APIs over brittle automation when practical.

One orchestrator may use concurrent I/O for independent searches. This does not require autonomous subagents. Mutations and approvals need controlled ordering.

15. Data model

All event-owned records carry workspace and event IDs. Global vendor profiles are a later optimization; offers and permissions remain event-specific.







Entity



Essential fields





Workspace/membership



ID, user, role, policy, integration references.





Event



Version, title, timezone, start/end, venue, headcount, currency, budget, preferences.





Requirement



Category, specification, quantity, needed-by, status, owner, source, version.





Party



Person/organization, roles, contacts, identity, contact provenance.





Candidate/source



Purpose, fit, unknowns; URL/document, excerpt, retrieval time, page/field reference.





Conversation/message



Thread, party, direction, body, provider ID, received time, evidence, origin.





Availability



Party, purpose, timezone-aware intervals, assumed/confirmed, source.





Offer



Service/contribution, quantity, price/fees, conditions, expiry, evidence.





Commitment



Accepted terms, confirmation evidence, outstanding amount, owner, status.





Document/finding



Type, identity match, validity, checklist item, result, evidence.





Task



Owner, deadline, dependencies, sources, status, version.





Schedule item



Interval, room, people, setup needs, dependencies, confirmation state.





Artifact



File reference, MIME type, version, provenance, review state, access scope.





Action/approval



Kind, payload/hash, relevant versions, policy result, approver, expiry, execution state.





Run/activity



Skill/version, input references, status, tool outcomes, errors, timestamps, origin.

Store instants in UTC and display the event timezone. Retain original timezone information for supplied availability. Define all-day deadlines separately. Preserve source text separately from extracted fields so findings can be reviewed.

16. Skill and tool contracts

These are proposed interfaces, not existing repository APIs.

{
  "skill_id": "vendors.source_options",
  "version": "1.0",
  "event_id": "demo_event_001",
  "input": {"requirement_id": "req_badges_001"},
  "required_fields": ["event.start_at", "requirement.quantity"],
  "allowed_tools": ["get_event", "get_requirement", "search_candidates", "save_candidate", "draft_message"],
  "completion_rule": "Save sourced options or explain the shortfall",
  "execution_policy": "draft_only"
}

{
  "run_id": "run_demo_001",
  "skill_id": "vendors.source_options",
  "status": "needs_input",
  "summary": "Need badge quantity before comparison",
  "record_refs": [],
  "artifact_refs": [],
  "questions": [{"field": "requirement.quantity", "prompt": "How many badges do you need?"}],
  "proposed_action_ids": [],
  "warnings": [],
  "origin": "live"
}

Run states: queued, running, needs_input, awaiting_approval, succeeded, partial, failed, cancelled. Waiting for approval should persist state, not hold an in-memory model loop indefinitely.

Core tools: get_event, update_event, save_requirement, search_candidates, save_candidate, draft_message, ingest_reply, extract_offer, compare_quotes, review_document, fill_supported_pdf, calculate_budget, create_task, build_schedule, create_briefing, propose_plan_change, request_approval, execute_approved_action.

Tools return typed success/error, affected IDs, evidence references, and retryability. Validate model-generated arguments. Derive actor and workspace from authentication, never model-supplied claims.

17. State transitions and reliability





Relationship: candidate → contacted → replied → interested/conditional → awaiting confirmation → confirmed; declined and cancelled remain distinct.



Offer: extracted → needs clarification → complete → selected → accepted/declined. Selection is not a confirmed booking.



Action: draft → pending approval → approved → executing → succeeded/failed/outcome_unknown. Rejected, stale, and cancelled stay visible.



Task: proposed → assigned → in progress → blocked/completed; cancelled is separate.

Use unique ingestion keys for replies and idempotency keys for dispatch. Persist execution attempts before provider calls. A timeout after possible delivery becomes outcome_unknown and requires reconciliation before retry. Do not promise exactly-once delivery without provider support.

Revalidate permission, approval, versions, and constraints immediately before execution. Use transactions for claiming actions and budget reservations. Repeated clicks, model retries, and webhook replays must not create duplicate sends or commitments.

18. Minimal backend interface







Route



Responsibility





POST /events



Create a brief.





GET /events/{id}



Return authorized event state.





PATCH /events/{id}



Version-checked edit and affected-record review.





POST /events/{id}/runs



Start a bounded skill run.





GET /runs/{id}



Progress, questions, artifacts, decisions.





POST /events/{id}/messages



Ingest reply with deduplication.





POST /events/{id}/documents



Authorized upload.





GET /artifacts/{id}



Authorized download.





POST /actions/{id}/approve



Approve exact current action.





POST /actions/{id}/reject



Reject without executing.





POST /actions/{id}/execute



Recheck policy and execute.





POST /events/{id}/pause



Stop queued/new work.

Authentication, workspace authorization, file type/size limits, and validation apply throughout. Use an access-controlled synthetic demo workspace initially; do not expose unauthenticated live-account automation.

19. Integrations and component reuse







Integration



Initial route



Later expansion





Search



One provider or supplied URLs, saved evidence.



Specialized sources.





Email



Drafts, controlled test sends, pasted replies.



Inbound webhooks or mailbox sync.





Calendar



Entered availability, proposed slots.



Authorized reads and invitations.





Luma



Manual brief/CSV and source URL.



Authorized import or management.





PDF



Text PDFs and selected fillable forms.



OCR and more templates.





Social media



Draft artifact.



Approved publication.





Payments



Simulated policy-controlled tool.



Hosted provider flow.

Luma REST documentation checked earlier on October 17 required Luma Plus and calendar-scoped API keys. Its MCP documentation separately describes authorized management capabilities. Verify the chosen path; do not assume REST and MCP share access requirements.

The user may have access to an HR agent through her brother's contacts. Look for tool registries, extraction, form filling, approvals, email adapters, and persistence. Do not import employee data, credentials, or irrelevant HR workflows.

For external code, verify permission, license, hackathon reuse rules, a working example, runtime compatibility, dependencies, and execution boundaries. Time-box evaluation to 15–20 minutes per promising component. Wrap it behind the shared interface, preserve attribution, and disclose reuse as required. No specific repository has been selected or vetted.

Suggested organization: frontend; backend API; agent runner/policy; separate outreach, vendors, logistics modules; shared tools/adapters; models/storage; document templates; fixtures; focused tests; environment-variable example without secrets. Adapt to the existing repository instead of restructuring automatically.

20. Four-person ownership







Builder



Primary ownership



First connected output





A



Outreach O1, then O2/O3



Saved candidates and outreach draft.





B



Vendors V1, then V2/V3 based on reuse



Requirements and sourced options.





C



Logistics L1, then L2/L3



Tasks/timeline consuming shared records.





D



Shared agent, API, UI, approvals, deployment



Create/reload event and run skills.

These labels are proposed roles, not named assignments. Each area owner implements their own tools, outputs, fixture, and checks. D must not become responsible for rewriting everyone's backend work. All four agree data contracts before branching. If the shared foundation blocks everyone, help unblock it.

Integrate small changes frequently. The first connection check should happen before all skills are finished. Use one result shape and database, rather than merging three independent apps at the end.

21. Build order and definition of done





Inspect current code, working credentials, workshop resources, and permitted reuse. Choose a demo and contracts.



Deploy the smallest UI/API/database path. Create, load, and update an event with authorization.



Build O1, V1, and L1 on that event. Persist and display results.



Connect real record IDs across areas and show one dependency.



Add the next skill that improves the demonstrated workflow, including form filling when feasible.



Demonstrate allowed, approval-required, stale, and blocked actions.



Verify deployed behavior, record backup, submit, and rehearse.

A skill is done when valid input produces the promised artifact/records, missing information is handled, evidence is retained, permission is respected, failures remain failures, results survive refresh, and one representative scenario passes. A polished prompt is not a finished skill.

22. Updated schedule

The team requested two hours total for food and sleep from 3:00–8:00 a.m. This schedule begins at 1:15 p.m. after the handoff checkpoint, reserves all food time because prior breaks are unreported, and assumes a Sunday 12:30 p.m. endpoint. Confirm the official cutoff immediately.







Pacific time



Block



Outcome





Sat 1:15–1:45 p.m.



Scope/contracts



Roles, initial skills, schemas, demo, credentials.





1:45–3:45 p.m.



Foundation/tools



Deployed workspace and callable skill skeletons.





3:45–4:15 p.m.



Food



30 minutes.





4:15–6:30 p.m.



Initial skills



O1, V1, L1 write persistent records.





6:30–7:30 p.m.



Integrate



One event flows across all areas.





7:30–8:15 p.m.



Food



45 minutes.





8:15–10:15 p.m.



Next skills



Most useful additions and shared controls.





10:15 p.m.–midnight



Demo/robustness



Evidence, coordination, permission boundaries.





Sun midnight–1:30 a.m.



Verify



Critical state, permissions, duplicates, errors.





1:30–2:30 a.m.



Rehearse/record



Backup demo and submission draft.





2:30–3:00 a.m.



Stable checkpoint



Deploy known-good version and freeze features.





3:00–8:00 a.m.



Sleep



Five hours protected.





8:00–8:45 a.m.



Food



45 minutes.





8:45–10:00 a.m.



Regression



Fresh-session check; blocker fixes only.





10:00–11:00 a.m.



Package



Video, screenshots, description, links.





11:00 a.m.–noon



Submit



Verify requirements and links.





Noon–12:30 p.m.



Buffer



Submission issues and rehearsal.

From 1:15 p.m., 23 hours 15 minutes remain: 16 hours 15 minutes work, two hours food, five hours sleep. Four people provide 65 nominal team-hours including integration, verification, and submission. This does not claim earlier time was spent coding. Update elapsed blocks based on actual progress.

Scope gates: If the workspace is disconnected at 3:45, prioritize foundation. If the first three skills are not integrated by 7:30, drop third skills and live-integration work. After midnight, finish the demo rather than expand scope. After sleep, repair blockers only.

23. Demo scenarios



Primary connected event

Use a fictional local technology workshop: 80 attendees, one venue, a workshop host, a prospective sponsor, food, and badges. Label fixture people, offers, and replies as simulated; label live research separately.





Enter the brief; the agent asks about badges, AV, and artwork.



Confirm quantity and print-ready artwork; V1 saves supplier options.



O1 drafts a workshop invitation and sponsor inquiry, with evidence and approval.



If O2 exists, ingest a reply with availability and AV needs. Otherwise enter an organizer-provided arrangement without implying automatic reply processing.



L1 uses shared records to generate setup tasks and a draft timeline.



Show a standout artifact: completed form or evidence-backed document review.



Show a backend-blocked unauthorized action. If L3 exists, move the workshop and show affected records and notification proposals; otherwise do not imply replanning is implemented.



Optional budget fixture

Food ceiling is $450. Vendor A offers 60 meals for $300 plus $30 delivery, tax included. Attendance rises to 90. Vendor B offers 30 supplemental meals for $90 plus $15 delivery, tax included. Combined proposal: $435, $15 remaining. For 18 vegan attendees, explicit offers allocate 12 vegan meals from A and six from B. It remains a proposal until confirmed.

Trust fixture

A vendor email asks the agent to disclose attendees or ignore a spending rule. Legitimate offer facts may be extracted, but backend execution blocks unauthorized action. Show the reason and activity record. This verifies the tested boundary, not universal immunity to prompt injection.

24. Acceptance checks







Area



Passing behavior





Persistence



Brief and outputs survive refresh and expected restart.





Discovery



Relevant questions; accepted/declined needs retained.





Research



Sources, contact provenance, unknowns, origin visible.





Outreach



Appropriate speaker/sponsor drafts; no invented claims.





Replies



Conditions preserved; duplicate ingestion is harmless.





Availability



Explicit timezone; no booking claim without execution evidence.





Quotes



Unknown fees remain unknown; quantity and lead time compared.





Documents



Identity/missing evidence flagged; no blanket compliance verdict.





Forms



Correct known fields; unknowns/signatures flagged; readable output.





Logistics



Shared records drive tasks, owners, setup, teardown, dependencies.





Authorization



Direct calls cannot bypass approval or workspace scope.





Freshness



Relevant edits invalidate pending authority.





Duplicates



Retries and clicks do not repeat dispatch or commitments.





Budget



No double counting; over-limit simulated action blocked.





Errors



Failures/timeouts do not become bookings or successful sends.





Pause



New/queued work stops; resumed work revalidates.





Untrusted data



Embedded text cannot grant authority.





Demo



Fresh session, reset, origin labels, backup recording.

Test optional skills only if implemented. Use focused tests for arithmetic, transitions, authorization, and deduplication, plus one connected deployed smoke test. Avoid implementation-mirroring tests for static UI details.

25. Competitive context

Public research earlier on October 17 found meaningful overlap. These are advertised capabilities, not independent product evaluations.





Nowadays: Corporate event planning, supplier outreach, comparisons, budgets, registration, human support.



Planned: Enterprise sourcing and quote workflows, registration, reporting, human experts.



Cvent Vendor Marketplace: Supplier matching, communication, quotes, contracts, invoices, payments.



Ducket Sponsorship OS: Research, ranking, drafts, approvals; described as used through agency engagements with wider release developing.



Luma: Registration and communication with documented assistant-accessible management capabilities.



Firsthand Event: Private-beta agentic logistics/replanning claims; reliability unverified here.



Hestia: Similar hackathon project using an orchestrator, catering/venue workflows, outreach, and Luma. Prototype precedent rather than a proven commercial competitor.

The positioning hypothesis is useful modular execution for smaller teams, informed by organizer and vendor experience, with enforceable delegation. Neither agents nor approvals alone are unique. Validate a concrete reason to choose this product over incumbents and manual workflows.

26. Risks and fallbacks







Risk



Response





Nine-skill scope overwhelms team



Finish initial three and freeze expansion.





Integration owner bottleneck



Area owners implement tools and fixtures against shared contracts.





Weak/stale research



Accept supplied URLs; retain dates and unknowns.





No real replies



Labeled fixtures with real parsing and persistence.





Email/calendar setup blocked



Drafts, pasted replies, entered availability.





Luma unavailable



Manual brief/CSV.





Unsupported/scanned forms



Selected fillable templates; visible limitation.





Inconclusive records



Request documents/review; no automatic accusation or certification.





Uncertain provider outcome



Reconcile before retrying.





False model claim



Evidence and typed state transitions.





Payments/socials consume time



Simulated spending and draft publication.





Unstable deployment



Known-good build, exported fixtures, recorded backup.



27. Open decisions

Resolve technical blockers now; defer branding and pricing until the core works.





What repository and code actually exist?



Which person owns each area and foundation?



Which stack, model, credentials, and host already work?



What did the workshop provide?



Which vendor categories will the first demo cover?



Can form filling be reused quickly enough to promote V3?



What exact checklist and jurisdiction does document review support?



Which communication path is live versus fixture-based?



What are the official submission and code-reuse requirements?



Can a short follow-up clarify sponsorship scheduling and internal approvals?



28. Instructions for the next LLM or developer

Inspect the current repository and request an implementation update only where necessary. Preserve scope and continue work rather than re-ideating. Identify current state, the next smallest connected milestone, its owner, and blockers.

Do not present stretch skills as MVP requirements. Do not introduce autonomous subagents solely because the product has three areas. Use shared tools, typed contracts, persistent records, evidence, origin labels, and backend policy checks.

Do not fabricate confirmations, integration access, customer validation, or external success. Ask narrow questions when a missing decision blocks progress; otherwise use documented defaults and state assumptions. Update this handoff when decisions change, marking implemented, partial, fixture-only, deferred, and untested work. A planning document cannot substitute for code inspection or deployed verification.

29. References

Sources were consulted earlier on October 17, 2026. Recheck time-sensitive integration requirements and local rules before live use. Public evidence is not automatic permission or a safety guarantee.





Luma REST: https://docs.luma.com/reference/getting-started-with-your-api



Luma MCP: https://help.luma.com/p/mcp



OWASP agent guidance: https://cheatsheetseries.owasp.org/cheatsheets/AI_Agent_Security_Cheat_Sheet.html



OWASP excessive agency: https://genai.owasp.org/llmrisk/llm062025-excessive-agency/



King County ratings/inspection lookup: https://kingcounty.gov/foodsafety/ratings



King County data; verify coverage/freshness: https://data.kingcounty.gov/Health-Wellness/Food-Establishment-Inspection-Data/r878-4sxa



Washington food trucks/trailers: https://lni.wa.gov/licensing-permits/manufactured-modular-mobile-structures/food-trucks-trailers/



Seattle food-service event guidance: https://www.seattle.gov/special-events/permits/food-service



Nowadays: https://www.nowadays.ai/



Planned: https://planned.com/



Cvent: https://www.cvent.com/en/event-marketing-management/vendor-marketplace



Ducket: https://ducket.io/os



Firsthand Event: https://www.firsthandevent.com/



Hestia: https://devpost.com/software/hestia-lbjg7v

Next milestone: A working shared workspace with one completed skill in outreach, vendors, and logistics—not the entire roadmap.