# Decisions
This file contains my personal decisions and assumptions made based on the BRIEF.md before starting to build the product.

## Who and what
* Customer: An institutions / organizations operations team. Organizations can be space agencies or other private companies. 
* Main or power user: A mission lead. This person manages missions and staffs them with qualified and available staff while ensuring they are not overloaded. 
* Other users: 
  * A director. This person approves missions sent for a approval by the mission lead and oversees the organization. This includes managing organizational settings (skills)
  * A crew member. This person manages their profile (manage their skills and availability) and responds to assingments (accept / decline)
* Today's pain point: Mission leads spend hours cross-referencing skill profiles, availability calendars and existing commitments. Staffing missions efficiently is the bottleneck

## Requirements
### P0: Core requirements enabling first initial version ready to pitch to a customer
#### Delivery
1. Ready version a reviewer can clone and run locally in minutes
    - GitHub repository
    - Setup instructions
    - Seeding initial data - demo
    - Design document written before implementation and used to guide the agent
    - API + CLI
    - Evidence of verification: test output and scripted CLI demo
2. Seed data with 2 orgs and 2 Directors in one org
    - Representative data enough crew so the matcher shows trade-offs (experts vs closest fit, leave, workload)
#### Auth and tenant
3. Multi-Tenant system: Organizations are separate tenants. Exclusive data access
    - Enforced in data-access layer and with composite foreign keys in DB
4. Users have different roles (Director, Lead, Crew member) and role permissions are enforced
    - Login in the CLI with a seeded user (e.g. mc login --user username)
    - CLI shows a clear error for forbidden actions: which role and which rule
    - Actions / Permissions are protected on the API layer
#### Mission lifecycle
5. Initial version of mission lifecycle management
    - Each missions needs approval
    - Leads send for approval to Director
    - Directors approve / reject. The approval view shows the matcher preview
    - Crew members accept/ decline assignment
6. Directors can view the whole org (broad view)
    - All missions
    - All crew members (API + CLI)
#### Crew and skills
7. Crew members have a skill profile and availability and manage them via CLI
    - Skills: list, add, update, remove own skills from the org catalogue with proficiency
    - Availability: list, add, remove own unavailability
8. Crew members see their own assignments incl. history (past, declined), profile and mission and can respond to assignments (accept / decline)
9. Each org has own set of skills
    - Seed data in this phase, editing in P1
#### Matching
10. Smart suggestions of crew members for a mission
    - Inputs: Skills, availability, workload
    - Lead can run a readonly preview in draft status to check the mission can be staffed before submit
    - Invites only when mission is approved
    - Rematching only fills open slots and never suggests a member who declined this mission
#### CLI
11. Primary workflows run through the CLI: login, missions list /detail, create/ edit, submit, approve / reject, matching preview and invites, my assignments and history (crew), accept / decline, my profile and availability (crew).
#### Quality
12. Tests: minimal happy path only for now
    - Happy path per workflow: lifecycle, matcher, invites and responses, crew profile
    - Cross org access checks: other org's resources return 404
13. Evidence of verification
    - Scripted end-to-end CLI demo over the seed data (full mission lifecycle)
    - Test results documented: Readme?

### P0 build order
Each step ends with its happy path test and cross org check. Each step is one or more commits.
1. Skeleton: docker-compose Postgres, FastAPI app, Alembic, Typer entry point, README run steps
2. Data model + first migration + seed data (2 orgs, 2 directors in one org, leads, crew, skills, leave, existing assignments for workload)
3. Auth and tenant: mc login, JWT with user_id, per request user / org / role load, org scoped data-access layer, RBAC error format
4. Missions in DRAFT: create, edit, slots, list, show
5. Matcher preview: filters, ranking, slot assignment. mc missions match
6. Approval: submit, withdraw, approve, reject. No self approval, additional director flag, preview in approval view
7. Staffing: invite, mc assignments list / accept / decline, double booking check, decliner exclusion on rematch
8. Remaining transitions: withdraw from APPROVED back to draft, start (guard), complete, cancel. Assignment cancellation
9. Crew profile: mc profile show, skills, availability
10. Scripted end-to-end CLI demo + test results in README

