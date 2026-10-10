import {
  Alert,
  AppBar,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Container,
  Divider,
  Drawer,
  FormControl,
  FormControlLabel,
  Grid,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  Switch,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Toolbar,
  Typography
} from '@mui/material';
import GroupsIcon from '@mui/icons-material/Groups';
import PaidIcon from '@mui/icons-material/Paid';
import SpeedIcon from '@mui/icons-material/Speed';
import TokenIcon from '@mui/icons-material/DataObject';
import OutputIcon from '@mui/icons-material/Output';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { api } from './api/client';
import { identities } from './api/identities';
import type { Capability, CapabilityStateResponse, GroupResponse } from './api/types';
import { PlatformComparisonCharts, WeeklyTrends } from './components/DashboardCharts';
import { MetricCard } from './components/MetricCard';
import { EmptyState, ErrorState, LoadingState } from './components/StateViews';
import { compactFormat, formatRequests, moneyFormat, numberFormat } from './components/format';

const drawerWidth = 280;
const periods = [
  { value: 'last_7_days', label: 'Last 7 days' },
  { value: 'last_30_days', label: 'Last 30 days' },
  { value: '2026-W36', label: 'ISO week 2026-W36' },
  { value: '2026-09', label: 'September 2026' }
];

function canWriteCapabilities(role: string | undefined, environment: string) {
  if (role === 'platform_admin') {
    return true;
  }
  return role === 'team_lead' && environment !== 'prod';
}

function selectedGroup(groups: GroupResponse[] | undefined, groupId: string) {
  return groups?.find((group) => group.group_id === groupId);
}

function capabilityLabel(capability: Capability) {
  return capability
    .split('-')
    .map((part) => part[0].toUpperCase() + part.slice(1))
    .join(' ');
}

function sourceLabel(capability: CapabilityStateResponse) {
  return capability.updated_at ? 'Override' : 'YAML default';
}

