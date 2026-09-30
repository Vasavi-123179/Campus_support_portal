export type ApiResponse<T = any> = {
  data: T;
  statusCode: number;
};

export const api = {
  async post<T = any>(path: string, data: Record<string, unknown> = {}): Promise<ApiResponse<T>> {
    const response = await fetch(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(payload.detail || payload.message || `Request failed (${response.status})`);
    }
    return { data: payload, statusCode: response.status };
  },
};