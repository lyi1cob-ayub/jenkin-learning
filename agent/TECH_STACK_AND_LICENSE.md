# Technology Stack and Licenses

A simple inventory of the technologies configured in this Jenkins RCA Agent project, their purpose, declared versions, and license status.

> **Version note:** Python dependency versions below are the constraints in `requirements.txt`, not necessarily the exact installed versions. Several Docker images use floating tags such as `latest` or `lts`. Pin versions and check the license shipped with the exact artifact before a production or distribution release.

## Application and Python dependencies

| Technology | Version declared in this repository | What it is used for | License / status |
|---|---|---|---|
| Python | Not pinned | Implements the API, workflow, parser, database access, and integrations. | Open-source; Python Software Foundation License. |
| FastAPI | `>=0.110.0` | HTTP endpoints for Jenkins webhooks, feedback, and health checks. | Open source — MIT. |
| Uvicorn | `>=0.28.0` (`standard` extras) | Runs the FastAPI ASGI application. | Open source — BSD-3-Clause. |
| Pydantic | `>=2.6.0` | Validates request data, settings, and structured RCA responses. | Open source — MIT. |
| Pydantic Settings | Not explicitly listed | Loads configuration from environment variables and `.env` files. | Open source — MIT; version is not pinned/listed. |
| LangGraph | `==1.0.5` | Orchestrates the parse → classify → notify workflow. | Open source — MIT for the Python library. This does not cover separately licensed hosting or commercial products. |
| LangChain Community | `==0.4.1` | Provides community integrations used by the agent. | Open source — MIT. |
| LangChain Ollama | `>=0.2.0` | Connects LangChain components to Ollama. | Open source — MIT. |
| SQLAlchemy | `>=2.0.35,<3.0.0` | ORM and database connection layer. | Open source — MIT. |
| SQLModel | `>=0.0.16` | Defines database models using Pydantic and SQLAlchemy. | Open source — MIT. |
| mysqlclient | `>=2.2.0` | MySQL database driver. | Open source; GPL-2.0 license terms. Review its distribution/license metadata for the exact version before redistribution. |
| PyMySQL | `>=1.1.1,<2.0.0` | Pure-Python MySQL driver option. | Open source — MIT. |
| `aiofiles` | `>=24.1.0` | Asynchronous file operations while saving Jenkins logs. | Open source — Apache-2.0. |
| Loguru | `>=0.7.2` | Application logging. | Open source — MIT. |
| `prometheus-fastapi-instrumentator` | `>=7.0.0` | Adds HTTP metrics and exposes them at `/metrics`. | Open source — MIT. |
| Langfuse Python SDK | `<3.0.0` | Sends LLM tracing/observability data to Langfuse. | Open-source SDK; check the license for the exact resolved package version. |
| Requests | Not explicitly listed | Makes HTTP requests to external services/providers. | Open source — Apache-2.0; version is not pinned/listed. |
| PyYAML | Not explicitly listed | Reads the local YAML prompt configuration. | Open source — MIT; version is not pinned/listed. |
| Tenacity | Not explicitly listed | Retries selected transient provider errors. | Open source — Apache-2.0; version is not pinned/listed. |

## Services, models, and integrations

| Technology | Version/tag configured | What it is used for | License / status |
|---|---|---|---|
| Ollama | Docker tag `latest`; example model `qwen3:14b` | Runs the language model locally. | Ollama software is open source — MIT. The model has its own separate license/terms; verify the exact model version before use. |
| OpenRouter | Optional; example model `qwen/qwen-2.5-coder-32b-instruct` | Optional hosted model API when enabled. | Hosted commercial service, not an open-source software dependency. Provider and model terms apply; usage may incur fees. |
| Jenkins | Docker tag `lts` | Runs CI pipelines and sends failed-build information to the RCA API. | Open source — MIT for Jenkins core. Plugins can have different licenses. |
| Microsoft Power Automate | Configured webhook | Routes RCA notifications to collaboration tools. | Proprietary hosted service; Microsoft terms/subscription apply. |
| Microsoft Teams | No version configured | Delivers failure summaries and remediation guidance. | Proprietary service; Microsoft terms/subscription apply. |
| Email | Configured through the automation flow | Delivers notifications to developers. | Depends on the email service/provider; no specific implementation is pinned here. |

## Database, monitoring, and deployment

| Technology | Version/tag configured | What it is used for | License / status |
|---|---|---|---|
| MySQL | Docker tag `8.0` | Stores RCA analyses and developer feedback. | Open-source Community Server is GPL-2.0 with the MySQL FOSS License Exception; commercial licensing is also available. Check the exact image distribution. |
| PostgreSQL | Docker tag `16-alpine` | Stores Langfuse application data. | Open source — PostgreSQL License (permissive BSD-style license). |
| Langfuse | Docker tag `2` | Provides the prompt/trace UI and LLM observability service. | Check the license for the exact Langfuse 2 release and included features before deployment or redistribution. |
| Prometheus | Docker tag `latest` | Scrapes and stores application metrics. | Open source — Apache-2.0. |
| Grafana | Docker tag `latest` | Displays metrics dashboards. | Grafana OSS is open source — AGPL-3.0. Confirm the exact image/edition; Grafana Enterprise features have separate terms. |
| Docker Compose | Compose file format `3.8` | Starts the supporting development services together. The agent itself is currently started separately. | Compose is an open-source tool; the format version is not the Docker Compose software version. Docker Desktop may have separate licensing terms. |

## Project license

No repository-level `LICENSE` file was identified when this inventory was prepared. Therefore, this project does **not** currently declare a license for its own code. Do not assume that it is open source or grant permission to reuse, modify, or distribute it. Add a repository `LICENSE` file if you want to publish the project under a specific license.

Third-party software, Docker images, hosted services, and AI models each have separate license or service terms. This document is a practical inventory, not legal advice. Verify the license metadata and notices for the exact versions and artifacts you deploy, especially where a dependency version is only a range or a Docker tag floats.

## Version and dependency gaps

- `requirements.txt` pins only LangGraph and LangChain Community exactly; many other packages use minimum-version ranges, and some imported packages are not declared there.
- `ollama/ollama:latest`, `grafana/grafana:latest`, `prom/prometheus:latest`, and `jenkins/jenkins:lts` can resolve to different image versions over time.
- The model name in `env.example` is an example/configuration value, not a locked model artifact. Model license and use conditions must be checked separately.
- Use a lock file and pinned container image digests for reproducible installs and deployments. Keep a generated software bill of materials (SBOM) and verify licenses during releases.
