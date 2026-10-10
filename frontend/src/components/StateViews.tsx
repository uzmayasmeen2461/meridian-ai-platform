import { Alert, Box, Button, CircularProgress, Typography } from '@mui/material';
import type { ApiError } from '../api/client';

export function LoadingState({ label = 'Loading data' }: { label?: string }) {
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, py: 3 }}>
      <CircularProgress size={22} />
      <Typography color="text.secondary">{label}</Typography>
    </Box>
  );
}

export function EmptyState({ title, detail }: { title: string; detail?: string }) {
  return (
    <Box sx={{ py: 4 }}>
      <Typography variant="subtitle1">{title}</Typography>
      {detail ? <Typography color="text.secondary">{detail}</Typography> : null}
    </Box>
  );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const apiError = error as ApiError;
  const denial = apiError?.denial;
  return (
    <Alert
      severity={denial ? 'warning' : 'error'}
      action={
        onRetry ? (
          <Button color="inherit" size="small" onClick={onRetry}>
            Retry
          </Button>
        ) : undefined
      }
    >
      <Typography fontWeight={700}>{denial ? 'Permission denied' : 'Request failed'}</Typography>
      <Typography variant="body2">
        {denial ? denial.reason : apiError?.message ?? 'The backend did not return a usable response.'}
      </Typography>
      {denial?.required_scope ? (
        <Typography variant="caption">Required scope: {denial.required_scope}</Typography>
      ) : null}
    </Alert>
  );
}
