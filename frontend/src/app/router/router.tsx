import React from "react";
import {
  createRouter,
  createRoute,
  createRootRoute,
  Navigate,
} from "@tanstack/react-router";
import { AppLayout } from "../../core/components/layout/AppLayout";
import { UsersPage } from "../../modules/users/pages/UsersPage";
import { StrategiesPage } from "../../modules/strategies/pages/StrategiesPage";
import { StrategyDetailPage } from "../../modules/strategies/pages/StrategyDetailPage";
import { StrategyEditorPage } from "../../modules/strategies/pages/StrategyEditorPage";
import { RulesPage } from "../../modules/strategies/pages/RulesPage";
import { MasterPage } from "../../modules/master/pages/MasterPage";

// Root Route housing AppLayout
const rootRoute = createRootRoute({
  component: AppLayout,
});

// NotFound Page Component
const NotFoundPage: React.FC = () => {
  return (
    <div className="not-found-page p-12 text-center text-muted">
      <h2 className="text-xl font-bold text-primary mb-2">404 — Route Not Found</h2>
      <p className="text-sm">The requested route does not exist in the auto-trader route tree.</p>
    </div>
  );
};

// Route Definitions
const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  component: () => <Navigate to="/strategies" replace />,
});

const settingsUsersRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/settings/users",
  component: UsersPage,
});

const usersRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/users",
  component: UsersPage,
});

const strategiesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/strategies",
  component: StrategiesPage,
});

const strategyCreateRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/strategies/create",
  component: StrategyEditorPage,
});

const strategyDetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/strategies/$id",
  component: StrategyDetailPage,
});

const strategyEditRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/strategies/$id/edit",
  component: StrategyEditorPage,
});

const rulesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/rules",
  component: () => <RulesPage showHeader={true} />,
});

const masterRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/master",
  component: MasterPage,
});

// Build route tree
const routeTree = rootRoute.addChildren([
  indexRoute,
  settingsUsersRoute,
  usersRoute,
  strategiesRoute,
  strategyCreateRoute,
  strategyDetailRoute,
  strategyEditRoute,
  rulesRoute,
  masterRoute,
]);

export const router = createRouter({
  routeTree,
  defaultNotFoundComponent: NotFoundPage,
});

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
