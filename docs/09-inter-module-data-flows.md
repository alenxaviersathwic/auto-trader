# 09. Inter-Module Connections & End-to-End Data Flows

> **Document Type:** System Integration Specification  
> **Status:** Authoritative  
> **Repository:** `auto-trader`

---

## 1. Executive Summary

The strength of **Auto-Trader** lies in the deterministic coordination of its domain modules. Rather than operating in isolated silos, the platform connects macro sentiment intelligence, quantitative rule ASTs, real-time market data, broker credentials, and conversational AI co-pilots into unified execution pipelines.

This specification documents the **core end-to-end data flows** that power the platform (the five numbered below, plus the session loop in section 7b):
1. **Autonomous Market Intelligence Flow** (`research` $\longrightarrow$ `pgvector` $\longrightarrow$ `opportunities`)
2. **Real-Time Trade Opportunity Discovery Flow** (`Upstox API` $\longrightarrow$ `research` $\longrightarrow$ `strategies` $\longrightarrow$ `opportunities`)
3. **Conversational Strategy Creation Flow** (`master` $\longleftrightarrow$ `FastMCP` $\longleftrightarrow$ `strategies`)
4. **Broker Authentication & Token Renewal Lifecycle** (`users` $\longleftrightarrow$ `APScheduler` $\longleftrightarrow$ `Upstox API`)
5. **Automated Strategy Health & Quarantine Flow** (`opportunities` $\longrightarrow$ `strategies` $\longrightarrow$ `health`)

---

## 2. End-to-End System Integration Matrix

```mermaid
graph TB
    subgraph UsersModule ["Users & Broker Module"]
        Users_Vault["AES-GCM Credential Vault"]
        Users_Job["TokenRefreshJob (APScheduler)"]
        Users_Client["UpstoxService (OAuth2 & TOTP)"]
    end

    subgraph ResearchModule ["Research Engine Module"]
        Res_Fetch["RSS & SearxNG Scraper"]
        Res_NLP["Claim Extraction & Verification"]
        Res_Score["Opportunity Scoring Engine"]
        Res_DB[("research_candidates (pgvector)")]
        Res_MCP["Research FastMCP Server"]
    end

    subgraph StrategiesModule ["Strategies & Rules Module"]
        Strat_AST["Strategy & Rule AST Engine"]
        Strat_Eval["RuleEvaluator (Stateless AST Match)"]
        Strat_Health["Health Diagnostics & Quarantine"]
        Strat_MCP["Strategy FastMCP Server"]
    end

    subgraph OpportunitiesModule ["Opportunities Scanner Module"]
        Opp_Provider["UpstoxMarketDataProvider"]
        Opp_Master["OpportunityMaster Card Sessions"]
        Opp_Graph["LangGraph (underlying_graph)"]
        Opp_Memory["Vector Trade Memory (pgvector)"]
        Opp_Picks[("trade_opportunities")]
    end

    subgraph MasterModule ["AI Master Co-Pilot Module"]
        Master_Lang["LangGraph 11-Step Agent"]
        Master_Gate["ToolGateway (FastMCP Client)"]
        Master_Prop["Proposal Review & Executor"]
    end

    Users_Client -->|Live Tokens| Opp_Provider
    Users_Job -->|Refreshed Tokens| Users_Vault
    
    Res_Fetch --> Res_NLP --> Res_Score --> Res_DB
    Res_DB -->|Sentiment Clearance & Direction| Opp_Graph
    Res_DB --> Res_MCP
    
    Strat_AST --> Strat_Eval
    Strat_Eval -->|Evaluates Conditions| Opp_Graph
    Strat_AST --> Strat_MCP
    
    Opp_Provider -->|Live Quotes & Option Chain| Opp_Graph
    Opp_Graph --> Opp_Memory
    Opp_Graph --> Opp_Picks
    Opp_Picks -->|Resolution PnL| Strat_Health
    
    Master_Lang --> Master_Gate
    Master_Gate -->|Inspect Tools| Strat_MCP
    Master_Gate -->|Inspect Sentiment| Res_MCP
    Master_Lang --> Master_Prop
    Master_Prop -->|Deploys Approved Code| Strat_AST
```

