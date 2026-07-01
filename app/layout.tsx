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
      <body className="min-h-full bg-white text-gray-900">
        {children}
        {/* 已读标记：记住上次访问时间，隐藏已看过的 alerts */}
        <script
          dangerouslySetInnerHTML={{
            __html: `
(function() {
  var KEY = 'radar_last_visit';
  var now = new Date().toISOString().split('T')[0];
  var lastVisit = localStorage.getItem(KEY);

  // 隐藏已看过的板块红点
  if (lastVisit) {
    document.querySelectorAll('.sector-card').forEach(function(card) {
      var updated = card.getAttribute('data-updated');
      if (updated && updated <= lastVisit) {
        var badge = card.querySelector('.alert-badge');
        var text = card.querySelector('.alert-text');
        if (badge) badge.style.display = 'none';
        if (text) text.style.display = 'none';
      }
    });
  }

  // 记录本次访问时间
  localStorage.setItem(KEY, now);
})();
          `.trim(),
          }}
        />
      </body>
    </html>
  );
}
