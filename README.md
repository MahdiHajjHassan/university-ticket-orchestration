# University Multi-Agent Ticket Routing

> [!CAUTION]
> **University project.** This page describes the multi-agent system I built. Diagrams and example tickets explain its workflow; application source, deployment records and evaluation results are not published here.

## Connect a university request to the people who can resolve it

Students and staff use a ticket platform to ask for help with university services. I built a multi-agent system for a university that retrieves relevant university knowledge, analyzes the request and routes the ticket to the responsible department and person.

**My contribution:** I built the orchestrator, university knowledge agent and workflow agent, and connected their responsibilities into a coordinated ticket-routing process.

**AI approach:** multi-agent orchestration · retrieval-augmented generation (RAG) · request analysis · workflow routing

<picture>
  <source media="(prefers-color-scheme: dark) and (max-width: 520px)" srcset="assets/university-ticket-story-v3-mobile-dark.svg">
  <source media="(max-width: 520px)" srcset="assets/university-ticket-story-v3-mobile-light.svg">
  <source media="(prefers-color-scheme: dark)" srcset="assets/university-ticket-story-v3-dark.svg">
  <img src="assets/university-ticket-story-v3-light.svg" alt="Students and staff submit a university request. An orchestrator coordinates a knowledge RAG agent and a workflow agent. Retrieved university context supports request analysis, department selection and assignment to a responsible staff member." width="680">
</picture>

### What I built

| Component | Responsibility | Contribution to the ticket |
| --- | --- | --- |
| Orchestrator | Coordinate the specialist agents. | Connect retrieval, analysis and routing into one workflow. |
| University knowledge agent | Retrieve relevant university information through RAG. | Supply context about services, procedures and responsibilities. |
| Workflow agent | Analyze the request and select its destination. | Route it to the department and person responsible for handling it. |

The workflow ends with an assigned ticket. Its purpose is to connect a student's or staff member's request to the next action in the university's service process.

### Follow a request through the system

For **“I cannot access the course portal,”** the orchestrator coordinates processing, the knowledge agent retrieves portal guidance and support responsibilities, and the workflow agent routes the ticket to IT support and the person responsible for portal access.

| Request | Context used for routing | Destination |
| --- | --- | --- |
| Course portal access problem | Portal guidance and support ownership. | IT support and the responsible staff member. |
| Enrollment letter request | Student-service procedures and document responsibilities. | Student services and the document owner. |
| Staff leave question | Staff procedures and administrative responsibilities. | HR or staff administration and the responsible person. |

<details>
<summary><strong>Engineering details: orchestration, retrieval, and routing</strong></summary>

### Specialist responsibilities and handoffs

I separated knowledge retrieval from workflow routing. The knowledge agent supplies relevant university context; the workflow agent uses the request and that context to decide who should handle it. The orchestrator connects these responsibilities.

1. **Input:** a student or staff member submits a ticket.
2. **Coordination:** the orchestrator organizes request processing.
3. **Retrieval:** the knowledge agent finds relevant university information.
4. **Analysis:** the workflow agent interprets the request with that context.
5. **Assignment:** the ticket goes to the responsible department and person.

This makes the routing destination part of the application's workflow. Retrieved knowledge supports an operational decision that university staff can act on.

</details>

[Back to my portfolio](https://github.com/MahdiHajjHassan)
