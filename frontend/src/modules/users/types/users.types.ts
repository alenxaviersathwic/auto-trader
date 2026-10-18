import { BaseFilter } from "../../../core/types/filter.types";

export type UpstoxAuthStatus = "NEVER" | "VALID" | "EXPIRED" | "AUTH_FAILED";

export interface UpstoxConfig {
  apiKey: string;
  mobile: string;
  hasApiSecret: boolean;
  hasPin: boolean;
  hasTotpSecret: boolean;
  redirectUri: string;
  autoAuthEnabled: boolean;
  authStatus: UpstoxAuthStatus;
  tokenExpiresAt: string | null;
  lastAuthAt: string | null;
  lastError: string | null;
  upstoxUserId: string | null;
  profileName: string | null;
  email: string | null;
}

export interface User {
  id: number;
  name: string;
  isDefault: boolean;
  status: "ACTIVE" | "DELETED";
  createdAt: string;
  upstox: UpstoxConfig | null;
}

export interface UserCreatePayload {
  name: string;
  apiKey: string;
  apiSecret: string;
  mobile: string;
  pin: string;
  totpSecret: string;
  autoAuthEnabled: boolean;
}

export interface UserUpdatePayload {
  name?: string;
  apiKey?: string;
  apiSecret?: string;
  mobile?: string;
  pin?: string;
  totpSecret?: string;
  autoAuthEnabled?: boolean;
}

export interface UserSearchFilter extends BaseFilter {
  authStatus?: UpstoxAuthStatus | "";
  isDefault?: boolean;
}

export interface RedirectUrlResult {
  redirectUri: string;
}
