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
  var VERSION_KEY = 'radar_build_version';
  var READ_KEY = 'radar_read_counts';   // per-sector read counts: {"slug": 5}

  // 1. 更新提示条
  var banner = document.getElementById('update-banner');
  if (banner) {
    banner.addEventListener('click', function() { location.reload(); });
    var lastVersion = localStorage.getItem(VERSION_KEY);
    if (lastVersion && lastVersion !== BUILD_TIME) {
      banner.classList.remove('hidden');
    }
  }
  localStorage.setItem(VERSION_KEY, BUILD_TIME);

  // 2. QQ式未读计数: 总消息数 - 已读数 = 未读数
  var readCounts = {};
  try {
    readCounts = JSON.parse(localStorage.getItem(READ_KEY) || '{}');
  } catch(e) {}

  document.querySelectorAll('.sector-card').forEach(function(card) {
    var slug = card.getAttribute('data-sector');
    var total = parseInt(card.getAttribute('data-alert-count')) || 0;
    var read = readCounts[slug] || 0;
    var unread = Math.max(0, total - read);
    var badge = card.querySelector('.alert-badge');

    if (badge && unread > 0) {
      // Update badge text to show unread count
      badge.textContent = unread;
      badge.style.display = '';
    } else if (badge && unread === 0) {
      badge.style.display = 'none';
    }
  });

  // 3. 点击卡片 = 已读该板块所有消息
  document.querySelectorAll('.sector-card').forEach(function(card) {
    card.addEventListener('click', function() {
      var slug = card.getAttribute('data-sector');
      var total = parseInt(card.getAttribute('data-alert-count')) || 0;
      readCounts[slug] = total;
      localStorage.setItem(READ_KEY, JSON.stringify(readCounts));
    });
  });
})();
          `.trim(),
          }}
        />
      </body>
    </html>
  );
}
