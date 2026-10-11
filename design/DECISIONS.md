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
    - Directors approve / reject
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
    - Rank breakdown per suggestion - defer to P1?
#### CLI
11. Primary workflows run through the CLI: login, missions list /detail, create/ edit, submit, approve / reject, matching preview and invites, my assignments and history (crew), accept / decline, my profile and availability (crew).
#### Quality
12. Tests
    - Cross org access tests for all endpoints
    - Matcher and mission lifecycle transitions
    - RBAC: no self approval, role visibility / actions
13. Evidence of verification
    - Scripted end-to-end CLI demo over the seed data (full mission lifecycle)
    - Test results documented: Readme?

### P1: Next extensions: If time permits in this session
#### Crew and skills
1. Directors manage org settings
    - Skill catalogue
#### Mission lifecyle
2. Mission audit logs
#### Matching
3. Decision insights for lead: Excluded members: Why?
...

### P2: Scoped as outside of this session
#### Auth and tenant
1. Noisy-neighbour protection / uneven org sizes in this multi tenant architecture
2. Real idp oidc, login / signup, 
3. Postgres RLS?
4. User and role management
#### Mission lifecycle
5. Approval workflow customization
6. Crew members withdraw after accepting
#### Crew and skills
7. Edit / archive skills
8. Verification of self assessed proficiency
#### Matching
9. Additional resource constraints, extending the matching engine
10. No matches and report gap and potential resolutions
11. Rest buffer between missions
12. Mission priority
13. Optimize for larger orgs with lots of staff
#### Operations
13. CI / CD
14. Scalability, Observability, IaC, offline jobs, etc. 

## Ambiguity resolution
1. Different skill taxonomy per org -> Skills owned by each org with fixed proficiency scale (1-5)
2. Different approval processes per org -> Initial scope will be one single director approval in code. Later extension to DB stored approval configs
3. Leads cannot approve their own missions -> One role per user with hierarchy Director > Lead, so a director can also lead missions. The mission lead can never approve their own mission. A director who is also leading a mission needs a second director to get approval.
4. Who can be assinged to a mission: Only crew members can be assigned to missions.
4. Directors approve missions -> A mission to approve consists of requirements, timeline and date. Lead can preview the matcher in draft to check the mission can be staffed before submit. Invites happen only after approval, so scarce skills are not reserved for unfunded missions. No separate steps for now
5. Changing after approval -> Missions can only be edited in draft. Before changing mission details after a director approved lead needs to put the mission back to draft status. Staffing changes (e.g. replacing a declined crew member) are not a change and need no new approval.
6. Availability tracking -> Instead of managing available periods it is more pragmatic to manage unavailable timeslots: holiday leave, sick leave, internal meetings, etc. Dates only. A crew member is blocked by unavailability, invited and accepted assignments.
7. Account for workload in matching -> Initially setting to booked mission days (invited + accepted) in time window (e.g. 90d) before and after the mission. Rest between missions deferred to P2
8. Crew has "limited" visibility -> Fixing to profile, own mission assignments and mission details. Enforced via RBAC in the API
9. Data must never leak across tenants -> Org enforced in data-access layer and with composite foreign keys in DB. Cross org access returns 404 dont indicate resource exists in responses for security?
10. Crews accept missions -> Crew members need to respond to approved missions. Only an approved mission is sent to the Crew members to ensure the whole mission is funded before reserving scarce skills for a mission. Otherwise skills might be missing for other missions currently being planned. 
11. Mission requirements -> A mission has slots: skill + minimum level. One skill per slot. One crew member fills max one slot per mission.

## RBAC role resolution
- Directors 
    - Can do everything a lead can
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
- JWT only carries user_id. Org and role are loaded from DB on each request -> role changes apply immediately but creates DB load. In a highly regulated space like in a space agency might be better to revoke early, but needs further discussion in low level task
- Every query needs to pass a data-access layer that checks their own org and the org data they want to retrieve / change
    - Every referenced id (e.g. skill_id, crew_id) is looked up with org filter. Cross org returns no data
