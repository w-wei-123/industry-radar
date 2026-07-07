import type { Metadata } from 'next';
import './globals.css';

// 构建时间戳 — 每次 npm run build 时自动更新，用于版本检测
const BUILD_TIME = new Date().toISOString();

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
    <html lang="zh-CN" className="h-full antialiased" data-build={BUILD_TIME}>
      <head>
        {/* 禁止浏览器缓存，确保每次打开都是最新版本 */}
        <meta httpEquiv="Cache-Control" content="no-cache, no-store, must-revalidate" />
        <meta httpEquiv="Pragma" content="no-cache" />
        <meta httpEquiv="Expires" content="0" />
        <meta name="build-time" content={BUILD_TIME} />
      </head>
      <body className="min-h-full bg-white text-gray-900">
        {/* 更新检测提示条 — JS 控制显示和点击 */}
        <div id="update-banner" className="hidden fixed top-0 left-0 right-0 z-[9999] bg-blue-700 text-white text-center py-2.5 px-4 text-sm font-semibold cursor-pointer">
          🆕 网站已更新 — 点击刷新查看最新内容
        </div>
        {children}
        <script
          dangerouslySetInnerHTML={{
            __html: `
(function() {
  var BUILD_TIME = '${BUILD_TIME}';
  var VISIT_KEY = 'radar_last_visit';
  var VERSION_KEY = 'radar_build_version';
  var now = new Date().toISOString().split('T')[0];
  var lastVisit = localStorage.getItem(VISIT_KEY);
  var lastVersion = localStorage.getItem(VERSION_KEY);

  // 1. 更新提示条：点击刷新 + 版本检测自动显示
  var banner = document.getElementById('update-banner');
  if (banner) {
    banner.addEventListener('click', function() { location.reload(); });
    if (lastVersion && lastVersion !== BUILD_TIME) {
      banner.classList.remove('hidden');
    }
  }
  localStorage.setItem(VERSION_KEY, BUILD_TIME);

  // 2. 红点检测：上次访问 < 板块更新 → 隐藏红点
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

  // 3. 记录本次访问
  localStorage.setItem(VISIT_KEY, now);
})();
          `.trim(),
          }}
        />
      </body>
    </html>
  );
}