### P1: Next extensions: If time permits in this session
#### Crew and skills
1. Directors manage org settings
    - Skill catalogue
#### Mission lifecyle
2. Mission audit logs
#### Matching
3. Decision insights for lead: Excluded members: Why?
4. Rank breakdown per suggestion: Why is this the best person for the slot
#### CLI
5. Short references for missions (`MSN-<n>`) and skills (`slug`), see Short references
...

### P2: Scoped as outside of this session
#### Auth and tenant
1. Noisy-neighbour protection / uneven org sizes in this multi tenant architecture
2. Real idp oidc, login / signup, 
3. Postgres RLS as second layer for reads (composite FKs only protect writes / links)
4. User and role management
#### Mission lifecycle
5. Approval workflow customization
6. Crew members withdraw after accepting
7. Reject with comment, cancel with reason
8. Reassign the lead of a mission
#### Crew and skills
9. Edit / archive skills
10. Verification of self assessed proficiency
#### Matching
11. Additional resource constraints, extending the matching engine
12. No matches and report gap and potential resolutions
13. Rest buffer between missions
14. Mission priority
15. Optimize for larger orgs with lots of staff
#### Operations
16. CI / CD
17. Scalability, Observability, IaC, offline jobs, etc. 

## Ambiguity resolution
1. Different skill taxonomy per org -> Skills owned by each org with fixed proficiency scale (1-5). Skill names are unique per org: UNIQUE(org_id, name)
2. Different approval processes per org -> Initial scope will be one single director approval in code. Later extension to DB stored approval configs
3. Leads cannot approve their own missions -> One role per user with hierarchy Director > Lead, so a director can also lead missions. The mission lead can never approve their own mission. A director who is also leading a mission needs a second director to get approval. On mission creation the API and CLI flag that this mission requires an additional director for approval.
4. Who can be assinged to a mission: Only crew members can be assigned to missions. A lead is never a crew member and a director is never a crew member. The Director > Lead hierarchy does not include Crew.
5. Directors approve missions -> A mission to approve consists of requirements, timeline and date. Lead can preview the matcher in draft to check the mission can be staffed before submit. The director sees the same matcher preview in the approval view. Invites happen only after approval, so scarce skills are not reserved for unfunded missions. No separate steps for now
6. Changing after approval -> Missions can only be edited in draft. Before changing mission details after a director approved lead needs to withdraw the mission back to draft status. All INVITED / ACCEPTED assignments are then CANCELLED. Staffing changes (e.g. replacing a declined crew member) are not a change and need no new approval.
7. Availability tracking -> Instead of managing available periods it is more pragmatic to manage unavailable timeslots: holiday leave, sick leave, internal meetings, etc. Dates only. A crew member is blocked by unavailability, invited and accepted assignments.
8. Account for workload in matching -> Initially setting to booked mission days (invited + accepted) in time window (e.g. 90d) before and after the mission. Rest between missions deferred to P2
9. Crew has "limited" visibility -> Fixing to profile, own mission assignments and mission details. Enforced via RBAC in the API
10. Data must never leak across tenants -> Reads are protected by the org scoped data-access layer only. Composite foreign keys in DB protect writes / links. Error rule:
    - Resource does not exist -> 404
    - Resource exists in another org -> 404, so the response never reveals that it exists
    - Resource exists in the own org but the role has no access -> 403 with role and rule
11. Crews accept missions -> Crew members need to respond to approved missions. Only an approved mission is sent to the Crew members to ensure the whole mission is funded before reserving scarce skills for a mission. Otherwise skills might be missing for other missions currently being planned. 
12. Mission requirements -> A mission has slots: skill + minimum level. One skill per slot. One crew member fills max one slot per mission. Deleting a slot (DRAFT only) is a soft delete (archived_at), so assignment history keeps its reference. Matcher, invite and start guard ignore archived slots.
13. Staffing state -> No additional mission state (e.g. STAFFING). The assignments reflect the staffing progress
14. Crew profile change conflicts with an INVITED / ACCEPTED assignment -> API rejects and the error names the conflict:
    - Added unavailability overlaps the mission dates
    - Lowered skill level is below the slot minimum
    - Removed skill is required by the slot

