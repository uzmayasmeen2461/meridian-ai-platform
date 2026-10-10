export const numberFormat = new Intl.NumberFormat('en-US');
export const compactFormat = new Intl.NumberFormat('en-US', {
  notation: 'compact',
  maximumFractionDigits: 1
});
export const moneyFormat = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
  maximumFractionDigits: 2
});

export function formatRequests(value: number | null) {
  return value === null ? 'Not reported' : numberFormat.format(value);
}
