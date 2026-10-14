import React, { useState } from "react";
import {
  createRouter,
  createRoute,
  createRootRoute,
} from "@tanstack/react-router";
import { AppLayout } from "../../core/components/layout/AppLayout";
import { FilterBar } from "../../core/components/filter/FilterBar";
import { BaseFilter } from "../../core/types/filter.types";
import {
  Cpu,
  Database,
  Lock,
  Layers,
  Sparkles,
  Terminal,
  CheckCircle2,
} from "lucide-react";

// Root Route housing AppLayout
const rootRoute = createRootRoute({
  component: AppLayout,
});

// Overview Page Component showcasing core architectural foundation
const OverviewPage: React.FC = () => {
  const [filterState, setFilterState] = useState<BaseFilter>({
    page: 0,
    limit: 10,
    status: "ACTIVE",
    sortBy: "createdAt",
    sortDir: "desc",
    query: "",
  });

  return (
    <div className="overview-page">
      <div className="page-header">
        <div className="header-title-group">
          <h1 className="page-title">Architecture & System Overview</h1>
          <p className="page-description">
            Locked single-process engine running FastAPI with 1 uvicorn worker,
            PostgreSQL with pgvector, TanStack frontend suite, and strict architectural standards.
          </p>
        </div>
      </div>

      {/* Grid of Core Architectural Pillars */}
      <div className="grid-pillars">
        <div className="pillar-card">
          <div className="pillar-header">
            <div className="pillar-icon bg-emerald">
              <Cpu size={20} />
            </div>
            <span className="pillar-tag">RUNTIME</span>
          </div>
          <h3 className="pillar-title">Single Uvicorn Worker</h3>
          <p className="pillar-text">
            All schedulers (APScheduler in <code>Asia/Kolkata</code>), event bus, and
            in-memory state live in exactly one process. No distributed locks or race conditions.
          </p>
          <div className="pillar-footer">
            <CheckCircle2 size={15} className="text-emerald" />
            <span>Lifespan managed in <code>app/main.py</code></span>
          </div>
        </div>

        <div className="pillar-card">
          <div className="pillar-header">
            <div className="pillar-icon bg-cyan">
              <Database size={20} />
            </div>
            <span className="pillar-tag">DATA LAYER</span>
          </div>
          <h3 className="pillar-title">PostgreSQL + pgvector</h3>
          <p className="pillar-text">
            Async SQLAlchemy 2 with Alembic. All entities inherit <code>BaseEntity</code> (id,
            created_at, status). Soft delete everywhere with partial unique indexes.
          </p>
          <div className="pillar-footer">
            <CheckCircle2 size={15} className="text-cyan" />
            <span>StatusType (1/0 &lt;-&gt; ACTIVE/DELETED)</span>
          </div>
        </div>

        <div className="pillar-card">
          <div className="pillar-header">
            <div className="pillar-icon bg-violet">
              <Layers size={20} />
            </div>
            <span className="pillar-tag">API CONTRACT</span>
          </div>
          <h3 className="pillar-title">Universal Envelope & Search</h3>
          <p className="pillar-text">
            Uniform <code>ApiResponse[T]</code> envelope on all endpoints. All listing endpoints
            use <code>POST /search</code> extending <code>BaseFilter</code> with central <code>FilterBuilder</code>.
          </p>
          <div className="pillar-footer">
            <CheckCircle2 size={15} className="text-violet" />
            <span>Zero-based paging & DateFilter</span>
          </div>
        </div>

        <div className="pillar-card">
          <div className="pillar-header">
            <div className="pillar-icon bg-amber">
              <Lock size={20} />
            </div>
            <span className="pillar-tag">SECURITY</span>
          </div>
          <h3 className="pillar-title">AES-GCM Secret Cipher</h3>
          <p className="pillar-text">
            Zero plain-text credentials in logs or DB. Master key from environment,
            never DB. Secrets encrypted with authenticated AES-GCM.
          </p>
          <div className="pillar-footer">
            <CheckCircle2 size={15} className="text-amber" />
            <span><code>core/crypto/secret_cipher.py</code></span>
          </div>
        </div>
      </div>

      {/* Interactive Core Building Block: FilterBar Demo */}
      <section className="demo-section">
        <div className="section-header">
          <div className="section-title-wrap">
            <Terminal size={18} className="text-emerald" />
            <h2>Universal FilterBar Component</h2>
          </div>
          <span className="badge-demo">Interactive Testbed</span>
        </div>
        <p className="section-desc">
          This reusable component standardizes text search (debounced), entity status selection,
          and createdAt range filtering across all future feature listing screens.
        </p>

        <div className="demo-card">
          <FilterBar
            filter={filterState}
            onFilterChange={(updated) => setFilterState(updated)}
            searchPlaceholder="Test keyword debounce..."
          />

          <div className="demo-state-output">
            <div className="state-header">
              <Sparkles size={14} />
              <span>Current BaseFilter State (sent to POST /search)</span>
            </div>
            <pre className="state-code">
              {JSON.stringify(filterState, null, 2)}
            </pre>
          </div>
        </div>
      </section>
    </div>
  );
};

// NotFound Page Component
const NotFoundPage: React.FC = () => {
  return (
    <div className="not-found-page">
      <h2>404 — Route Not Found</h2>
      <p>The requested route does not exist in the auto-trader route tree.</p>
    </div>
  );
};

// Route Definitions
const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  component: OverviewPage,
});

// Build route tree
const routeTree = rootRoute.addChildren([indexRoute]);

export const router = createRouter({
  routeTree,
  defaultNotFoundComponent: NotFoundPage,
});

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
