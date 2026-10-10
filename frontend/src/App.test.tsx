import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import App from './App';
import { api } from './api/client';
import type { CapabilityStateResponse, GroupResponse, UsageSummaryResponse, WeeklyUsageResponse } from './api/types';

vi.mock('./api/client', () => {
  class ApiError extends Error {
    status?: number;
    denial?: unknown;
    constructor(message: string, status?: number, denial?: unknown) {
      super(message);
      this.status = status;
      this.denial = denial;
    }
  }
  return {
    ApiError,
    api: {
      me: vi.fn(),
      groups: vi.fn(),
      summary: vi.fn(),
      weekly: vi.fn(),
      topUsers: vi.fn(),
      capabilities: vi.fn(),
      setCapability: vi.fn()
    }
  };
});

const mockedApi = vi.mocked(api);

const admin = {
  user_id: 'user_533B58E6F66C98ACB833527A',
  email: 'chloe.dubois@meridianls.example',
  name: 'Chloe Dubois',
  role: 'platform_admin' as const,
  group_id: 'it-platform'
};

const priya = {
  user_id: 'user_E7691888F28227066DD2FB86',
  email: 'priya.nair@meridianls.example',
  name: 'Priya Nair',
  role: 'team_lead' as const,
  group_id: 'clinical-operations'
};

const groups: GroupResponse[] = [
  { group_id: 'clinical-operations', name: 'Clinical Operations', team_lead_user_id: priya.user_id },
  { group_id: 'finance', name: 'Finance', team_lead_user_id: 'user_0CF0516C4D9067BED584DB3F' }
];

function summary(group = 'clinical-operations'): UsageSummaryResponse {
  return {
    group,
    period: { start: '2026-09-21', end_exclusive: '2026-09-28' },
    platforms: [
      { platform: 'claude', requests: 273, input_tokens: 777862, output_tokens: 146039, total_tokens: 923901, cost_usd: 13.138176 },
      { platform: 'gemini', requests: null, input_tokens: 1308144, output_tokens: 332854, total_tokens: 1640998, cost_usd: 1.224578 }
    ],
    totals: { input_tokens: 2086006, output_tokens: 478893, total_tokens: 2564899, cost_usd: 14.362754 }
  };
}

const weeks: WeeklyUsageResponse[] = [
  {
    week: '2026-W39',
    start: '2026-09-21',
    end_exclusive: '2026-09-28',
    platforms: summary().platforms,
    totals: { input_tokens: 0, output_tokens: 0, total_tokens: 2564899, cost_usd: 14.362754 }
  }
];

const capabilities: CapabilityStateResponse[] = [
  { group: 'clinical-operations', capability: 'code-execution', enabled: false, updated_at: null, updated_by: null },
  { group: 'clinical-operations', capability: 'usage-connector', enabled: true, updated_at: null, updated_by: null },
  { group: 'clinical-operations', capability: 'web-search', enabled: true, updated_at: '2026-10-09T10:00:00Z', updated_by: admin.user_id }
];

function arrange() {
  mockedApi.me.mockResolvedValue(admin);
  mockedApi.groups.mockResolvedValue(groups);
  mockedApi.summary.mockImplementation((_userId, groupId, period) => Promise.resolve({ ...summary(groupId), period: period === '2026-09' ? { start: '2026-09-01', end_exclusive: '2026-10-01' } : summary().period }));
  mockedApi.weekly.mockResolvedValue(weeks);
  mockedApi.topUsers.mockResolvedValue([
    { user_id: priya.user_id, name: 'Priya Nair', email: priya.email, group: 'Clinical Operations', total_tokens: 1800583, cost_usd: 4.84453 }
  ]);
  mockedApi.capabilities.mockResolvedValue(capabilities);
  mockedApi.setCapability.mockResolvedValue({ ...capabilities[0], enabled: true, updated_at: '2026-10-09T12:00:00Z', updated_by: admin.user_id });
}

function renderApp() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } }
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  arrange();
});