export default function App() {
  const queryClient = useQueryClient();
  const [userId, setUserId] = useState(identities.find((user) => user.role === 'platform_admin')?.user_id ?? identities[0].user_id);
  const [groupId, setGroupId] = useState('');
  const [period, setPeriod] = useState('last_7_days');
  const activeIdentity = identities.find((user) => user.user_id === userId) ?? identities[0];
  const environment = import.meta.env.VITE_MERIDIAN_ENV ?? 'dev';

  const meQuery = useQuery({
    queryKey: ['me', userId],
    queryFn: () => api.me(userId)
  });

  const groupsQuery = useQuery({
    queryKey: ['groups', userId],
    queryFn: () => api.groups(userId),
    retry: false
  });

  useEffect(() => {
    const groups = groupsQuery.data;
    if (!groups?.length) {
      setGroupId('');
      return;
    }
    if (!groupId || !groups.some((group) => group.group_id === groupId)) {
      setGroupId(groups[0].group_id);
    }
  }, [groupsQuery.data, groupId]);

  const enabled = Boolean(groupId);
  const summaryQuery = useQuery({
    queryKey: ['summary', userId, groupId, period],
    queryFn: () => api.summary(userId, groupId, period),
    enabled,
    retry: false
  });

  const weeklyQuery = useQuery({
    queryKey: ['weekly', userId, groupId],
    queryFn: () => api.weekly(userId, groupId),
    enabled,
    retry: false
  });

  const topUsersQuery = useQuery({
    queryKey: ['top-users', userId, groupId, period],
    queryFn: () => api.topUsers(userId, groupId, period, 10),
    enabled,
    retry: false
  });

  const capabilitiesQuery = useQuery({
    queryKey: ['capabilities', userId, groupId],
    queryFn: () => api.capabilities(userId, groupId),
    enabled,
    retry: false
  });

  const capabilityMutation = useMutation({
    mutationFn: ({ capability, checked }: { capability: Capability; checked: boolean }) =>
      api.setCapability(userId, groupId, capability, checked),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['capabilities'] });
      queryClient.invalidateQueries({ queryKey: ['summary'] });
      queryClient.invalidateQueries({ queryKey: ['weekly'] });
    }
  });

  const summary = summaryQuery.data;
  const visibleGroup = selectedGroup(groupsQuery.data, groupId);
  const canTryCapabilityWrite = canWriteCapabilities(meQuery.data?.role, environment);
  const busy = groupsQuery.isLoading || summaryQuery.isLoading || weeklyQuery.isLoading || topUsersQuery.isLoading || capabilitiesQuery.isLoading;
  const dashboardError = summaryQuery.error ?? weeklyQuery.error ?? topUsersQuery.error ?? capabilitiesQuery.error;

  const platformRows = summary?.platforms ?? [];
  const sidebar = (
    <Box sx={{ width: drawerWidth, p: 2 }}>
      <Typography variant="h6" sx={{ fontWeight: 800, mb: 0.5 }}>
        Meridian AI
      </Typography>
      <Typography variant="body2" color="text.secondary">
        Usage and capability governance
      </Typography>
      <Divider sx={{ my: 2 }} />
      <Stack spacing={2}>
        <FormControl fullWidth size="small">
          <InputLabel id="identity-label">Simulated user</InputLabel>
          <Select
            labelId="identity-label"
            label="Simulated user"
            value={userId}
            onChange={(event) => {
              setUserId(event.target.value);
              setGroupId('');
              queryClient.clear();
            }}
          >
            {identities.map((user) => (
              <MenuItem key={user.user_id} value={user.user_id}>
                {user.name}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
        <Box>
          <Typography variant="caption" color="text.secondary">
            Header sent
          </Typography>
          <Typography variant="body2" sx={{ fontFamily: 'monospace', wordBreak: 'break-all' }}>
            X-User-Id: {userId}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            Simulated only, not production authentication.
          </Typography>
        </Box>
        <Divider />
        <Stack spacing={1}>
          <Typography variant="subtitle2">Active identity</Typography>
          <Typography variant="body2">{meQuery.data?.name ?? activeIdentity.name}</Typography>
          <Stack direction="row" spacing={1} flexWrap="wrap">
            <Chip size="small" label={meQuery.data?.role ?? activeIdentity.role} />
            <Chip size="small" variant="outlined" label={meQuery.data?.group_id ?? activeIdentity.group_id} />
          </Stack>
        </Stack>
      </Stack>
    </Box>
  );

  return (
    <Box sx={{ display: 'flex', minHeight: '100vh', bgcolor: '#f6f8fb' }}>
      <Drawer
        variant="permanent"
        sx={{
          display: { xs: 'none', md: 'block' },
          width: drawerWidth,
          flexShrink: 0,
          '& .MuiDrawer-paper': { width: drawerWidth, boxSizing: 'border-box' }
        }}
      >
        {sidebar}
      </Drawer>
      <Box sx={{ flex: 1, minWidth: 0 }}>
        <AppBar position="sticky" color="inherit" elevation={0} sx={{ borderBottom: '1px solid', borderColor: 'divider' }}>
          <Toolbar sx={{ gap: 2, justifyContent: 'space-between' }}>
            <Box>
              <Typography variant="h6" sx={{ fontWeight: 800 }}>
                Platform dashboard
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Data from normalized FastAPI endpoints
              </Typography>
            </Box>
            <Stack direction="row" spacing={1} alignItems="center">
              <Chip color="primary" variant="outlined" label={`env: ${environment}`} />
              <Chip icon={<GroupsIcon />} label={visibleGroup?.name ?? 'No group'} />
            </Stack>
          </Toolbar>
        </AppBar>

        <Container maxWidth="xl" sx={{ py: 3 }}>
          <Box sx={{ display: { xs: 'block', md: 'none' }, mb: 2 }}>
            <Card variant="outlined" sx={{ borderRadius: 2 }}>
              <CardContent>{sidebar}</CardContent>
            </Card>
          </Box>

          <Grid container spacing={2} sx={{ mb: 2 }}>
            <Grid item xs={12} md={5}>
              <FormControl fullWidth>
                <InputLabel id="group-label">Visible group</InputLabel>
                <Select
                  labelId="group-label"
                  label="Visible group"
                  value={groupId}
                  onChange={(event) => setGroupId(event.target.value)}
                  disabled={groupsQuery.isLoading || !groupsQuery.data?.length}
                >
                  {(groupsQuery.data ?? []).map((group) => (
                    <MenuItem key={group.group_id} value={group.group_id}>
                      {group.name}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12} md={4}>
              <FormControl fullWidth>
                <InputLabel id="period-label">Period</InputLabel>
                <Select labelId="period-label" label="Period" value={period} onChange={(event) => setPeriod(event.target.value)}>
                  {periods.map((item) => (
                    <MenuItem key={item.value} value={item.value}>
                      {item.label}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12} md={3}>
              <Button
                fullWidth
                sx={{ height: '100%' }}
                variant="outlined"
                onClick={() => queryClient.invalidateQueries()}
              >
                Refresh data
              </Button>
            </Grid>
          </Grid>

          {groupsQuery.isError ? <ErrorState error={groupsQuery.error} onRetry={() => groupsQuery.refetch()} /> : null}
          {busy ? <LoadingState label="Refreshing dashboard" /> : null}
          {dashboardError ? <ErrorState error={dashboardError} /> : null}
          {!busy && !dashboardError && !summary ? <EmptyState title="No usage data available" /> : null}

          {summary ? (
            <Stack spacing={2}>
              <Grid container spacing={2}>
                <Grid item xs={12} sm={6} lg={3}>
                  <MetricCard label="Total tokens" value={compactFormat.format(summary.totals.total_tokens)} helper={numberFormat.format(summary.totals.total_tokens)} icon={<TokenIcon color="primary" />} />
                </Grid>
                <Grid item xs={12} sm={6} lg={3}>
                  <MetricCard label="Input tokens" value={compactFormat.format(summary.totals.input_tokens)} helper={numberFormat.format(summary.totals.input_tokens)} icon={<SpeedIcon color="primary" />} />
                </Grid>
                <Grid item xs={12} sm={6} lg={3}>
                  <MetricCard label="Output tokens" value={compactFormat.format(summary.totals.output_tokens)} helper={numberFormat.format(summary.totals.output_tokens)} icon={<OutputIcon color="secondary" />} />
                </Grid>
                <Grid item xs={12} sm={6} lg={3}>
                  <MetricCard label="Total cost" value={moneyFormat.format(summary.totals.cost_usd)} helper={`${summary.period.start} to ${summary.period.end_exclusive}`} icon={<PaidIcon color="success" />} />
                </Grid>
              </Grid>

              <Grid container spacing={2}>
                <Grid item xs={12} lg={5}>
                  <PlatformComparisonCharts summary={summary} />
                </Grid>
                <Grid item xs={12} lg={7}>
                  <Card variant="outlined" sx={{ borderRadius: 2, height: '100%' }}>
                    <CardContent>
                      <Typography variant="h6">Platform totals</Typography>
                      <TableContainer>
                        <Table size="small" aria-label="Platform totals">
                          <TableHead>
                            <TableRow>
                              <TableCell>Platform</TableCell>
                              <TableCell align="right">Requests</TableCell>
                              <TableCell align="right">Tokens</TableCell>
                              <TableCell align="right">Cost</TableCell>
                            </TableRow>
                          </TableHead>
                          <TableBody>
                            {platformRows.map((row) => (
                              <TableRow key={row.platform}>
                                <TableCell sx={{ textTransform: 'capitalize' }}>{row.platform}</TableCell>
                                <TableCell align="right">{formatRequests(row.requests)}</TableCell>
                                <TableCell align="right">{numberFormat.format(row.total_tokens)}</TableCell>
                                <TableCell align="right">{moneyFormat.format(row.cost_usd)}</TableCell>
                              </TableRow>
                            ))}
                          </TableBody>
                        </Table>
                      </TableContainer>
                    </CardContent>
                  </Card>
                </Grid>
              </Grid>

              <WeeklyTrends weeks={weeklyQuery.data} />

              <Grid container spacing={2}>
                <Grid item xs={12} lg={7}>
                  <Card variant="outlined" sx={{ borderRadius: 2 }}>
                    <CardContent>
                      <Typography variant="h6">Top users</Typography>
                      {topUsersQuery.data?.length ? (
                        <TableContainer>
                          <Table size="small" aria-label="Top users">
                            <TableHead>
                              <TableRow>
                                <TableCell>Name</TableCell>
                                <TableCell>Email</TableCell>
                                <TableCell align="right">Tokens</TableCell>
                                <TableCell align="right">Cost</TableCell>
                              </TableRow>
                            </TableHead>
                            <TableBody>
                              {topUsersQuery.data.map((user) => (
                                <TableRow key={user.user_id}>
                                  <TableCell>{user.name}</TableCell>
                                  <TableCell>{user.email}</TableCell>
                                  <TableCell align="right">{numberFormat.format(user.total_tokens)}</TableCell>
                                  <TableCell align="right">{moneyFormat.format(user.cost_usd)}</TableCell>
                                </TableRow>
                              ))}
                            </TableBody>
                          </Table>
                        </TableContainer>
                      ) : (
                        <EmptyState title="No users in this period" />
                      )}
                    </CardContent>
                  </Card>
                </Grid>
                <Grid item xs={12} lg={5}>
                  <Card variant="outlined" sx={{ borderRadius: 2 }}>
                    <CardContent>
                      <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1 }}>
                        <Box>
                          <Typography variant="h6">Capability governance</Typography>
                          <Typography variant="body2" color="text.secondary">
                            Defaults come from environment YAML; updates persist as overrides.
                          </Typography>
                        </Box>
                      </Stack>
                      {capabilityMutation.error ? <ErrorState error={capabilityMutation.error} /> : null}
                      <Stack divider={<Divider flexItem />} spacing={1}>
                        {(capabilitiesQuery.data ?? []).map((capability) => (
                          <Stack key={capability.capability} direction="row" justifyContent="space-between" alignItems="center" spacing={2}>
                            <Box>
                              <Typography variant="subtitle2">{capabilityLabel(capability.capability)}</Typography>
                              <Typography variant="caption" color="text.secondary">
                                {sourceLabel(capability)}
                              </Typography>
                            </Box>
                            <FormControlLabel
                              label={capability.enabled ? 'Enabled' : 'Disabled'}
                              control={
                                <Switch
                                  checked={capability.enabled}
                                  disabled={!canTryCapabilityWrite || capabilityMutation.isPending}
                                  onChange={(event) =>
                                    capabilityMutation.mutate({
                                      capability: capability.capability,
                                      checked: event.target.checked
                                    })
                                  }
                                  inputProps={{ 'aria-label': `${capability.capability} enabled` }}
                                />
                              }
                            />
                          </Stack>
                        ))}
                      </Stack>
                      {!canTryCapabilityWrite ? (
                        <Alert severity="info" sx={{ mt: 2 }}>
                          This identity can view capabilities but cannot change them in the selected environment.
                        </Alert>
                      ) : null}
                    </CardContent>
                  </Card>
                </Grid>
              </Grid>
            </Stack>
          ) : null}
        </Container>
      </Box>
    </Box>
  );
}