- Composite foreign keys as second layer so DB rejects cross org links even if the data-access layer has a bug
    - Every tenant table has org_id, parent tables have UNIQUE(org_id, id)
    - Child tables reference (org_id, x_id) -> parent(org_id, id): assignment -> mission / user, mission_requirement -> mission / skill, crew_skill -> user / skill, unavailability -> user, mission.lead_id -> user
    - Only crew can be assigned is not covered by FK -> checked in service layer
- Will ensure via cross org acess tests - parametrized test over all endpoints?
- Potential postgres feature using RLS? Third layer? - Defer for now

## Initial mission lifecycle
1. DRAFT: Mission lead creates, edits mission. Can preview the matcher
2. APPROVAL_REQUIRED:  Mission details are finalized. Mission is sent to Director for approval. Awaiting response
    - Director rejects with comment -> back to DRAFT
    - Lead withdraws -> back to DRAFT
3. APPROVED: Mission is approved and mission lead performs staffing. Inviting the crew. Awaiting their response. 
5. ACTIVE: Mission lead started the mission
6. COMPLETED: Mission lead completed the mission
7. CANCELLED: Cancelled by mission lead with a reason. Changing to this state from any state except COMPLETED.
- Transitions stored in code for now to reduce scope (from, to) -> allowed roles. Extension point for approval workflow customization later

## Assignment lifecycle
1. INVITED: Lead invites crew member. Only when mission is APPROVED
2. ACCEPTED: Crew member accepted
3. DECLINED: Crew member declined. Slot is open again, lead reruns matching
- Double booking check when inviting and accepting - DB constraint?

## Staffing matching v1
- Each slot seeks to be filled by one crew member (slot = skill + min level)
- P0: Include member in selection set if: 
    - Same org
    - Skill at minimum level
    - Available during timeframe / no unavailability during timeframe
        - other mission (invited or accepted)
        - leave
- P0: Rank / boost member in selection set if:
    - Lower workload than others
    - ~~(past mission with same skills? - member should update the proficiency themself then so exclude for now)~~
    - Be mindful of experts - could be required by other mission with higher proficiency requirement -> closest fit: proficiency closest to minimum ranks higher
- P0: All slots are matched together for now (linear optimization?)
- P1: Rank breakdown: Why is this the best person for the slot
- P1: Decision insights for lead
    - Excluded members: Why?
    - P2: No matches: Report gap and potential resolutions: e.g. 2 qualified but on leave / other mission?



## Proposed Tech stack
API + CLI. One language (Python) for API and CLI keeps the stack small
1. CLI Typer + httpx + Rich: typed commands, generated help, readable tables
    - CLI to API 
    - Stores the token locally after login
    - Table views by default, flag for scripting?
2. Backend FastAPI +Pydantic + SQLAlchemy with Alembic: Typed OpenAPI spec for the CLI and safe DB access with migrations
    - Matching could require additional libs for optimization problem or naive solution? to be decided in low level step
    - openapi-python-client for typed API client
3. Database: Postgres
4. Local JWT login with seeded users
    - Token only carries user_id, org and role loaded per request -> explained abovr
5. Orchestration of services / seeding of data via local docker-compose

### MVP CLI commands v0
1. Login: mc login --user username, mc logout
2. Missions list: mc missions list
3. Mission detail: mc missions show id
    - Edit, submit, approve or reject: mc missions create|edit|submit|withdraw|approve|reject|cancel|start|complete
    - Staff with the matcher: mc missions match id, mc missions invite id --slot slotId --crew crewId (APPROVED only)
4. My assignments (Crew): mc assignments list (current and history)
    - Accept, decline: mc assignments accept|decline id
5. My profile (Crew): mc profile show
    - Skills: mc profile skills set skillId --level n, mc profile skills remove skillId
    - Availability: mc availability list / add --from date --to date / remove id

## Open questions / follow ups
- Additonal step required to indicate invited members? INVIATION_PENDING / STAFFING?
- To be clarified workflow v1 steps sufficient? (Staffing before vs after approval
- Crew adds unavailability that overlaps an INVITED / ACCEPTED assignment: reject, warn or auto-decline?
- Crew lowers a skill level below a slot minimum while INVITED / ACCEPTED: keep, warn or flag to lead?
- Can a Director be a mission lead at the same time? Assumed yes for now
- Double booking prevention for crew members, dive deep into DB constraints
- Fast revocation of token with instant lookup of org and role per user request or slow role change with longer lived token but less DB load