## RBAC role resolution
- Directors 
    - Can do everything a lead can, on their own missions only
    - Cannot act on missions of other leads, except approve / reject
    - Can approve / reject missions (not their own)
    - Can view whole org data
    - Can edit org settings (skills)
- Leads
    - Can manage own missions (edit in draft only)
    - Can run matching on own missions and preview in draft and invite crew (approved only)
    - Can view all missions and crew of the org leave only shown as "unavailable", no reason
    - Cannot approve own missions
- Crew members
    - can view their own missions only
    - Can view mission details of their own missions
    - Can accept / decline mission assignments
    - Can view own assignment history
    - Can view and edit own profile: skills and unavailability

## Tenant isolation
- Each user is assigned to one single organization for now
- JWT only carries user_id. Org and role are loaded from DB on each request -> role changes and revocation apply immediately. The cost is one primary key lookup per request. Decided.
- Every query needs to pass a data-access layer that checks their own org and the org data they want to retrieve / change
    - Every referenced id (e.g. skill_id, crew_id) is looked up with org filter. Cross org returns no data
- Composite foreign keys as second layer for writes so DB rejects cross org links even if the data-access layer has a bug. They do not protect reads. Reads rely on the data-access layer only
    - Every tenant table has org_id, parent tables have UNIQUE(org_id, id)
    - Child tables reference (org_id, x_id) -> parent(org_id, id): assignment -> mission / user, assignment (org_id, mission_id, requirement_id) -> mission_requirement (org_id, mission_id, id) so the slot belongs to the same mission, mission_requirement -> mission / skill, crew_skill -> user / skill, unavailability -> user, mission.lead_id -> user, mission.approved_by -> user
    - Only crew can be assigned is not covered by FK -> checked in service layer
- Will ensure via cross org access checks in the happy path tests
- Postgres RLS would be the second layer for reads - Deferred to P2

## Short references
P0: API paths use UUIDs, so paths stay stable. The CLI uses UUIDs for missions and skills. Every entity in an API response contains the id and, if it has one, the short reference. Short references are enforced by a DB unique constraint.
- Users: `username`, globally unique, because `mc login --user` has no org context. Crew references in the CLI use the username
    - Follow-up: the unique constraint is case-sensitive for now, so `Ava` and `ava` can both exist. Later: a unique index on `lower(username)` and a case-insensitive lookup in `mc login` and `--crew`
- Slots: position in the mission (1, 2, 3) with partial unique index on (mission_id, position) WHERE archived_at IS NULL, so a new slot can reuse the position of an archived slot
- Slots: partial unique index on assignment (requirement_id) WHERE status IN (INVITED, ACCEPTED): one active assignment per slot
- Assignments: referenced by mission UUID. Partial unique index: one INVITED / ACCEPTED assignment per (mission_id, user_id)

P1: short references for missions and skills in the CLI
- Skills: `slug` with UNIQUE(org_id, slug). A duplicate slug is rejected with a clear error, no auto suffix
- Missions: per org code `MSN-<n>` with UNIQUE(org_id, number). Next number via `UPDATE org SET mission_seq = mission_seq + 1 ... RETURNING` in the same transaction. The row lock serializes concurrent creates, so no collisions

## Initial mission lifecycle
1. DRAFT: Mission lead creates, edits mission. Can preview the matcher. If the lead is a director, the mission is flagged as requiring an additional director for approval. The flag is derived from the lead's current role and never stored
2. APPROVAL_REQUIRED:  Mission details are finalized. Mission is sent to Director for approval. Director sees the matcher preview. Awaiting response
    - Director rejects -> back to DRAFT (no comment, P2)
    - Lead withdraws -> back to DRAFT
