# Mission Control — Senior Software Engineer Challenge

Our philosophy: We're not testing whether you can memorise syntax or generate the largest application. We're testing how you frame problems, make technical decisions, communicate an implementation direction, direct an agent, and verify what it produces.

### The Challenge

Space organisations need to plan complex missions requiring specific crew capabilities. Crew assignment is currently manual and error-prone — leads spend hours cross-referencing skill profiles, availability calendars, and existing commitments. Multiple organisations will use this platform, each with different crew sizes, skill taxonomies, and approval processes.

Mission Control is a B2B platform that helps organisations manage missions and intelligently assign crew based on skills, availability, and workload. Your task is to design and build its core.

Before implementation, produce the design document you would use to communicate the intended solution to an engineering team and guide an AI coding agent. Submit that document with your implementation and transcripts.

You have broad latitude over the product design, data model, technical architecture, and the form and structure of the design document. We're looking for a solution you'd be comfortable putting in front of a customer.

Minimum scope: A multi-tenant API with roles, a mission lifecycle and approval workflow, crew management with skill profiles, an auto-matching engine, and a CLI through which the primary workflows can be exercised.

#### What We Expect

A working system that demonstrates senior-level judgment. The design document should establish a clear and implementable technical direction without being constrained to a prescribed format. The data model should be well-considered, and the matching algorithm should show real thought about the problem space. The API and CLI workflows should feel coherent and intentional. The code should be structured for a team to work in, not just for a demo to run.

The CLI UX is an important component that would be assessed as part of the usability review.

A web interface is not required.

### What to Submit

You are required to use AI development tools (Claude Code, Cursor, Copilot, or equivalent). The design document and transcripts are first-class parts of the submission.

Your initial design document — prepared before implementation and used to guide your AI coding agent. You are welcome to brainstorm this document with AI; in this case, include the process in your transcripts

A working API and CLI — easy to run locally, with clear setup instructions and representative seed data

Source code — a GitHub repository (public or shared with us) with meaningful commit history

Full AI transcripts — every conversation with your AI coding tool during the challenge, unedited

Time expectation: 3–5 hours of focused work. We respect your time—submit what you have. Prioritise a coherent design, a working vertical slice, and evidence of verification over breadth or polish.

Tech stack: Your choice. We use TypeScript, React, Python, and GCP internally — but use whatever you're most effective with. The tools and architectural decisions you make are part of what we're evaluating.

API keys: If you need API keys for Claude, we're happy to provide them — just reach out to our friendly team.

Timeline: There is no hard deadline, but we ask that you submit within 7 days of receiving the challenge.

Questions: If anything in the brief is unclear, email us. Ambiguity in the brief is sometimes intentional — how you resolve it is part of what we're evaluating.

### The Domain

Mission Control is a multi-tenant B2B platform for space organisations. Here's the world you're building for:

Organisations are your tenants — space agencies, research labs, private companies. All data is strictly scoped to an organisation. Data must never leak across tenants.

Crew Members belong to an organisation. They have skill profiles, availability, and assignment history. How you model skills and proficiency is up to you.

Missions belong to an organisation. They have requirements, timelines, and a lifecycle that includes some form of approval before going active. How you design the lifecycle and its transitions is a design decision we're interested in.

Assignments connect crew to missions. The platform should include an auto-matching engine that intelligently suggests crew for missions based on skills, availability, and constraints. The sophistication of this algorithm is part of what we're evaluating.

#### Roles

The platform has three user roles with different levels of access:

Directors run the organisation. They manage settings, approve missions, and have broad visibility.

Mission Leads plan and manage missions. They define requirements, run the matcher, and submit missions for approval. They should not be able to approve their own missions.

Crew Members manage their own profiles, availability, and respond to assignments. They have limited visibility into the broader organisation.

### About the Design Document and AI Transcripts

The design document and transcripts are first-class evaluation artifacts — as important as the code itself. We want to understand how you translated the brief into a technical direction, how you used that direction to guide your AI tool, and how you evaluated what it produced.

We are intentionally not prescribing the structure of the design document. Its scope, organisation, level of detail, and usefulness as implementation context are part of what we're evaluating.

Don't edit the transcripts. We want to see your real process, including dead ends, changes of direction, and mistakes.

### What Happens Next

If you pass the async stage, you'll be invited to a 90-minute live session that builds on your submission. Here's what to expect:

Product and architecture deep-dive (30 min): Present your solution as if pitching it to the engineering team. Walk us through the design document, where implementation diverged from it, and the product and technical trade-offs you made. We'll challenge your decisions and ask how you used the design to guide and constrain the agent.

Novel system design (40 min): Fresh design problems, whiteboard-style. We'll ask you to extend the architecture on the fly — for example, how you'd layer in resource constraints or redesign approval workflows.

Team and process discussion (20 min): How you'd break down work, delegate, review AI-generated code, and set guardrails.

Good luck. We're excited to see how you think. ​