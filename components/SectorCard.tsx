import Link from 'next/link';
import { SectorMeta } from '@/lib/sectors';

// 判断是否为今天更新
function isToday(dateStr: string): boolean {
  if (!dateStr) return false;
  const today = new Date().toISOString().split('T')[0];
  return dateStr === today;
}

export default function SectorCard({ sector }: { sector: SectorMeta }) {
  const updatedToday = isToday(sector.updated || '');

  return (
    <Link
      href={`/sector/${sector.slug}`}
      className="block p-6 rounded-xl border border-gray-200 hover:border-blue-400 hover:shadow-lg transition-all group bg-white relative sector-card"
      data-sector={sector.slug}
      data-updated={sector.updated || ''}
      data-alert-count={sector.alertCount}
    >
      {/* Red dot for alerts — hidden by JS when already seen */}
      {sector.alertCount > 0 && (
        <span className="alert-badge absolute top-3 right-3 inline-flex items-center justify-center w-6 h-6 rounded-full bg-red-500 text-white text-xs font-bold animate-pulse">
          {sector.alertCount}
        </span>
      )}

      {/* NEW badge for today-updated sectors without alerts */}
      {sector.alertCount === 0 && updatedToday && (
        <span className="alert-badge absolute top-3 right-3 inline-flex items-center justify-center px-2 h-5 rounded-full bg-blue-500 text-white text-[10px] font-bold">
          NEW
        </span>
      )}

      <h2 className="text-xl font-bold text-gray-900 group-hover:text-blue-600 transition-colors pr-8">
        {sector.sector}
      </h2>

      <div className="flex flex-wrap gap-1.5 mt-3">
        {sector.tags.map((tag) => (
          <span
            key={tag}
            className="px-2 py-0.5 text-xs rounded-full bg-gray-100 text-gray-700"
          >
            {tag}
          </span>
        ))}
      </div>

      <div className="mt-4 flex items-center justify-between text-sm text-gray-600">
        <span>{sector.stocks.length} 只成分股</span>
        <div className="flex items-center gap-3">
          {sector.alertCount > 0 && (
            <span className="alert-text text-red-500 text-xs font-medium">
              {sector.alertCount} 条新消息
            </span>
          )}
          {updatedToday && sector.alertCount === 0 && (
            <span className="alert-text text-blue-500 text-xs font-medium">
              今日更新
            </span>
          )}
          {sector.updated && <span>更新于 {sector.updated}</span>}
        </div>
      </div>
    </Link>
  );
}
