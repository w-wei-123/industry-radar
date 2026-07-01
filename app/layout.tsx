import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: '行业雷达 — A股前沿行业全景分析',
  description: '聚焦A股前沿行业，头部企业、产业链、材料缺口、市场前景一键掌握',
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN" className="h-full antialiased">
      <body className="min-h-full bg-white text-gray-900">{children}</body>
    </html>
  );
}
