export interface Position {
  id: number;
  fund_code: string;
  fund_name?: string | null;
  position_date: string;
  shares: number;
  avg_cost: number;
  pending_amount: number;
  created_at: string;
  updated_at: string;
}

export interface FundInfo {
  fund_code: string;
  fund_name: string;
  fund_type?: string | null;
  estimated_nav?: number | null;
  unit_nav?: number | null;
  change_rate?: number | null;
  nav_date?: string | null;
  source: string;
}

export interface FundHistoryPoint {
  nav_date: string;
  unit_nav: number;
  change_rate?: number | null;
}

export interface FundHistory {
  fund_code: string;
  fund_name: string;
  source: string;
  points: FundHistoryPoint[];
}

export interface ValuationItem {
  fund_code: string;
  fund_name?: string | null;
  position_date?: string | null;
  shares: number;
  avg_cost: number;
  estimated_nav?: number | null;
  unit_nav?: number | null;
  market_value?: number | null;
  cost_value: number;
  profit?: number | null;
  profit_rate?: number | null;
  change_rate?: number | null;
  nav_date?: string | null;
  source?: string | null;
  status: "success" | "failed";
  error?: string | null;
}

export interface PortfolioValuation {
  total_cost: number;
  total_market_value: number;
  total_profit: number;
  total_profit_rate?: number | null;
  success_count: number;
  failed_count: number;
  items: ValuationItem[];
}
