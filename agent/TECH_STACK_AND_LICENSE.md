# Technology Stack and License

This document describes the technologies present in the Jenkins RCA Agent repository and why they are used. It reflects the repository configuration inspected for this project; some versions and model choices are configurable and may differ between the code defaults and `env.example`.

## Application stack

| Technology | Where it is used | Why it is used |
|---|---|---|
| Python | Agent application | Implements the API, log processing, workflow, database access, and integrations. |
| FastAPI | `main.py`, API routes | Provides the HTTP API for Jenkins webhooks, feedback, and health checks, with typed request handling. |
| Uvicorn | API startup | Runs the FastAPI ASGI application. |
| Pydantic / Pydantic Settings | Models and configuration | Validates structured RCA data and loads application settings from environment variables and `.env`. |
| LangGraph | `app/graph/` | Orchestrates the parse → classify → notify workflow and passes shared state between its steps. |
| LangChain Community and LangChain Ollama | Requirements and LLM/tool integration | Supplies LangChain integrations used by the agent, including the Ollama connection/tool ecosystem. |
| SQLAlchemy and SQLModel | Database layer | Defines and accesses database records through Python ORM abstractions. |
| MySQL 8.0 | Compose database service | Stores RCA analyses and developer feedback. The app connects through MySQL drivers. |
| PyMySQL and mysqlclient | Database drivers | Provide MySQL connectivity for SQLAlchemy. |
| `aiofiles` | Log ingestion | Supports asynchronous file operations while saving downloaded Jenkins logs. |
| Loguru | Application logging | Provides application-level logs for workflow stages and integrations. |
| Requests | LLM and HTTP integrations | Sends HTTP requests to configured LLM providers and external services. |
| PyYAML | Prompt configuration | Reads the local YAML prompt registry. |
| Tenacity | OpenRouter client | Retries selected transient provider errors with backoff. |

## AI and workflow services

| Technology | Configured use | Why it is used |
|---|---|---|
| Ollama | Local inference; example model `qwen3:14b` in `env.example` | Runs a model locally, allowing the project to use a private/local inference path. The model name is configurable; code defaults may differ from the example environment file. |
| OpenRouter | Optional external inference; example model `qwen/qwen-2.5-coder-32b-instruct` | Provides an optional hosted model route and fallback flexibility when enabled. It is disabled by default in `env.example`. |
| Local YAML prompts | `app/prompts/prompts.yaml` | Keeps prompt text and versions configurable outside the workflow code. |
| Langfuse | Langfuse 2 Compose service and Python integration | Provides LLM prompt management and tracing/observability for analysis and generation. |

The repository also uses `RCAOutput` validation to ensure model responses match the expected structured fields before they are persisted or sent to notification integrations.

## CI/CD, API integrations, and notifications

| Technology | Where it is used | Why it is used |
|---|---|---|
| Jenkins | Jenkins LTS service, `agent/Jenkinsfile` | Runs build pipelines and triggers the RCA webhook when a build fails. The current pipeline includes an infrastructure-failure simulation. |
| Jenkins console log endpoint | Webhook flow | Supplies the build log that the agent parses for likely failure evidence. |
| Microsoft Power Automate | Configured webhook integration | Receives a flat RCA payload and can route notifications through an existing automation flow. |
| Microsoft Teams and email | Downstream notification destinations | Delivers failure summaries and remediation guidance to developers. These are reached through the Power Automate integration. |

## Monitoring, deployment, and persistence

| Technology | Where it is used | Why it is used |
|---|---|---|
| Docker Compose | `agent/docker-compose.yaml` | Starts the supporting development services together. The FastAPI agent is currently run separately rather than defined as a Compose service. |
| Prometheus | Metrics service and `prometheus.yml` | Scrapes the agent's `/metrics` endpoint for operational metrics. |
| `prometheus-fastapi-instrumentator` | FastAPI application | Instruments API requests and exposes Prometheus-format metrics. |
| Grafana | Compose service | Provides dashboards for metrics collected by Prometheus. |
| PostgreSQL 16 | `langfuse_db` Compose service | Stores Langfuse's own application data; it is separate from the MySQL database used by the RCA agent. |
| Environment variables / `.env` | `app/config.py`, `env.example` | Keeps connection details, model selection, credentials, and limits configurable rather than hard-coding normal deployment configuration. Do not commit real secrets. |

## High-level flow

1. Jenkins posts failed-build metadata and a console-log URL to the FastAPI service.
2. The agent downloads and stores the log, then schedules the LangGraph workflow.
3. The parser extracts bounded error context; the configured LLM produces a structured RCA.
4. The result and any developer feedback are stored in MySQL.
5. A notification payload is sent to Power Automate for Teams/email delivery.
6. Prometheus scrapes API metrics; Langfuse records LLM traces when configured.

## License status

**No repository-level `LICENSE` file was present in the repository tree inspected for this document. The project therefore does not currently declare an open-source license.** Do not assume that the repository is MIT, Apache-2.0, or otherwise freely reusable. Choose a license that matches the owner's intent and add the appropriate `LICENSE` file before distributing the project under an open-source license. If no license is granted, normal copyright restrictions apply; this is not legal advice.

This repository's files do not establish the licenses for its third-party packages, Docker images, Jenkins, LLM models, or hosted services. Their terms are separate and may vary by version, model, and provider. Review upstream license notices and service/model terms before redistribution or production use. The project currently does not include a generated third-party license inventory or SBOM.

## Dependency inventory note

`agent/requirements.txt` lists the main Python dependencies, but code also imports packages such as `requests`, `PyYAML` (`yaml`), `tenacity`, and `pydantic-settings` that are not explicitly listed there in the inspected version. They may currently arrive transitively in a particular environment, but should be declared directly and pinned/locked as appropriate to make installations reproducible and license review complete.

## Configuration and version caveat

Versions and model names are not uniformly pinned across the stack: for example, the Compose file uses tags such as `latest`, and the Ollama model shown in `env.example` differs from the code default. Record the deployed image digests, package lock versions, and model/provider versions for a reproducible release and a reliable license/security inventory.
