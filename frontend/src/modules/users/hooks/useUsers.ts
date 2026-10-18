import {
  useMutation,
  useQuery,
  useQueryClient,
  keepPreviousData,
} from "@tanstack/react-query";
import {
  authenticateUser,
  createUser,
  deleteUser,
  getDefaultUser,
  getRedirectUrl,
  getUser,
  searchUsers,
  setDefaultUser,
  updateAutoAuth,
  updateUser,
} from "../api/users.api";
import { userQueryKeys } from "../queryKeys/usersQueryKeys";
import {
  UserCreatePayload,
  UserSearchFilter,
  UserUpdatePayload,
} from "../types/users.types";

/**
 * Hook to search users with pagination and filters.
 */
export function useUserSearch(filter: UserSearchFilter) {
  return useQuery({
    queryKey: userQueryKeys.list(filter),
    queryFn: () => searchUsers(filter),
    placeholderData: keepPreviousData,
  });
}

/**
 * Hook to fetch the single active default user.
 */
export function useDefaultUser() {
  return useQuery({
    queryKey: userQueryKeys.default(),
    queryFn: () => getDefaultUser(),
    refetchInterval: 15000, // Sync default user status periodically
  });
}

/**
 * Hook to fetch single user details.
 */
export function useUserDetail(id: number) {
  return useQuery({
    queryKey: userQueryKeys.detail(id),
    queryFn: () => getUser(id),
    enabled: id > 0,
  });
}

/**
 * Hook to fetch Upstox redirect URL for a user.
 */
export function useRedirectUrl(id: number, enabled: boolean = false) {
  return useQuery({
    queryKey: userQueryKeys.redirectUrl(id),
    queryFn: () => getRedirectUrl(id),
    enabled: enabled && id > 0,
  });
}

/**
 * Hook to create a new user and initial Upstox config.
 */
export function useCreateUser() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (payload: UserCreatePayload) => createUser(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: userQueryKeys.lists() });
      queryClient.invalidateQueries({ queryKey: userQueryKeys.default() });
    },
  });
}

/**
 * Hook to update an existing user.
 */
export function useUpdateUser() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: UserUpdatePayload }) =>
      updateUser(id, payload),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: userQueryKeys.lists() });
      queryClient.invalidateQueries({ queryKey: userQueryKeys.detail(data.id) });
      queryClient.invalidateQueries({ queryKey: userQueryKeys.default() });
    },
  });
}

/**
 * Hook to soft delete a user.
 */
export function useDeleteUser() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: number) => deleteUser(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: userQueryKeys.lists() });
      queryClient.invalidateQueries({ queryKey: userQueryKeys.default() });
    },
  });
}

/**
 * Hook to set user as primary default account.
 */
export function useSetDefaultUser() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: number) => setDefaultUser(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: userQueryKeys.lists() });
      queryClient.invalidateQueries({ queryKey: userQueryKeys.default() });
    },
  });
}

/**
 * Hook to toggle auto authentication on/off.
 */
export function useUpdateAutoAuth() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, enabled }: { id: number; enabled: boolean }) =>
      updateAutoAuth(id, enabled),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: userQueryKeys.lists() });
      queryClient.invalidateQueries({ queryKey: userQueryKeys.detail(data.id) });
      queryClient.invalidateQueries({ queryKey: userQueryKeys.default() });
    },
  });
}

/**
 * Hook to execute manual Upstox authentication.
 */
export function useAuthenticateUser() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: number) => authenticateUser(id),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: userQueryKeys.lists() });
      queryClient.invalidateQueries({ queryKey: userQueryKeys.detail(data.id) });
      queryClient.invalidateQueries({ queryKey: userQueryKeys.default() });
    },
  });
}
