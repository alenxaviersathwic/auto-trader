import { useQuery } from "@tanstack/react-query";
import { getMasterHealth } from "../api/master.api";
import { masterQueryKeys } from "../queryKeys/masterQueryKeys";

export function useMasterHealth() {
  return useQuery({
    queryKey: masterQueryKeys.health,
    queryFn: getMasterHealth,
    refetchInterval: 30000,
    retry: 1,
  });
}
