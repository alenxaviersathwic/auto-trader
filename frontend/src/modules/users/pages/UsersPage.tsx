import React, { useState } from "react";
import {
  useUserSearch,
  useDefaultUser,
  useCreateUser,
  useUpdateUser,
  useDeleteUser,
  useSetDefaultUser,
  useAuthenticateUser,
  useRedirectUrl,
} from "../hooks/useUsers";
import { User, UserSearchFilter } from "../types/users.types";
import { FilterBar } from "../../../core/components/filter/FilterBar";
import { UserBanner } from "../components/UserBanner";
import { UserTable } from "../components/UserTable";
import { UserDialog } from "../components/UserDialog";
import { RedirectUrlDialog } from "../components/RedirectUrlDialog";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { UserEmptyState } from "../components/UserEmptyState";
import {
  UserPlus,
  Users,
  CheckCircle2,
  AlertCircle,
  X,
} from "lucide-react";

export const UsersPage: React.FC = () => {
  // Filter state for POST /users/search
  const [filterState, setFilterState] = useState<UserSearchFilter>({
    page: 0,
    limit: 10,
    status: "ACTIVE",
    sortBy: "createdAt",
    sortDir: "desc",
    query: "",
    authStatus: "",
  });

  // Toast notification state
  const [toast, setToast] = useState<{
    type: "success" | "error";
    message: string;
  } | null>(null);

  const showToast = (type: "success" | "error", message: string) => {
    setToast({ type, message });
    setTimeout(() => {
      setToast(null);
    }, 4500);
  };

  // Queries
  const {
    data: pagedData,
    isLoading: isSearchLoading,
    refetch: refetchSearch,
  } = useUserSearch(filterState);

  const {
    data: defaultUser,
    isLoading: isDefaultLoading,
    refetch: refetchDefault,
    isFetching: isDefaultFetching,
  } = useDefaultUser();

  // Mutations
  const createUserMutation = useCreateUser();
  const updateUserMutation = useUpdateUser();
  const deleteUserMutation = useDeleteUser();
  const setDefaultUserMutation = useSetDefaultUser();
  const authenticateUserMutation = useAuthenticateUser();

  // Dialog & Modal states
  const [isUserDialogOpen, setIsUserDialogOpen] = useState(false);
  const [userToEdit, setUserToEdit] = useState<User | null>(null);

  const [redirectDialogUser, setRedirectDialogUser] = useState<User | null>(null);
  const { data: redirectUrlData } = useRedirectUrl(
    redirectDialogUser?.id || 0,
    !!redirectDialogUser
  );

  const [confirmDefaultUser, setConfirmDefaultUser] = useState<User | null>(null);
  const [confirmDeleteUser, setConfirmDeleteUser] = useState<User | null>(null);

  const [authenticatingUserId, setAuthenticatingUserId] = useState<number | null>(
    null
  );

  // Filter change handler (resets page to 0 per standard)
  const handleFilterChange = (updated: any) => {
    setFilterState({
      ...filterState,
      ...updated,
      page: 0, // Reset page to 0 on any filter change
    });
  };

  // Pagination handlers
  const handlePageChange = (newPage: number) => {
    setFilterState((prev) => ({ ...prev, page: newPage }));
  };

  const handlePageSizeChange = (newSize: number) => {
    setFilterState((prev) => ({ ...prev, limit: newSize, page: 0 }));
  };

  // Actions
  const handleOpenAddUser = () => {
    setUserToEdit(null);
    setIsUserDialogOpen(true);
  };

  const handleOpenEditUser = (user: User) => {
    setUserToEdit(user);
    setIsUserDialogOpen(true);
  };

  const handleOpenRedirectUrl = (user: User) => {
    setRedirectDialogUser(user);
  };

  const handleAutoAuth = async (user: User) => {
    setAuthenticatingUserId(user.id);
    try {
      const res = await authenticateUserMutation.mutateAsync(user.id);
      if (res.upstox?.authStatus === "VALID") {
        showToast("success", `Auto-auth succeeded for ${user.name}! Token is valid.`);
      } else {
        showToast(
          "error",
          `Auto-auth failed for ${user.name}: ${res.upstox?.lastError || "Unknown error"}`
        );
      }
    } catch (err: any) {
      showToast("error", err?.message || "Failed to execute auto-auth");
    } finally {
      setAuthenticatingUserId(null);
    }
  };

  const handleConfirmMakeDefault = async () => {
    if (!confirmDefaultUser) return;
    try {
      await setDefaultUserMutation.mutateAsync(confirmDefaultUser.id);
      showToast(
        "success",
        `User '${confirmDefaultUser.name}' is now the default trading account!`
      );
      setConfirmDefaultUser(null);
    } catch (err: any) {
      showToast("error", err?.message || "Failed to set default account");
    }
  };

  const handleConfirmDelete = async () => {
    if (!confirmDeleteUser) return;
    try {
      await deleteUserMutation.mutateAsync(confirmDeleteUser.id);
      showToast("success", `User '${confirmDeleteUser.name}' has been deleted.`);
      setConfirmDeleteUser(null);
    } catch (err: any) {
      showToast("error", err?.message || "Failed to delete user");
    }
  };

  const isTotalZero = !isSearchLoading && pagedData?.totalItems === 0 && !filterState.query && !filterState.authStatus;

  return (
    <div className="page-container">
      {/* Toast Notification */}
      {toast && (
        <div className={`toast-notification toast-${toast.type}`}>
          {toast.type === "success" ? (
            <CheckCircle2 size={16} />
          ) : (
            <AlertCircle size={16} />
          )}
          <span>{toast.message}</span>
          <button
            type="button"
            className="toast-close"
            onClick={() => setToast(null)}
          >
            <X size={14} />
          </button>
        </div>
      )}

      {/* Page Header */}
      <div className="page-header">
        <div className="header-title-wrap">
          <div className="header-icon-box">
            <Users size={22} className="text-emerald" />
          </div>
          <div>
            <h1 className="header-title">Settings &bull; Users &amp; Upstox Accounts</h1>
            <p className="header-desc">
              Manage multi-account Upstox credentials, automated TOTP daily authentication, and primary market data feeds.
            </p>
          </div>
        </div>

        <div className="page-actions">
          <button
            type="button"
            className="btn btn--primary"
            onClick={handleOpenAddUser}
          >
            <UserPlus size={16} />
            <span>+ Add User</span>
          </button>
        </div>
      </div>

      {/* Default User State Banner */}
      <UserBanner
        defaultUser={defaultUser}
        isLoading={isDefaultLoading}
        onRefresh={() => {
          refetchDefault();
          refetchSearch();
        }}
        isRefreshing={isDefaultFetching}
      />

      {/* Main Content: FilterBar + Table or Empty State */}
      {isTotalZero ? (
        <UserEmptyState onAddUser={handleOpenAddUser} />
      ) : (
        <div className="card card--flat">
          {/* Universal FilterBar with extra authStatus filter */}
          <div className="users-filter-row">
            <div className="filter-bar-flex">
              <FilterBar
                filter={filterState}
                onFilterChange={handleFilterChange}
                searchPlaceholder="Search by name, Upstox ID, or profile name..."
              />
            </div>

            {/* Additional Filter: Auth Status */}
            <div className="filter-item auth-filter-item">
              <span className="filter-label">Auth:</span>
              <select
                className="select"
                value={filterState.authStatus || ""}
                onChange={(e) =>
                  handleFilterChange({
                    authStatus: (e.target.value as any) || undefined,
                  })
                }
              >
                <option value="">All Statuses</option>
                <option value="VALID">Valid</option>
                <option value="EXPIRED">Expired</option>
                <option value="AUTH_FAILED">Auth Failed</option>
                <option value="NEVER">Never</option>
              </select>
            </div>
          </div>

          {/* User Table */}
          <UserTable
            pageResult={pagedData}
            isLoading={isSearchLoading}
            pageIndex={filterState.page}
            pageSize={filterState.limit}
            onPageChange={handlePageChange}
            onPageSizeChange={handlePageSizeChange}
            onMakeDefault={(user) => setConfirmDefaultUser(user)}
            onEdit={handleOpenEditUser}
            onDelete={(user) => setConfirmDeleteUser(user)}
            onAutoAuth={handleAutoAuth}
            onShowRedirectUrl={handleOpenRedirectUrl}
            authenticatingUserId={authenticatingUserId}
          />
        </div>
      )}

      {/* Add / Edit User Dialog */}
      <UserDialog
        isOpen={isUserDialogOpen}
        userToEdit={userToEdit}
        onClose={() => setIsUserDialogOpen(false)}
        onCreate={(payload) => createUserMutation.mutateAsync(payload)}
        onUpdate={(id, payload) =>
          updateUserMutation.mutateAsync({ id, payload })
        }
      />

      {/* View Redirect URL Dialog */}
      <RedirectUrlDialog
        isOpen={!!redirectDialogUser}
        redirectUri={
          redirectUrlData?.redirectUri ||
          redirectDialogUser?.upstox?.redirectUri ||
          ""
        }
        userName={redirectDialogUser?.name}
        onClose={() => setRedirectDialogUser(null)}
      />

      {/* Confirm Make Default Modal */}
      <ConfirmDialog
        isOpen={!!confirmDefaultUser}
        title="Make Primary Default User?"
        message={`Are you sure you want to designate "${confirmDefaultUser?.name}" as the primary default account? Real-time market data quotes and algorithmic order executions will switch to this account.`}
        confirmLabel="Make Default"
        isLoading={setDefaultUserMutation.isPending}
        onConfirm={handleConfirmMakeDefault}
        onCancel={() => setConfirmDefaultUser(null)}
      />

      {/* Confirm Delete Modal */}
      <ConfirmDialog
        isOpen={!!confirmDeleteUser}
        title="Delete User Account?"
        message={`Are you sure you want to delete user "${confirmDeleteUser?.name}"? The user account and associated Upstox credentials will be soft-deleted.`}
        confirmLabel="Delete User"
        isDestructive={true}
        isLoading={deleteUserMutation.isPending}
        onConfirm={handleConfirmDelete}
        onCancel={() => setConfirmDeleteUser(null)}
      />
    </div>
  );
};
