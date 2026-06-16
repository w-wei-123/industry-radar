import { Company } from '@/lib/sectors';

const medalColors = [
  'bg-amber-400 text-white',
  'bg-gray-300 text-gray-700',
  'bg-amber-600 text-white',
];

export default function CompanyTable({ companies }: { companies: Company[] }) {
  if (!companies.length) return null;

  return (
    <div className="space-y-4">
      {companies.map((c) => {
        const medal =
          c.rank <= 3
            ? medalColors[c.rank - 1]
            : 'bg-gray-100 text-gray-500';
        return (
          <div
            key={c.rank}
            className="rounded-xl border border-gray-200 bg-white shadow-sm hover:shadow-md transition-shadow relative"
          >
            {/* Alert dot */}
            {c.hasAlert && (
              <span className="absolute top-3 right-3 w-2.5 h-2.5 bg-red-500 rounded-full animate-pulse" title="有新消息" />
            )}

            <div className="flex items-start gap-4 p-5">
              {/* Rank badge */}
              <span
                className={`flex-shrink-0 inline-flex items-center justify-center w-8 h-8 rounded-full text-sm font-bold ${medal}`}
              >
                {c.rank}
              </span>

              {/* Content */}
              <div className="flex-1 min-w-0 space-y-3">
                <div className="flex items-center gap-2">
                  <h3 className="text-lg font-bold text-gray-900">{c.name}</h3>
                  {c.hasAlert && (
                    <span className="text-xs text-red-500 font-medium">🔔 新动态</span>
                  )}
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-2">
                  <InfoRow label="主营业务" value={c.business} />
                  <InfoRow label="优势区域" value={c.region} />
                  <InfoRow label="核心竞争力" value={c.advantage} full />
                </div>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function InfoRow({
  label,
  value,
  full = false,
}: {
  label: string;
  value: string;
  full?: boolean;
}) {
  return (
    <div className={full ? 'sm:col-span-2' : ''}>
      <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide font-bold">
        {label}
      </span>
      <p className="mt-0.5 text-sm text-gray-800 leading-relaxed">{value}</p>
    </div>
  );
}
