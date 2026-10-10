import axios, { AxiosError } from 'axios';
import type {
  Capability,
  CapabilityStateResponse,
  DenialResponse,
  GroupResponse,
  TopUserResponse,
  UsageSummaryResponse,
  UserResponse,
  WeeklyUsageResponse
} from './types';

const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? ''
});

export class ApiError extends Error {
  status?: number;
  denial?: DenialResponse;

  constructor(message: string, status?: number, denial?: DenialResponse) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.denial = denial;
  }
}

function headers(userId: string) {
  return { 'X-User-Id': userId };
}

function toApiError(error: unknown): ApiError {
  if (axios.isAxiosError(error)) {
    const axiosError = error as AxiosError<DenialResponse | { detail?: string }>;
    const status = axiosError.response?.status;
    const data = axiosError.response?.data;
    if (data && 'error' in data && data.error === 'permission_denied') {
      return new ApiError(data.reason, status, data);
    }
    if (data && 'detail' in data) {
      return new ApiError(String(data.detail), status);
    }
    return new ApiError(axiosError.message, status);
  }
  return new ApiError(error instanceof Error ? error.message : 'Unexpected API error');
}

async function request<T>(call: () => Promise<{ data: T }>): Promise<T> {
  try {
    const response = await call();
    return response.data;
  } catch (error) {
    throw toApiError(error);
  }
}

export const api = {
  me: (userId: string) => request<UserResponse>(() => http.get('/api/me', { headers: headers(userId) })),
  groups: (userId: string) => request<GroupResponse[]>(() => http.get('/api/groups', { headers: headers(userId) })),
  summary: (userId: string, groupId: string, period: string) =>
    request<UsageSummaryResponse>(() =>
      http.get('/api/usage/summary', {
        headers: headers(userId),
        params: { group_id: groupId, period }
      })
    ),
  weekly: (userId: string, groupId: string) =>
    request<WeeklyUsageResponse[]>(() =>
      http.get('/api/usage/by-week', {
        headers: headers(userId),
        params: { group_id: groupId }
      })
    ),
  topUsers: (userId: string, groupId: string, period: string, limit = 10) =>
    request<TopUserResponse[]>(() =>
      http.get('/api/usage/top-users', {
        headers: headers(userId),
        params: { group_id: groupId, period, limit }
      })
    ),
  capabilities: (userId: string, groupId: string) =>
    request<CapabilityStateResponse[]>(() =>
      http.get('/api/capabilities', {
        headers: headers(userId),
        params: { group_id: groupId }
      })
    ),
  setCapability: (userId: string, groupId: string, capability: Capability, enabled: boolean) =>
    request<CapabilityStateResponse>(() =>
      http.put(
        `/api/capabilities/${groupId}/${capability}`,
        { enabled },
        { headers: headers(userId) }
      )
    )
};