---

## 3. Flow 1: Autonomous Market Intelligence Pipeline

**Purpose:** Continuously aggregates news, extracts verifiable claims, and establishes sentiment clearance so trading strategies never enter long positions on compromised underlyings.

```mermaid
sequenceDiagram
    autonumber
    participant Sched as APScheduler / User
    participant RunSvc as ResearchRunService
    participant Runner as ResearchWorkflowRunner
    participant Web as RSS Feeds & SearxNG
    participant LLM as Embedding / LLM Client
    participant DB as PostgreSQL (pgvector)

    Sched->>RunSvc: trigger_run(scope=["INDEX", "COMMODITY"])
    RunSvc->>DB: Insert ResearchRun (state="RUNNING")
    RunSvc->>Runner: run(state, session)

    Runner->>Web: 1. search_and_fetch (Moneycontrol, Livemint, Reuters)
    Web-->>Runner: Return raw HTML articles
    Runner->>Runner: 2. clean_filter_dedupe (Strip boilerplate, SimHash dedupe)
    
    Runner->>LLM: 3. embed_chunks (Generate 768-dim embeddings)
    LLM-->>Runner: Vector arrays
    
    Runner->>LLM: 4. extract_claims (Extract structured fact assertions)
    LLM-->>Runner: Structured claims [{ entity, sentiment, severity }]
    
    Runner->>Runner: 5. verify_claims (Cross-publisher corroboration)
    Runner->>Runner: 6. negative_sweep (Detect regulatory/earnings catalysts)
    Runner->>Runner: 7. classify_status (Assign CLEAR, WATCH, or BLOCKED)
    Runner->>Runner: 8. score_rank (Compute OpportunityScore & Direction)
    Runner->>LLM: 9. write_briefs (Generate thesis & blog summary)
    
    Runner->>DB: 10. persist (In-place upsert into research_candidates)
    Runner->>DB: 11. finalize (Mark ResearchRun state="COMPLETED")
```

---

## 4. Flow 2: Real-Time Trade Opportunity Discovery Pipeline

**Purpose:** Continuously scans live option chains, matches quantitative strategy rules, checks vector memory, and emits executable intraday trades.

```mermaid
sequenceDiagram
    autonumber
    participant UI as Browser (OpportunitiesPage)
    participant Ctrl as OpportunityController
    participant Svc as OpportunityRunService
    participant Graph as LangGraph (underlying_graph)
    participant Broker as Upstox API v2
    participant Res as Research Module
    participant Strat as Strategies (RuleEvaluator)
    participant Mem as MemoryService (pgvector)
    participant DB as PostgreSQL

    UI->>Ctrl: POST /opportunities/masters/{id}/iterate
    Ctrl->>Svc: iterate(master_id, session)
    Svc->>Graph: invoke(UnderlyingState)

    Note over Graph: Node 1: gather
    Graph->>Broker: Fetch live spot price & intraday OHLCV
    Graph->>Res: Check clearance status (must not be BLOCKED)
    Graph->>Mem: Query past trade memories for similar pattern
    
    Note over Graph: Node 2: make_menu
    Graph->>Broker: Fetch nearest expiry Option Chain
    Graph->>Graph: Filter strikes (ATM, ITM, OTM) & check OI/spread liquidity

    Note over Graph: Node 3: ai_select
    Graph->>Strat: Evaluate active strategy AST via RuleEvaluator
    Strat-->>Graph: Returns { entryMet: true, activeCaseKey: "1" }
    Graph->>Graph: Calculate entry, stop-loss, and target via ATR multiples

    Note over Graph: Node 4: validate
    Graph->>Graph: Deduct Indian statutory taxes & brokerages (costs.py)
    Graph->>Graph: Check RRR >= 1.5 and net profit margin >= 4.0%

    alt Valid Opportunity Found
        Graph->>DB: Insert TradeOpportunity (outcome="PENDING", isLatest=True)
        Graph->>DB: Log OpportunityIteration (result="SAVED")
        Svc-->>UI: Return updated opportunity card
    else Setup Rejected or No Liquidity
        Graph->>DB: Log OpportunityIteration (result="NO_SETUP" / "SETUP_REJECTED")
        Svc-->>UI: Return diagnostic skip reason
    end
```

