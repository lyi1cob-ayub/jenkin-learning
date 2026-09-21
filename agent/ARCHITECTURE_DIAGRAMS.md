# Jenkins RCA Agent — Architecture Diagrams

This file contains presentation-ready diagrams for the Jenkins RCA Agent. The diagrams are intentionally kept in Mermaid so they can be rendered by GitHub, Mermaid Live, documentation portals, or architecture tooling that supports Mermaid.

## 1. System context

```mermaid
flowchart LR
    Dev[Developer / Build Owner]
    J[Jenkins]
    A[RCA Agent]
    LLM[Ollama or OpenRouter]
    DB[(MySQL)]
    PA[Power Automate]
    Teams[Microsoft Teams / Email]
    Obs[Prometheus / Grafana / Langfuse]
    J -->|failed build webhook| A
    A -->|retrieve console log| J
    A -->|RCA request| LLM
    A -->|analysis and feedback| DB
    A -->|structured notification| PA
    PA --> Teams
    Teams -->|feedback| A
    A --> Obs
    Dev --> Teams
```

## 2. Container architecture

```mermaid
flowchart TB
    subgraph CI[CI environment]
        Jenkins[Jenkins controller/worker]
    end
    subgraph Agent[Agent runtime]
        API[FastAPI application]
        Graph[LangGraph workflow]
        Parser[Streaming log parser]
        Client[LLM client]
        Notify[Notification adapter]
    end
    subgraph Platform[Supporting platform services]
        Ollama[Ollama]
        OpenRouter[OpenRouter]
        MySQL[(MySQL)]
        Prom[Prometheus]
        Grafana[Grafana]
        Langfuse[Langfuse]
        PG[(Langfuse PostgreSQL)]
    end
    subgraph Enterprise[Enterprise collaboration]
        PA[Power Automate]
        Teams[Teams and email]
    end
    Jenkins --> API
    API --> Graph
    Graph --> Parser
    Graph --> Client
    Graph --> Notify
    Client --> Ollama
    Client -. optional .-> OpenRouter
    Client --> Langfuse
    Graph --> MySQL
    Notify --> PA
    PA --> Teams
    API --> Prom
    Prom --> Grafana
    Langfuse --> PG
```

## 3. Data flow

```mermaid
sequenceDiagram
    participant J as Jenkins
    participant API as FastAPI
    participant FS as Raw log storage
    participant G as LangGraph
    participant P as Parser
    participant M as LLM
    participant DB as MySQL
    participant PA as Power Automate
    J->>API: Failure metadata + log URL
    API->>J: GET consoleText
    J-->>API: Chunked log response
    API->>FS: Persist raw log
    API-->>J: 202 Accepted
    API->>G: Initial AgentState
    G->>P: Extract bounded context
    P-->>G: Sanitized snippets
    G->>M: Structured RCA request
    M-->>G: RCAOutput
    G->>DB: Save analysis
    G->>PA: Flat notification payload
```

## 4. Failure and fallback paths

```mermaid
flowchart TD
    Start[Analysis request] --> Fetch{Can Jenkins log be fetched?}
    Fetch -->|no| Reject[Return HTTP error; log failure]
    Fetch -->|yes| Parse{Known errors found?}
    Parse -->|no| Tail[Use bounded tail fallback]
    Parse -->|yes| Context[Use prioritized context]
    Tail --> Model[Call selected LLM]
    Context --> Model
    Model --> Provider{Provider available?}
    Provider -->|OpenRouter enabled| OR[OpenRouter with retries]
    Provider -->|local/default| O[Ollama]
    OR -->|failed| O
    O --> Validate{Valid RCA JSON?}
    Validate -->|no| Unknown[Unknown fallback schema, confidence 0]
    Validate -->|yes| RCA[Persist RCA and notify]
    Unknown --> RCA
    RCA --> Notify{Notification succeeds?}
    Notify -->|yes| Done[DISPATCHED]
    Notify -->|no| Failed[FAILED; alert/retry required]
```

## 5. Trust boundaries

```mermaid
flowchart LR
    subgraph Untrusted[External/untrusted inputs]
        Webhook[Jenkins webhook fields]
        URL[Caller-provided log_url]
        Log[Jenkins log content]
        Feedback[User feedback]
    end
    subgraph Trusted[Agent trust boundary]
        Validate[Pydantic validation]
        Allowlist[Host/scheme allowlist - required hardening]
        Redact[Log redaction - required hardening]
        Workflow[Workflow and persistence]
    end
    subgraph External[External destinations]
        Provider[External LLM provider]
        Teams[Power Automate / Teams]
    end
    Webhook --> Validate
    URL --> Allowlist
    Log --> Redact
    Feedback --> Validate
    Validate --> Workflow
    Allowlist --> Workflow
    Redact --> Workflow
    Workflow --> Provider
    Workflow --> Teams
```

## 6. Target production architecture

```mermaid
flowchart TB
    J[Jenkins] --> GW[Authenticated API gateway]
    GW --> API[Stateless FastAPI ingress]
    API --> Q[(Durable queue)]
    Q --> W[Scalable RCA workers]
    W --> OBJ[(Encrypted object storage with TTL)]
    W --> PARSE[Bounded parser]
    PARSE --> MODEL[Model gateway / approved providers]
    MODEL --> RCA[(Analysis store)]
    RCA --> NOTIFY[Retryable notification service]
    NOTIFY --> PA[Power Automate]
    PA --> T[Teams / email]
    T --> FB[Feedback API]
    FB --> RCA
    W --> MET[Metrics and traces]
    MET --> MON[Prometheus / Grafana / Langfuse]
    SEC[Secret manager + policy enforcement] -.-> GW
    SEC -.-> W
    SEC -.-> MODEL
```

## Diagram usage notes

- Use diagrams 1 and 2 for architecture review.
- Use diagram 3 for implementation and onboarding.
- Use diagram 4 for resilience and incident reviews.
- Use diagram 5 for security threat modeling.
- Use diagram 6 as the recommended target-state roadmap, not as a claim about the current deployment.
