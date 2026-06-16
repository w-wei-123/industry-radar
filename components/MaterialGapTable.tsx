import { MaterialGap } from '@/lib/sectors';

const gapConfig: Record<string, { bg: string; text: string; bar: string }> = {
  '严重': { bg: 'bg-red-50', text: 'text-red-700', bar: 'bg-red-500' },
  '较大': { bg: 'bg-orange-50', text: 'text-orange-700', bar: 'bg-orange-500' },
  '中等': { bg: 'bg-yellow-50', text: 'text-yellow-700', bar: 'bg-yellow-500' },
  '较小': { bg: 'bg-green-50', text: 'text-green-700', bar: 'bg-green-500' },
};

export default function MaterialGapTable({ materials }: { materials: MaterialGap[] }) {
  if (!materials.length) return null;

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {materials.map((m, i) => {
        const style = gapConfig[m.gapLevel] || { bg: 'bg-gray-50', text: 'text-gray-600', bar: 'bg-gray-400' };
        return (
          <div
            key={i}
            className={`rounded-xl border border-gray-200 p-5 ${style.bg} bg-opacity-40`}
          >
            {/* Material name + gap badge */}
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-bold text-gray-900 text-sm">{m.material}</h3>
              <span className={`inline-block px-2.5 py-0.5 rounded-full text-xs font-semibold ${style.text} bg-white border border-current/20`}>
                {m.gapLevel}
              </span>
            </div>

            {/* Gap bar */}
            <div className="w-full h-1.5 bg-gray-200 rounded-full mb-3 overflow-hidden">
              <div
                className={`h-full rounded-full ${style.bar}`}
                style={{
                  width:
                    m.gapLevel === '严重' ? '90%' :
                    m.gapLevel === '较大' ? '65%' :
                    m.gapLevel === '中等' ? '40%' : '20%'
                }}
              />
            </div>

            {/* Details */}
            <div className="space-y-1.5 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-500">国产化率</span>
                <span className="text-gray-700 font-medium">{m.localization}</span>
              </div>
              <div>
                <span className="text-gray-500 text-xs block mb-0.5">主要供应商</span>
                <span className="text-gray-800 leading-relaxed">{m.suppliers}</span>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
