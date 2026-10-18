Formative 1: Kawa Network MVP - Delivery API, Async Risk Checks, and Performance Foundations
100 points · individual · URL submission · due end of Week 3

Purpose
This formative opens the assessment arc. You will build the first runnable slice of a production-shaped API for Kawa Network, and it is the first stage of one cumulative repository you will keep through Formative 2 and the Summative.

Scenario
Harvest starts in three weeks and Emmanuel's station at Nyaruguru is the pilot. Two things are already known about the environment you are building for:

The external risk registry is slow and often down. Checking whether a plot sits on recently cleared land takes between two and forty seconds, and the service is unavailable for hours at a time. Emmanuel cannot hold a farmer at the weighing scale while it runs.
Harvest peak is four hundred deliveries a day at one station, recorded on a phone on 2G with a queue of farmers watching.
The team wants an MVP that survives the compliance, testing, and deployment work still to come, rather than a prototype thrown away in Week 5.

Stakeholder tension
Patrick wants traceability data flowing to buyers before the shipping window closes.
Jeanne wants every farmer paid correctly, the same day they deliver.
Emmanuel wants to record a delivery in seconds on a bad connection.
There is no single correct design. You are graded on fitness, clarity, and justification.

Learning outcomes evidenced
LO1 REST API design and documentation · LO2 async and background workflow implementation · LO3 performance-minded API design through caching or pagination · LO7 technical communication and reproducible developer setup.

Required assessed artifacts
ADR.md · a runnable Django REST API increment · an updated README.md · an API schema or documentation artifact · the f1 milestone tag pushed.

Tasks
Task 1: Architecture Decision Record
Choose and justify one product-architecture decision for the MVP. Explain what it improves, what it makes harder, which stakeholder benefits most, and which non-functional requirement it helps or stresses.

Task 2: Core API slice
Implement the first runnable Kawa API slice with farmer registration, plot registration, a plot listing, delivery recording, a station-facing delivery feed, and structured validation with clear error responses.

A delivery must be able to say which plot the cherry came from, and a plot must record both the administrative sector it sits in and the washing station it delivers to. The provenance chain is the product, and Formative 2 scopes access against both of those fields.

Task 3: Async risk-check flow
When a plot is registered, queue a background risk check against the external registry. Your implementation must show non-blocking behaviour and evidence that attempts are recorded or logged.

Because the registry is unavailable for hours at a time, your ADR.md should say what happens to a plot whose check never succeeds, and whether deliveries from that plot can still be recorded. You do not have to solve it in code. You do have to have a position.

Task 4: Performance foundation
Your API must expose GET /api/price-schedule/ regardless of what else you build. Then implement one assessed performance feature:

a paginated delivery feed built for harvest-peak volume on a slow connection, or
a cached price-schedule endpoint
Document why your choice fits the case. Emmanuel and the pricing path have different problems; say whose you chose to solve first and why. If you cache the schedule, README.md must also say how the cache is invalidated when the season's prices change.

Task 5: Documentation
Update the repository so another developer can run the MVP independently: local setup, environment variables, how async work is started, and example requests for the major endpoints.

Submission checklist
Accept the assignment once: gh student accept ALU-BSE advanced-python-programming kawa (or the classroom50.orgLinks to an external site. web app). Your repository is named advanced-python-programming-kawa-<github-username>.
Work on main. When F1 is ready: git tag f1 && git push origin f1.
Submit your repository URL in Canvas.
The repo contains ADR.md, an updated README.md, the API implementation, and your schema or docs artifact.
Your implementation satisfies the F1 autograding contract (docs/autograding/F1_CONTRACT.md) in your repository. The contract is the minimum objective baseline, not the design.
Rubric
This rubric uses the ALU 0–5 mastery scale. Work that correctly applies the skill scores level 3, worth 60% of each criterion. Scores above that require work that adapts to complexity (level 4) or transfers and extends beyond the brief (level 5). The rubric shows what each level looks like before you start.

