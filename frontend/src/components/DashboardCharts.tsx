import { Card, CardContent, Grid, Stack, Typography, useTheme } from '@mui/material';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from 'recharts';
import type { UsageSummaryResponse, WeeklyUsageResponse } from '../api/types';
import { compactFormat, moneyFormat } from './format';

function platformValue(summary: UsageSummaryResponse | undefined, platform: 'claude' | 'gemini', field: 'total_tokens' | 'cost_usd') {
  return summary?.platforms.find((item) => item.platform === platform)?.[field] ?? 0;
}

export function PlatformComparisonCharts({ summary }: { summary?: UsageSummaryResponse }) {
  const theme = useTheme();
  const tokenData = [
    {
      metric: 'Total tokens',
      Claude: platformValue(summary, 'claude', 'total_tokens'),
      Gemini: platformValue(summary, 'gemini', 'total_tokens')
    }
  ];
  const costData = [
    {
      metric: 'USD cost',
      Claude: platformValue(summary, 'claude', 'cost_usd'),
      Gemini: platformValue(summary, 'gemini', 'cost_usd')
    }
  ];

  return (
    <Stack spacing={2}>
      <Card variant="outlined" sx={{ borderRadius: 2 }}>
        <CardContent>
          <Typography variant="h6">Platform Tokens</Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Claude and Gemini token volume share the same token scale.
          </Typography>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={tokenData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="metric" />
              <YAxis tickFormatter={(value) => compactFormat.format(Number(value))} />
              <Tooltip formatter={(value: number) => compactFormat.format(value)} />
              <Legend />
              <Bar dataKey="Claude" fill={theme.palette.primary.main} radius={[4, 4, 0, 0]} />
              <Bar dataKey="Gemini" fill={theme.palette.secondary.main} radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>
      <Card variant="outlined" sx={{ borderRadius: 2 }}>
        <CardContent>
          <Typography variant="h6">Platform Cost</Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            USD costs use a separate money scale.
          </Typography>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={costData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="metric" />
              <YAxis tickFormatter={(value) => moneyFormat.format(Number(value))} />
              <Tooltip formatter={(value: number) => moneyFormat.format(value)} />
              <Legend />
              <Bar dataKey="Claude" fill={theme.palette.primary.main} radius={[4, 4, 0, 0]} />
              <Bar dataKey="Gemini" fill={theme.palette.secondary.main} radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>
    </Stack>
  );
}

export function WeeklyTrends({ weeks }: { weeks?: WeeklyUsageResponse[] }) {
  const theme = useTheme();
  const data = (weeks ?? []).map((week) => {
    const claude = week.platforms.find((item) => item.platform === 'claude');
    const gemini = week.platforms.find((item) => item.platform === 'gemini');
    return {
      week: week.week,
      tokens: week.totals.total_tokens,
      cost: week.totals.cost_usd,
      claudeTokens: claude?.total_tokens ?? 0,
      geminiTokens: gemini?.total_tokens ?? 0
    };
  });

  return (
    <Grid container spacing={2}>
      <Grid item xs={12} lg={7}>
        <Card variant="outlined" sx={{ borderRadius: 2 }}>
          <CardContent>
            <Typography variant="h6">Weekly Tokens</Typography>
            <ResponsiveContainer width="100%" height={280}>
              <LineChart data={data}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="week" />
                <YAxis tickFormatter={(value) => compactFormat.format(Number(value))} />
                <Tooltip formatter={(value: number) => compactFormat.format(value)} />
                <Legend />
                <Line type="monotone" dataKey="claudeTokens" name="Claude" stroke={theme.palette.primary.main} strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="geminiTokens" name="Gemini" stroke={theme.palette.secondary.main} strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </Grid>
      <Grid item xs={12} lg={5}>
        <Card variant="outlined" sx={{ borderRadius: 2 }}>
          <CardContent>
            <Typography variant="h6">Weekly Cost</Typography>
            <ResponsiveContainer width="100%" height={280}>
              <LineChart data={data}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="week" />
                <YAxis tickFormatter={(value) => moneyFormat.format(Number(value))} />
                <Tooltip formatter={(value: number) => moneyFormat.format(value)} />
                <Line type="monotone" dataKey="cost" name="USD" stroke={theme.palette.success.main} strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </Grid>
    </Grid>
  );
}
