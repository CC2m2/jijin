import ReactECharts from "echarts-for-react";

import type { ValuationItem } from "../types";

interface PortfolioChartProps {
  items: ValuationItem[];
}

export function PortfolioChart({ items }: PortfolioChartProps) {
  const successItems = items.filter((item) => item.status === "success" && item.market_value);
  const option = {
    backgroundColor: "transparent",
    tooltip: { trigger: "item" },
    series: [
      {
        type: "pie",
        radius: ["48%", "76%"],
        padAngle: 3,
        label: { color: "#16324f", formatter: "{b}\n{d}%" },
        itemStyle: {
          borderRadius: 14,
          borderColor: "#f8f5ef",
          borderWidth: 3,
        },
        data: successItems.map((item) => ({
          name: item.fund_name || item.fund_code,
          value: item.market_value,
        })),
      },
    ],
  };

  return <ReactECharts option={option} style={{ height: 320 }} />;
}