---

## 5. Flow 3: Conversational Strategy Generation Pipeline

**Purpose:** Converts natural language trading ideas into mathematically validated, conflict-free quantitative strategies via the AI Master and FastMCP.

```mermaid
sequenceDiagram
    autonumber
    participant User as Trader / User
    participant Master as Master Module (LangGraph)
    participant MCP as Strategy FastMCP Server
    participant Val as DefinitionValidator & ConflictAnalyzer
    participant DB as PostgreSQL

    User->>Master: "Create a 5m Nifty strategy buying when 9 EMA crosses above 21 EMA"
    Master->>Master: 1. Ingest & Redact user input
    Master->>Master: 2. Classify intent -> CREATE_STRATEGY
    Master->>Master: 3. Extract spec (Direction=LONG, Timeframe=5m, Symbol=NIFTY)
    Master->>Master: 4. Gap check -> Identifies missing stop-loss
    Master-->>User: "What stop-loss in points or percentage do you want?"
    
    User->>Master: "25 points stop-loss, 50 points target"
    Master->>Master: 5. Build definition (Compile AST JSON)
    
    Master->>MCP: 6. Call validate_strategy(definition)
    MCP->>Val: Check against registry_items
    Val-->>MCP: Valid schema
    MCP-->>Master: Return validation pass
    
    Master->>MCP: 7. Call analyze_conflicts(definition)
    MCP->>Val: Check contradictory conditions & existing strategy similarity
    Val-->>MCP: Zero blockers found
    MCP-->>Master: Complications clear
    
    Master->>Master: 8. Back-translate AST to plain English
    Master->>Master: 9. Verify parity between user prompt and back-translation
    Master->>DB: 10. Persist draft proposal in master_proposals table
    Master-->>User: Present interactive Proposal Card with AST Diff & Approve button

    alt User Clicks Approve & Deploy
        User->>Master: POST /api/v1/master/proposals/{id}/approve
        Master->>DB: Insert new StrategyEntity & RuleEntity records
        Master->>DB: Save immutable StrategyVersionEntity snapshot
        Master-->>User: Strategy active & available for execution!
    else User Clicks Reject
        User->>Master: POST /api/v1/master/proposals/{id}/reject
        Master->>DB: Mark proposal status="REJECTED"
    end
```

---

## 6. Flow 4: Broker Authentication & Token Renewal Lifecycle

**Purpose:** Ensures uninterrupted connectivity with Upstox by renewing transient access tokens before daily market open sessions.

```mermaid
sequenceDiagram
    autonumber
    participant Trader as Trader
    participant App as Users Service
    participant Sched as APScheduler Daemon
    participant Upstox as Upstox API v2
    participant Vault as AES-GCM Vault (PostgreSQL)

    Note over Trader,Vault: Initial User Setup
    Trader->>App: Input Upstox API Key, Secret & TOTP Seed
    App->>Vault: Encrypt credentials with APP_MASTER_ENCRYPTION_KEY
    Trader->>App: Click 'Connect Broker' (OAuth2 / Zero-Touch)
    App->>Upstox: Complete authorization exchange
    Upstox-->>App: Return initial access_token
    App->>Vault: Store access_token_encrypted & token_expires_at

    Note over Sched,Vault: Recurring Background Daemon (Every 15 min)
    loop Every 15 Minutes
        Sched->>App: Execute TokenRefreshJob._run()
        App->>Vault: Query upstox_configs where token expires <= 30 min
        
        alt Token Expiring Soon (or Past 03:30 IST Cutoff)
            App->>Vault: Decrypt API Key, Secret & TOTP Seed
            App->>Upstox: Automated TOTP authentication handshake
            Upstox-->>App: Return freshly issued access_token
            App->>App: Calculate next expiry (next day 03:30 IST)
            App->>Vault: Update access_token_encrypted & touch last_token_refresh_at
            Note over App: Broker session primed for 09:00 MCX / 09:15 NSE open!
        else Token Still Valid
            Note over App: Token active. No action taken.
        end
    end
```

