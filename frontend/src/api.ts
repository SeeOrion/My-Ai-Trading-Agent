export interface Factor {
  identifier: string;
  name: string;
  theme: string;
  formula: string;
  columns_required: string[];
  warmup_bars: number;
  horizon_days: number;
  description: string;
  version: string;
}

const apiBase = import.meta.env.VITE_API_BASE_URL ?? "";

export async function fetchFactors(): Promise<Factor[]> {
  const response = await fetch(`${apiBase}/api/v1/factors`);
  if (!response.ok) {
    throw new Error("无法连接后端因子库");
  }
  return response.json() as Promise<Factor[]>;
}
