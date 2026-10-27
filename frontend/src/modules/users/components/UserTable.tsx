import React, { useMemo, useState } from "react";
import {
  useReactTable,
  getCoreRowModel,
  flexRender,
  ColumnDef,
} from "@tanstack/react-table";
import {
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Clock,
  Star,
  Play,
  ExternalLink,
  Edit2,
  Trash2,
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
  RefreshCw,
  AlertCircle,
  Copy,
  Check,
} from "lucide-react";
import { User } from "../types/users.types";
import { PageResult } from "../../../core/types/pagination.types";
import { copyToClipboard } from "../../../core/utils/clipboard";

interface UserTableProps {
  pageResult: PageResult<User> | undefined;
  isLoading: boolean;
  pageIndex: number;
  pageSize: number;
  onPageChange: (newPage: number) => void;
  onPageSizeChange: (newSize: number) => void;
  onMakeDefault: (user: User) => void;
  onEdit: (user: User) => void;
  onDelete: (user: User) => void;
  onAutoAuth: (user: User) => void;
  onShowRedirectUrl: (user: User) => void;
  authenticatingUserId: number | null;
}

export const UserTable: React.FC<UserTableProps> = ({
  pageResult,
  isLoading,
  pageIndex,
  pageSize,
  onPageChange,
  onPageSizeChange,
  onMakeDefault,
  onEdit,
  onDelete,
  onAutoAuth,
  onShowRedirectUrl,
  authenticatingUserId,
}) => {
  const [copiedId, setCopiedId] = useState<number | null>(null);

  const users = useMemo(() => pageResult?.list || [], [pageResult]);
  const totalItems = pageResult?.totalItems || 0;
  const totalPages = pageResult?.totalPages || 0;

  const formatDate = (iso: string | null | undefined) => {
    if (!iso) return "—";
    try {
      const d = new Date(iso);
      return d.toLocaleString("en-IN", {
        timeZone: "Asia/Kolkata",
        dateStyle: "medium",
        timeStyle: "short",
      });
    } catch {
      return iso;
    }
  };

  const handleCopyId = async (id: number, text: string) => {
    const ok = await copyToClipboard(text);
    if (ok) {
      setCopiedId(id);
      setTimeout(() => setCopiedId(null), 1800);
    }
  };

  const columns = useMemo<ColumnDef<User>[]>(
    () => [
      {
        accessorKey: "name",
        header: "User / Account",
        cell: ({ row }) => {
          const user = row.original;
          const upstox = user.upstox;
          const isIdCopied = copiedId === user.id;

          return (
            <div className="table-user-cell">
              <div className="user-name-title">{user.name}</div>
              <div className="user-sub-details">
                {upstox?.upstoxUserId && (
                  <button
                    type="button"
                    className={`user-sub-tag-btn ${isIdCopied ? "tag-copied" : ""}`}
                    onClick={() => handleCopyId(user.id, upstox.upstoxUserId!)}
                    title="Click to copy Upstox User ID"
                  >
                    {isIdCopied ? (
                      <>
                        <Check size={10} />
                        <span>Copied</span>
                      </>
                    ) : (
                      <>
                        <Copy size={10} />
                        <span>ID: {upstox.upstoxUserId}</span>
                      </>
                    )}
                  </button>
                )}
                {upstox?.profileName && (
                  <span className="user-sub-text">{upstox.profileName}</span>
                )}
                {upstox?.mobile && (
                  <span className="user-sub-phone">M: {upstox.mobile}</span>
                )}
              </div>
            </div>
          );
        },
      },
      {
        id: "authStatus",
        header: "Token Status",
        cell: ({ row }) => {
          const authStatus = row.original.upstox?.authStatus || "NEVER";
          switch (authStatus) {
            case "VALID":
              return (
                <span className="badge badge--green">
                  <CheckCircle2 size={12} />
                  <span>Valid</span>
                </span>
              );
            case "EXPIRED":
              return (
                <span className="badge badge--amber">
                  <AlertTriangle size={12} />
                  <span>Expired</span>
                </span>
              );
            case "AUTH_FAILED":
              return (
                <span className="badge badge--red">
                  <XCircle size={12} />
                  <span>Auth Failed</span>
                </span>
              );
            default:
              return (
                <span className="badge badge--slate">
                  <Clock size={12} />
                  <span>Never</span>
                </span>
              );
          }
        },
      },
      {
        id: "tokenExpiresAt",
        header: "Token Expiry & Status",
        cell: ({ row }) => {
          const upstox = row.original.upstox;
          const expires = upstox?.tokenExpiresAt;
          const error = upstox?.lastError;
          const lastAuth = upstox?.lastAuthAt;

          return (
            <div className="token-expiry-cell">
              <span className="expiry-date">{formatDate(expires)}</span>
              {error ? (
                <span className="meta-err-text" title={error}>
                  <AlertCircle size={12} />
                  <span>{error.length > 35 ? error.slice(0, 35) + "..." : error}</span>
                </span>
              ) : lastAuth ? (
                <span className="meta-sub-text">Refreshed: {formatDate(lastAuth)}</span>
              ) : null}
            </div>
          );
        },
      },
      {
        accessorKey: "isDefault",
        header: "Default",
        cell: ({ row }) => {
          const user = row.original;
          if (user.isDefault) {
            return (
              <span className="badge-default">
                <Star size={12} className="star-icon" />
                <span>Default</span>
              </span>
            );
          }
          return (
            <button
              type="button"
              className="btn btn--ghost btn--sm"
              onClick={() => onMakeDefault(user)}
              title="Set as primary market data account"
            >
              Make default
            </button>
          );
        },
      },
      {
        id: "actions",
        header: "Actions",
        cell: ({ row }) => {
          const user = row.original;
          const isAuthenticating = authenticatingUserId === user.id;
          // Delete blocked for default user while others exist
          const isDeleteDisabled = user.isDefault && totalItems > 1;

          return (
            <div className="table-actions-cell">
              <button
                type="button"
                className="btn btn--icon btn-auth"
                onClick={() => onAutoAuth(user)}
                disabled={isAuthenticating}
                title="Run Auto Auth now"
              >
                {isAuthenticating ? (
                  <RefreshCw size={14} className="spin text-emerald" />
                ) : (
                  <Play size={14} />
                )}
              </button>

              <button
                type="button"
                className="btn btn--icon"
                onClick={() => onShowRedirectUrl(user)}
                title="View Redirect URL"
              >
                <ExternalLink size={14} />
              </button>

              <button
                type="button"
                className="btn btn--icon"
                onClick={() => onEdit(user)}
                title="Edit account credentials"
              >
                <Edit2 size={14} />
              </button>

              <span
                className="delete-btn-wrapper"
                title={
                  isDeleteDisabled
                    ? "Make another user default first"
                    : "Delete user"
                }
              >
                <button
                  type="button"
                  className="btn btn--icon btn--danger"
                  onClick={() => onDelete(user)}
                  disabled={isDeleteDisabled}
                >
                  <Trash2 size={14} />
                </button>
              </span>
            </div>
          );
        },
      },
    ],
    [totalItems, authenticatingUserId, copiedId, onMakeDefault, onEdit, onDelete, onAutoAuth, onShowRedirectUrl]
  );

  const table = useReactTable({
    data: users,
    columns,
    pageCount: totalPages,
    state: {
      pagination: {
        pageIndex,
        pageSize,
      },
    },
    manualPagination: true,
    getCoreRowModel: getCoreRowModel(),
  });

  return (
    <div className="data-table-wrapper">
      <div className="data-table-scroll">
        <table className="data-table">
          <thead>
            {table.getHeaderGroups().map((headerGroup) => (
              <tr key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
                  <th key={header.id}>
                    {header.isPlaceholder
                      ? null
                      : flexRender(
                          header.column.columnDef.header,
                          header.getContext()
                        )}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={columns.length} className="table-state-cell">
                  <div className="loading-spinner-wrap">
                    <RefreshCw size={18} className="spin text-emerald" />
                    <span>Loading users...</span>
                  </div>
                </td>
              </tr>
            ) : users.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="table-state-cell">
                  No users found matching current filter criteria.
                </td>
              </tr>
            ) : (
              table.getRowModel().rows.map((row) => (
                <tr
                  key={row.id}
                  className={row.original.isDefault ? "row-default" : ""}
                >
                  {row.getVisibleCells().map((cell) => (
                    <td key={cell.id}>
                      {flexRender(
                        cell.column.columnDef.cell,
                        cell.getContext()
                      )}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination Footer */}
      <div className="pagination-bar">
        <div className="pagination-info">
          <span>
            Showing{" "}
            <strong>
              {totalItems === 0
                ? 0
                : pageIndex * pageSize + 1}
            </strong>{" "}
            to{" "}
            <strong>
              {Math.min((pageIndex + 1) * pageSize, totalItems)}
            </strong>{" "}
            of <strong>{totalItems}</strong> entries
          </span>
        </div>

        <div className="pagination-controls">
          <div className="rows-per-page">
            <span className="rpp-label">Rows per page:</span>
            <select
              className="select rpp-select"
              value={pageSize}
              onChange={(e) => onPageSizeChange(Number(e.target.value))}
            >
              {[5, 10, 20, 50].map((size) => (
                <option key={size} value={size}>
                  {size}
                </option>
              ))}
            </select>
          </div>

          <div className="pagination-nav-buttons">
            <button
              type="button"
              className="nav-btn"
              onClick={() => onPageChange(0)}
              disabled={pageIndex === 0 || isLoading}
              title="First Page"
            >
              <ChevronsLeft size={16} />
            </button>
            <button
              type="button"
              className="nav-btn"
              onClick={() => onPageChange(pageIndex - 1)}
              disabled={pageIndex === 0 || isLoading}
              title="Previous Page"
            >
              <ChevronLeft size={16} />
            </button>

            <span className="page-indicator">
              Page <strong>{totalPages > 0 ? pageIndex + 1 : 0}</strong> of{" "}
              <strong>{totalPages}</strong>
            </span>

            <button
              type="button"
              className="nav-btn"
              onClick={() => onPageChange(pageIndex + 1)}
              disabled={pageIndex >= totalPages - 1 || isLoading}
              title="Next Page"
            >
              <ChevronRight size={16} />
            </button>
            <button
              type="button"
              className="nav-btn"
              onClick={() => onPageChange(totalPages - 1)}
              disabled={pageIndex >= totalPages - 1 || isLoading}
              title="Last Page"
            >
              <ChevronsRight size={16} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
