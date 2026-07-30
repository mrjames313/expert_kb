# Expert Knowledge Orchestration

A lightweight framework for orchestrating expert knowledge for multi-area project development with Claude Code agents. Handles the creation and application of knowledge across multiple interrelated domains working toward a common objective (the project).  Knowledge can take the form of text-based documents, code, or data - including artifacts created by agentic experts through research, experiments, or any other means.  The knowledge artifacts are organized by areas of expertise, and includes explicit mechanisms for managing shared / common knowledge across structures and exchanging information. 

A typical workflow involves interacting with one or more Claude Code agents, each of which is assigned an area of expertise that is informed by, and interacting with, the knowledge base.  Agents can be instructed to expand the knowledge base in a variety of ways; to produce plans, reports, and analyses; or to design and build SW systems - but critically the framework ensures that they consistently load, manage, and utilize expertise while executing tasks - staying grounded and consistent with the accumulated knowledge.

Typically, a project will kick off by developing relevant knowledge bases for a few areas (literature reviews to develop technical background, design and execution of experiments to collect first-hand data or resolve open questions, customer research and business analysis for commercial projects), then move to project alignment, planning, and execution.  A non-commercial project can take different forms, for example, it could consist of a collection of expert agents all collaborating on a common technical design.


## Getting started

Launch Claude Code in a fresh directory and ask it:

> Follow the setup instructions at https://github.com/mrjames313/project_kb/blob/main/SETUP.md

Claude will read [SETUP.md](SETUP.md), ask you a handful of questions (project name, what it's about, your first area, your first role), and bootstrap a customized project for you. Setup takes 5–10 minutes.

## What's here

- **[SETUP.md](SETUP.md)** — the bootstrap runbook Claude follows to create a new project.
- **[_framework/spec.md](_framework/spec.md)** — the full framework specification.
- **[_framework/adoption-guide.md](_framework/adoption-guide.md)** — how to start minimal and extend as your project grows.

## Concepts in 30 seconds

A project has **areas** — specialized knowledge domains like research, engineering, product, or business model. Each area is a folder with its own knowledge base, raw materials, code, and data, and operates with significant autonomy. Distilled findings flow up from areas to a shared **commons** through a defined promotion protocol; project direction flows down from commons to areas.

Each area defines **roles** with explicit context-loading rules. Each kb page carries **frontmatter** (type, status, relevance hints) that tells agents how to interpret and load it. Work is structured by **specs** (brief → plan → tasks → outcome) with explicit phase gates.

A small always-on foundation handles the typical case. Four togglable capabilities (`multi_area`, `por`, `task_subagents`, `formal_review`) add machinery when projects grow into needing them, managed through the `/framework` skill.

## License

MIT — see [LICENSE](LICENSE).
