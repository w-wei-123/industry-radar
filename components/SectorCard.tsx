import Link from 'next/link';
import { SectorMeta } from '@/lib/sectors';

function isRecent(dateStr: string, days: number): boolean {
  if (!dateStr) return false;
  const d = new Date(dateStr);
  const now = new Date();
  const diff = (now.getTime() - d.getTime()) / (1000 * 60 * 60 * 24);
  return diff <= days;
}

export default function SectorCard({ sector }: { sector: SectorMeta }) {
  const updatedToday = isRecent(sector.updated || '', 0);
  const updatedRecent = isRecent(sector.updated || '', 2);
  const hasAlerts = sector.alertCount > 0;

  return (
    <Link
      href={`/sector/${sector.slug}`}
      className={`block p-5 rounded-xl border-2 hover:shadow-lg transition-all group bg-white relative sector-card ${
        updatedToday ? 'border-blue-400 bg-blue-50/30' :
        updatedRecent ? 'border-gray-300' :
        'border-gray-200'
      }`}
      data-sector={sector.slug}
      data-updated={sector.updated || ''}
      data-alert-count={sector.alertCount}
    >
      {/* Update badge — prominent */}
      {hasAlerts && (
        <span className="alert-badge absolute -top-2 -right-2 inline-flex items-center justify-center min-w-[28px] h-7 rounded-full bg-red-500 text-white text-sm font-bold shadow-lg animate-pulse px-2">
          {sector.alertCount} 条更新
        </span>
      )}
      {!hasAlerts && updatedToday && (
        <span className="alert-badge absolute -top-2 -right-2 inline-flex items-center justify-center h-7 rounded-full bg-blue-500 text-white text-xs font-bold shadow-lg px-3">
          今日更新
        </span>
      )}
      {!hasAlerts && !updatedToday && updatedRecent && (
        <span className="absolute -top-2 -right-2 inline-flex items-center justify-center h-6 rounded-full bg-gray-400 text-white text-[10px] font-medium px-2">
          最近
        </span>
      )}

      {/* Title */}
      <h2 className="text-lg font-bold text-gray-900 group-hover:text-blue-600 transition-colors">
        {sector.sector}
      </h2>

      {/* Description — first tag as subtitle */}
      {sector.tags.length > 0 && (
        <p className="mt-1.5 text-sm text-gray-500 line-clamp-1">
          {sector.tags.slice(0, 3).join(' · ')}
        </p>
      )}

      {/* Bottom row */}
      <div className="mt-3 flex items-center justify-between text-xs text-gray-400">
        <span>{sector.stocks.length} 只标的</span>
        {sector.updated && (
          <span className={updatedToday ? 'text-blue-500 font-semibold' : ''}>
            {updatedToday ? '🕐 今天' : sector.updated}
          </span>
        )}
      </div>
    </Link>
  );
}
