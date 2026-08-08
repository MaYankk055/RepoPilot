/**
 * Centralized API utility for RepoPilot frontend.
 * Reads NEXT_PUBLIC_API_URL from environment variables with fallback to http://localhost:8000.
 */

export const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
).replace(/\/+$/, '');

export function getApiUrl(path: string): string {
  const cleanPath = path.startsWith('/') ? path : `/${path}`;
  return `${API_BASE_URL}${cleanPath}`;
}