---

## 7. Flow 5: Automated Health Diagnostics & Quarantine Flow

**Purpose:** Automatically detects degraded strategy performance and quarantines underperforming models to prevent capital erosion.

```mermaid
sequenceDiagram
    autonumber
    participant Opp as Opportunities Module
    participant DB as PostgreSQL
    participant Health as HealthService (Strategies)
    participant Pol as HealthPolicyEntity
    participant Admin as User / Admin Dashboard

    Opp->>DB: Update TradeOpportunity (outcome="LOSS", resolvedAt=now())
    Opp->>DB: Record StrategyPerformanceSnapshot (update winRate, drawdown, consecutiveLosses)

    Note over Health: Health Evaluation Trigger
    Health->>DB: Query latest performance snapshot for strategy
    Health->>Pol: Check against active health policies

    alt Consecutive Losses >= 4 OR Max Drawdown > 15%
        Health->>DB: Insert StrategyHealthEvent (severity="CRITICAL", policy="CONSECUTIVE_LOSS_LIMIT")
        Health->>DB: Update Strategy status="QUARANTINED"
        Note over Health: Strategy quarantined!
        
        Admin->>Admin: UI shows Amber warning pill & diagnostic reason
        Opp->>Health: Next opportunity scan ignores quarantined strategy
    else Metrics within Normal Bounds
        Note over Health: Strategy healthy. Status remains ACTIVE.
    end
```

---

## 7b. Session Loop: From a Saved Opportunity to Trade Lock

**Purpose:** Turns opportunities the engine has already saved into a ranked, capital-sized table of trades to take for one trading session, pushed live to the browser. Full specification: [10. Trading Sessions Module](10-sessions-module.md).

```mermaid
sequenceDiagram
    autonumber
    participant UI as Browser (Opportunities loop)
    participant Opp as OpportunityRunService
    participant DB as PostgreSQL
    participant Run as SessionLoopRunner (1 s loop)
    participant Svc as SessionLoopService
    participant Page as Browser (Session page, SSE)

    UI->>Opp: POST /masters/{id}/iterate every ~20 s
    Opp->>DB: INSERT trade_opportunities (PENDING, is_latest)
    loop every second, per MANUAL session in its hours
        Run->>Svc: tick(session_id)
        Svc->>DB: saved_candidates (latest, PENDING, created in last 30 s)
        Svc->>Svc: filter, size by confidence, rank by expected net
        Svc->>DB: INSERT session_picks (OFFERED)
        Run-->>Page: SSE loop event, only if something visible changed
    end
    Page->>Svc: POST /sessions/{id}/picks/{pickId}/lock
    Svc->>DB: re-check hours, capital, loss budget, set LOCKED + live price
    Svc-->>Page: locked pick (popup)
    Note over DB: At 16:00 IST finished sessions picks move to session_picks_archive
```

The two loops are decoupled: the session only reads `trade_opportunities`, so it shows new trades only while the Opportunities loop is fetching.

---

## 8. Cross-Cutting Event Bus Pub/Sub Flows

In addition to direct service-to-service calls, Auto-Trader utilizes `app.core.events.event_bus` for asynchronous event broadcasting:

```mermaid
graph LR
    Publisher["Event Publisher"] -->|publish(event_type, payload)| Bus["In-Memory Async EventBus"]
    
    Bus -->|run.started| Sub1["Audit & Traffic Logger"]
    Bus -->|proposal.approved| Sub2["Strategy Versioning Snapshotter"]
    Bus -->|strategy.quarantined| Sub3["Alert Notification Handler"]
    Bus -->|opportunity.resolved| Sub4["Trade Memory Vectorizer"]
```

### Event Naming Conventions:
- `<module>.<entity>.<action>` (e.g. `strategies.strategy.quarantined`, `opportunities.trade.resolved`, `master.run.started`).
- Event handlers are asynchronous and execute concurrently via `asyncio.gather(*tasks, return_exceptions=True)`.

