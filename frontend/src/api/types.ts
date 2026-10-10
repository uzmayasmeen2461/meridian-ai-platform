export type Role = 'member' | 'team_lead' | 'platform_admin';
export type Platform = 'claude' | 'gemini';
export type Capability = 'usage-connector' | 'web-search' | 'code-execution';
export type Period = 'last_7_days' | 'last_30_days' | string;

export interface DenialResponse {
  error: 'permission_denied';
  reason: string;
  required_scope?: string;
}

export interface UserResponse {
  user_id: string;
  email: string;
  name: string;
  role: Role;
  group_id: string;
}

export interface GroupResponse {
  group_id: string;
  name: string;
  team_lead_user_id: string;
}

export interface PlatformTotals {
  platform: Platform;
  requests: number | null;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  cost_usd: number;
}

export interface UsageSummaryResponse {
  group: string;
  period: {
    start: string;
    end_exclusive: string;
  };
  platforms: PlatformTotals[];
  totals: {
    input_tokens: number;
    output_tokens: number;
    total_tokens: number;
    cost_usd: number;
  };
}

export interface WeeklyUsageResponse {
  week: string;
  start: string;
  end_exclusive: string;
  platforms: PlatformTotals[];
  totals: {
    input_tokens: number;
    output_tokens: number;
    total_tokens: number;
    cost_usd: number;
  };
}

export interface TopUserResponse {
  user_id: string;
  name: string;
  email: string;
  group: string;
  total_tokens: number;
  cost_usd: number;
}

export interface CapabilityStateResponse {
  group: string;
  capability: Capability;
  enabled: boolean;
  updated_at: string | null;
  updated_by: string | null;
}
