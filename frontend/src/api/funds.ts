import { api } from "./client";
import type { FundHistory, FundInfo, PortfolioValuation, Position, ValuationItem } from "../types";

type PositionPayload = {
  fund_code: string;
  position_date: string;
  shares: number;
  avg_cost: number;
};

export async function fetchPositions(): Promise<Position[]> {
  const { data } = await api.get<Position[]>("/positions");
  return data;
}

export async function createPosition(payload: PositionPayload): Promise<Position> {
  const { data } = await api.post<Position>("/positions", payload);
  return data;
}

export async function updatePosition(id: number, payload: PositionPayload): Promise<Position> {
  const { data } = await api.put<Position>(`/positions/${id}`, payload);
  return data;
}

export async function deletePosition(id: number): Promise<void> {
  await api.delete(`/positions/${id}`);
}

export async function fetchFundInfo(fundCode: string): Promise<FundInfo> {
  const { data } = await api.get<FundInfo>(`/funds/${fundCode}`);
  return data;
}

export async function fetchFundHistory(fundCode: string, refresh = false): Promise<FundHistory> {
  const { data } = await api.get<FundHistory>(`/funds/${fundCode}/history`, { params: { refresh } });
  return data;
}

export async function fetchPortfolioValuation(refresh = false): Promise<PortfolioValuation> {
  const { data } = await api.get<PortfolioValuation>("/valuation/portfolio", { params: { refresh } });
  return data;
}

export async function fetchSingleValuation(payload: { fund_code: string; shares: number; avg_cost: number; refresh?: boolean }): Promise<ValuationItem> {
  const { data } = await api.post<ValuationItem>("/valuation/fund", payload);
  return data;
}
