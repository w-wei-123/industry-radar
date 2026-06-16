import Link from 'next/link';
import { SectorMeta } from '@/lib/sectors';

export default function SectorCard({ sector }: { sector: SectorMeta }) {
  return (
    <Link
      href={`/sector/${sector.slug}`}
      className="block p-6 rounded-xl border border-gray-200 hover:border-blue-400 hover:shadow-lg transition-all group bg-white relative"
    >
      {/* Alert badge */}
      {sector.alertCount > 0 && (
        <span className="absolute top-3 right-3 inline-flex items-center justify-center w-6 h-6 rounded-full bg-red-500 text-white text-xs font-bold animate-pulse">
          {sector.alertCount}
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
            <span className="text-red-500 text-xs font-medium">
              {sector.alertCount} 条新消息
            </span>
          )}
          {sector.updated && <span>更新于 {sector.updated}</span>}
        </div>
      </div>
    </Link>
  );
}
