import ReactECharts from "echarts-for-react";

import type { FundHistory } from "../types";

interface FundTrendChartProps {
  history: FundHistory | null;
  loading?: boolean;
}

export function FundTrendChart({ history, loading = false }: FundTrendChartProps) {
  const points = history?.points ?? [];
  const option = {
    animationDuration: 500,
    grid: { left: 36, right: 24, top: 36, bottom: 36 },
    tooltip: { trigger: "axis" },
    xAxis: {
      type: "category",
      boundaryGap: false,
      data: points.map((point) => point.nav_date),
      axisLabel: { color: "#62748a", hideOverlap: true },
    },
    yAxis: {
      type: "value",
      scale: true,
      axisLabel: { color: "#62748a" },
      splitLine: { lineStyle: { color: "rgba(22, 50, 79, 0.08)" } },
    },
    series: [
      {
        data: points.map((point) => point.unit_nav),
        type: "line",
        smooth: false,
        showSymbol: false,
        lineStyle: { width: 3, color: "#c97b2f" },
        areaStyle: {
          color: {
            type: "linear",
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: "rgba(201, 123, 47, 0.35)" },
              { offset: 1, color: "rgba(201, 123, 47, 0.03)" },
            ],
          },
        },
      },
    ],
  };

  return <ReactECharts option={option} showLoading={loading} style={{ height: 320 }} />;
}