3. APPROVED: Mission is approved and mission lead performs staffing. Inviting the crew. Awaiting their response. 
    - Lead withdraws mission back to DRAFT to change details -> all INVITED / ACCEPTED assignments become CANCELLED, approved_by / approved_at are cleared
4. ACTIVE: Mission lead started the mission. Guard: every slot has an ACCEPTED assignment
5. COMPLETED: Mission lead completed the mission
6. CANCELLED: Cancelled by mission lead (no reason, P2). Changing to this state from any state except COMPLETED. All INVITED / ACCEPTED assignments become CANCELLED.
- Transitions stored in code for now to reduce scope (from, to) -> allowed roles. Extension point for approval workflow customization later

## Assignment lifecycle
1. INVITED: Lead invites crew member. Only when mission is APPROVED
2. ACCEPTED: Crew member accepted
3. DECLINED: Crew member declined. Slot is open again, lead reruns matching. The matcher never suggests this member for this mission again
4. CANCELLED: Mission went back to DRAFT or was cancelled. Frees the crew member's availability
- Double booking check when inviting and accepting: the service locks the crew member's user row (`SELECT ... FOR UPDATE`) and checks date overlap with INVITED / ACCEPTED assignments in the same transaction. No DB constraint, because mission dates are not on the assignment

## Staffing matching v1
- Each slot seeks to be filled by one crew member (slot = skill + min level)
- P0: Include member in selection set if: 
    - Same org
    - Skill at minimum level
    - Available during timeframe / no unavailability during timeframe
        - other mission (invited or accepted)
        - leave
    - Has not declined this mission
- P0: Rematching only fills open slots (no INVITED / ACCEPTED assignment)
- P0: Rank / boost member in selection set if:
    - Lower workload than others
    - ~~(past mission with same skills? - member should update the proficiency themself then so exclude for now)~~
    - Be mindful of experts - could be required by other mission with higher proficiency requirement -> closest fit: proficiency closest to minimum ranks higher
    - Potential term: skill scarcity - fewer other members can fill slots with this skill -> member ranks lower to keep them free
- P0: All slots are matched together for now (linear optimization?)
    - Potential lib: scipy (`linear_sum_assignment`). Evaluate in the low level step
- Other constraints (resources, rest buffer, priority) left out for now, see P2
- P1: Rank breakdown: Why is this the best person for the slot
- P1: Decision insights for lead
    - Excluded members: Why?
    - P2: No matches: Report gap and potential resolutions: e.g. 2 qualified but on leave / other mission?



## Proposed Tech stack
API + CLI. One language (Python) for API and CLI keeps the stack small
1. CLI Typer + httpx + Rich: typed commands, generated help, readable tables
    - CLI to API 
    - Stores the token locally after login
    - Table views only, no flag for scripting
2. Backend FastAPI +Pydantic + SQLAlchemy with Alembic: Typed API with generated OpenAPI docs and safe DB access with migrations
    - Matching could require additional libs for optimization problem or naive solution? to be decided in low level step
    - Typed API client: shared Pydantic package in the same repository. API and CLI import the same request / response types. No generated OpenAPI client, so no regeneration step. The shared package depends on Pydantic only, no FastAPI or SQLAlchemy
3. Database: Postgres
4. Local JWT login with seeded users
    - Token only carries user_id, org and role loaded per request -> explained abovr
5. Orchestration of services / seeding of data via local docker-compose

### MVP CLI commands v0
1. Login: mc login --user username, mc logout
2. Missions list: mc missions list
3. Mission detail: mc missions show <mission-id>
    - Edit, submit, approve or reject: mc missions create|edit|submit|withdraw|approve|reject|cancel|start|complete
    - Staff with the matcher: mc missions match <mission-id>, mc missions invite <mission-id> --slot 1 --crew username (APPROVED only)
4. My assignments (Crew): mc assignments list (current and history)
    - Accept, decline: mc assignments accept|decline <mission-id>
5. My profile (Crew): mc profile show
    - Skills: mc profile skills set <skill-id> --level n, mc profile skills remove <skill-id>
    - Availability: mc profile availability list / add --from date --to date / remove id
