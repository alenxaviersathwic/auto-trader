import React, { useEffect, useState } from "react";
import { BaseFilter, DateFilter } from "../../types/filter.types";
import { EntityStatus } from "../../types/baseEntity.types";
import { Search, RotateCcw, Calendar } from "lucide-react";

export interface FilterBarProps {
  filter: BaseFilter;
  onFilterChange: (newFilter: BaseFilter) => void;
  searchPlaceholder?: string;
  allowedStatuses?: EntityStatus[];
  children?: React.ReactNode; // Extra module-specific filters
}

export const FilterBar: React.FC<FilterBarProps> = ({
  filter,
  onFilterChange,
  searchPlaceholder = "Search by keyword...",
  allowedStatuses = ["ACTIVE", "DELETED"],
  children,
}) => {
  const [searchTerm, setSearchTerm] = useState(filter.query || "");

  // Debounce search text input
  useEffect(() => {
    const timer = setTimeout(() => {
      if ((filter.query || "") !== searchTerm.trim()) {
        onFilterChange({
          ...filter,
          query: searchTerm.trim() ? searchTerm.trim() : undefined,
          page: 0, // Reset to page 0 on text change
        });
      }
    }, 400);

    return () => clearTimeout(timer);
  }, [searchTerm]);

  const handleStatusChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const val = e.target.value as EntityStatus | "";
    onFilterChange({
      ...filter,
      status: val ? (val as EntityStatus) : undefined,
      page: 0,
    });
  };

  const handleDateChange = (field: keyof DateFilter, val: string) => {
    const isoVal = val ? new Date(val).toISOString() : null;
    const currentDates: DateFilter = filter.dateFilter || { from: null, to: null };
    const nextDates: DateFilter = {
      ...currentDates,
      [field]: isoVal,
    };

    // If both dates are empty, pass null
    const hasAnyDate = nextDates.from !== null || nextDates.to !== null;
    onFilterChange({
      ...filter,
      dateFilter: hasAnyDate ? nextDates : null,
      page: 0,
    });
  };

  const handleReset = () => {
    setSearchTerm("");
    onFilterChange({
      ...filter,
      page: 0,
      query: undefined,
      status: "ACTIVE",
      dateFilter: null,
    });
  };

  // Convert ISO string back to date input format YYYY-MM-DD
  const formatInputDate = (isoStr: string | null | undefined): string => {
    if (!isoStr) return "";
    try {
      return isoStr.substring(0, 10);
    } catch {
      return "";
    }
  };

  return (
    <div className="filter-bar-container">
      <div className="filter-bar-row">
        {/* Search Input */}
        <div className="filter-item search-box">
          <Search className="filter-icon" size={16} />
          <input
            type="text"
            className="filter-input"
            placeholder={searchPlaceholder}
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>

        {/* Status Dropdown */}
        <div className="filter-item">
          <label className="filter-label">Status:</label>
          <select
            className="filter-select"
            value={filter.status || "ACTIVE"}
            onChange={handleStatusChange}
          >
            {allowedStatuses.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>

        {/* Date From */}
        <div className="filter-item">
          <Calendar className="filter-icon" size={14} />
          <label className="filter-label">From:</label>
          <input
            type="date"
            className="filter-input date-input"
            value={formatInputDate(filter.dateFilter?.from)}
            onChange={(e) => handleDateChange("from", e.target.value)}
          />
        </div>

        {/* Date To */}
        <div className="filter-item">
          <Calendar className="filter-icon" size={14} />
          <label className="filter-label">To:</label>
          <input
            type="date"
            className="filter-input date-input"
            value={formatInputDate(filter.dateFilter?.to)}
            onChange={(e) => handleDateChange("to", e.target.value)}
          />
        </div>

        {/* Extra module-specific filters */}
        {children && <div className="filter-custom-slots">{children}</div>}

        {/* Reset Button */}
        <button
          type="button"
          className="btn-filter-reset"
          onClick={handleReset}
          title="Reset all filters"
        >
          <RotateCcw size={14} />
          <span>Reset</span>
        </button>
      </div>
    </div>
  );
};
