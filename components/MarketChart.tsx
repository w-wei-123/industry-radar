'use client';

import ReactECharts from 'echarts-for-react';
import { MarketData } from '@/lib/sectors';

export default function MarketChart({ data }: { data: MarketData }) {
  const option = {
    tooltip: {
      trigger: 'axis' as const,
      formatter: (params: { name: string; value: number }[]) => {
        const p = params[0];
        return `${p.name}<br/><b>${p.value.toLocaleString()} ${data.unit}</b>`;
      },
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      top: '10%',
      containLabel: true,
    },
    xAxis: {
      type: 'category' as const,
      data: data.years,
      axisLine: { lineStyle: { color: '#d1d5db' } },
      axisLabel: { color: '#6b7280' },
    },
    yAxis: {
      type: 'value' as const,
      axisLabel: {
        color: '#6b7280',
        formatter: (v: number) => {
          if (v >= 100000000) return `${(v / 100000000).toFixed(1)}亿`;
          if (v >= 10000) return `${(v / 10000).toFixed(0)}万`;
          return v.toString();
        },
      },
      splitLine: { lineStyle: { color: '#f3f4f6' } },
    },
    series: [
      {
        name: data.label,
        data: data.values,
        type: 'line',
        smooth: true,
        symbol: 'circle',
        symbolSize: 8,
        lineStyle: { color: '#3b82f6', width: 3 },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(59,130,246,0.25)' },
              { offset: 1, color: 'rgba(59,130,246,0.02)' },
            ],
          },
        },
        itemStyle: { color: '#3b82f6' },
      },
    ],
  };

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
      <h3 className="text-sm font-semibold text-gray-700 mb-2">{data.label}</h3>
      <ReactECharts option={option} style={{ height: 380 }} />
    </div>
  );
}