describe('Meridian dashboard', () => {
  it('loads identity, visible groups, usage totals, and preserves Gemini null requests', async () => {
    renderApp();

    expect(await screen.findByText('Platform dashboard')).toBeInTheDocument();
    expect(await screen.findByText('2.6M')).toBeInTheDocument();
    expect(screen.getByText('Platform Tokens')).toBeInTheDocument();
    expect(screen.getByText('Platform Cost')).toBeInTheDocument();
    expect(screen.getByText('Not reported')).toBeInTheDocument();
    expect(mockedApi.summary).toHaveBeenCalledWith(admin.user_id, 'clinical-operations', 'last_7_days');
  });

  it('refreshes cached queries when identity changes', async () => {
    const user = userEvent.setup();
    mockedApi.me.mockImplementation((userId) => Promise.resolve(userId === priya.user_id ? priya : admin));
    mockedApi.groups.mockImplementation((userId) => Promise.resolve(userId === priya.user_id ? [groups[0]] : groups));

    renderApp();
    await screen.findByText('2.6M');

    await user.click(screen.getAllByRole('combobox', { name: /simulated user/i })[0]);
    await user.click(await screen.findByRole('option', { name: /Priya Nair/i }));

    await waitFor(() => expect(mockedApi.me).toHaveBeenCalledWith(priya.user_id));
    await waitFor(() => expect(mockedApi.groups).toHaveBeenCalledWith(priya.user_id));
  });

  it('uses visible group access and reacts to period changes', async () => {
    const user = userEvent.setup();
    renderApp();
    await screen.findByText('2.6M');

    await user.click(screen.getByRole('combobox', { name: /period/i }));
    await user.click(screen.getByRole('option', { name: /September 2026/i }));

    await waitFor(() => expect(mockedApi.summary).toHaveBeenCalledWith(admin.user_id, 'clinical-operations', '2026-09'));
  });

  it('shows structured API permission errors without protected rows', async () => {
    mockedApi.summary.mockRejectedValue({
      denial: {
        error: 'permission_denied',
        reason: 'Caller may not access the requested group.',
        required_scope: 'usage:read'
      },
      message: 'Caller may not access the requested group.'
    });

    renderApp();

    expect(await screen.findByText('Permission denied')).toBeInTheDocument();
    expect(screen.getByText('Required scope: usage:read')).toBeInTheDocument();
    expect(screen.queryByText(/sofia\.rossi/i)).not.toBeInTheDocument();
  });

  it('persists capability toggles through the API and shows default versus override state', async () => {
    const user = userEvent.setup();
    renderApp();

    expect((await screen.findAllByText('YAML default')).length).toBeGreaterThan(0);
    expect(await screen.findByText('Override')).toBeInTheDocument();

    const switchControl = screen.getByLabelText('code-execution enabled');
    await user.click(switchControl);

    await waitFor(() => {
      expect(mockedApi.setCapability).toHaveBeenCalledWith(admin.user_id, 'clinical-operations', 'code-execution', true);
    });
  });

  it('disables capability toggles for identities that are not authorized to write', async () => {
    mockedApi.me.mockResolvedValue({ ...admin, role: 'member' });

    renderApp();

    const switchControl = await screen.findByLabelText('code-execution enabled');
    expect(switchControl).toBeDisabled();
    expect(screen.getByText(/cannot change them/i)).toBeInTheDocument();
  });

  it('shows loading and empty states', async () => {
    mockedApi.groups.mockImplementation(() => new Promise(() => undefined));
    const { unmount } = renderApp();

    expect(await screen.findByText('Refreshing dashboard')).toBeInTheDocument();
    unmount();

    vi.clearAllMocks();
    arrange();
    mockedApi.groups.mockResolvedValue([]);
    renderApp();

    expect(await screen.findByText('No usage data available')).toBeInTheDocument();
  });

  it('renders the dashboard controls at a narrow viewport', async () => {
    Object.defineProperty(window, 'innerWidth', { configurable: true, value: 390 });
    window.dispatchEvent(new Event('resize'));

    renderApp();

    expect(await screen.findByText('Platform dashboard')).toBeInTheDocument();
    expect(screen.getAllByRole('combobox', { name: /simulated user/i }).length).toBeGreaterThan(0);
    expect(screen.getByRole('combobox', { name: /period/i })).toBeInTheDocument();
  });
});
