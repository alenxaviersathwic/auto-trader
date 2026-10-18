import { httpClient } from "../../../core/api/httpClient";
import { PageResult } from "../../../core/types/pagination.types";
import {
  RedirectUrlResult,
  User,
  UserCreatePayload,
  UserSearchFilter,
  UserUpdatePayload,
} from "../types/users.types";

/**
 * Pure API functions communicating with backend users endpoints.
 * Automatically unwraps standard ApiResponse envelope via httpClient.
 */

export async function searchUsers(
  filter: UserSearchFilter
): Promise<PageResult<User>> {
  return httpClient.post("/users/search", filter);
}

export async function getUser(id: number): Promise<User> {
  return httpClient.get(`/users/${id}`);
}

export async function getDefaultUser(): Promise<User | null> {
  return httpClient.get("/users/default");
}

export async function createUser(payload: UserCreatePayload): Promise<User> {
  return httpClient.post("/users", payload);
}

export async function updateUser(
  id: number,
  payload: UserUpdatePayload
): Promise<User> {
  return httpClient.put(`/users/${id}`, payload);
}

export async function deleteUser(
  id: number
): Promise<{ id: number; deleted: boolean }> {
  return httpClient.delete(`/users/${id}`);
}

export async function setDefaultUser(id: number): Promise<User> {
  return httpClient.patch(`/users/${id}/default`);
}

export async function updateAutoAuth(
  id: number,
  enabled: boolean
): Promise<User> {
  return httpClient.patch(`/users/${id}/auto-auth`, { enabled });
}

export async function authenticateUser(id: number): Promise<User> {
  return httpClient.post(`/users/${id}/upstox/authenticate`);
}

export async function getRedirectUrl(id: number): Promise<RedirectUrlResult> {
  return httpClient.get(`/users/${id}/upstox/redirect-url`);
}
