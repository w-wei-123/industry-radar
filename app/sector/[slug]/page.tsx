import { notFound } from 'next/navigation';
import Link from 'next/link';
import { getSectorBySlug, getAllSectors } from '@/lib/sectors';
import CompanyTable from '@/components/CompanyTable';
import MaterialGapTable from '@/components/MaterialGapTable';
import MarketChart from '@/components/MarketChart';
import SupplyChainMap from '@/components/SupplyChainMap';
import RelatedSectors from '@/components/RelatedSectors';
import ReactMarkdown from 'react-markdown';

function stripTableSections(md: string): string {
  return md
    .replace(/## 头部企业[\s\S]*?(?=## |$)/, '')
    .replace(/## 关键材料[\s\S]*?(?=## |$)/, '')
    .trim();
}

export function generateStaticParams() {
  return getAllSectors().map((s) => ({ slug: s.slug }));
}

export default async function SectorPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const sector = getSectorBySlug(slug);
  if (!sector) notFound();

  return (
    <main className="max-w-5xl mx-auto px-4 py-8">
      {/* Back nav */}
      <Link
        href="/"
        className="inline-flex items-center gap-1 text-sm text-blue-600 hover:text-blue-800 transition-colors mb-6"
      >
        <span>←</span> 返回首页
      </Link>

      {/* Header */}
      <div className="mb-10">
        <h1 className="text-3xl font-bold text-gray-900">
          {sector.meta.sector}
        </h1>
        <div className="flex flex-wrap gap-2 mt-3">
          {sector.meta.tags.map((tag) => (
            <span
              key={tag}
              className="px-3 py-1 text-xs rounded-full bg-blue-50 text-blue-700 border border-blue-200"
            >
              {tag}
            </span>
          ))}
        </div>
        <p className="mt-2 text-sm text-gray-500">
          {sector.meta.stocks.length} 只成分股 · 更新于 {sector.meta.updated}
        </p>
      </div>

      {/* Alerts: active (≤14days) + history */}
      {sector.alerts.length > 0 && (() => {
        const cutoff = new Date();
        cutoff.setDate(cutoff.getDate() - 14);
        const active = sector.alerts.filter((a) => new Date(a.date) >= cutoff);
        const history = sector.alerts.filter((a) => new Date(a.date) < cutoff);

        return (
          <section className="mb-10">
            {/* Active alerts */}
            {active.length > 0 && (
              <>
                <h2 className="text-lg font-bold text-red-600 mb-3">
                  🔔 近期提醒（{active.length}条，14天内）
                </h2>
                <div className="space-y-2 mb-4">
                  {active.map((a, i) => (
                    <div key={i} className="flex items-start gap-3 px-4 py-3 rounded-lg bg-red-50 border border-red-200">
                      <span className="flex-shrink-0 inline-flex items-center justify-center w-6 h-6 rounded-full bg-red-500 text-white text-xs font-bold">{i + 1}</span>
                      <div>
                        <p className="text-sm text-red-800 leading-relaxed">{a.text}</p>
                        <p className="text-xs text-red-400 mt-1">{a.date} · 涉及：{a.companies.join('、')}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </>
            )}

            {/* History alerts */}
            {history.length > 0 && (
              <details className="group">
                <summary className="cursor-pointer text-sm text-gray-500 hover:text-gray-700 font-medium">
                  📋 历史提醒（{history.length}条，14天前）
                </summary>
                <div className="space-y-2 mt-3">
                  {history.map((a, i) => (
                    <div key={i} className="flex items-start gap-3 px-4 py-3 rounded-lg bg-gray-50 border border-gray-200">
                      <span className="flex-shrink-0 inline-flex items-center justify-center w-6 h-6 rounded-full bg-gray-400 text-white text-xs font-bold">{i + 1}</span>
                      <div>
                        <p className="text-sm text-gray-700 leading-relaxed">{a.text}</p>
                        <p className="text-xs text-gray-400 mt-1">{a.date} · 涉及：{a.companies.join('、')}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </details>
            )}
          </section>
        );
      })()}

      {/* Markdown content */}
      <article className="article-content mb-12">
        <ReactMarkdown>{stripTableSections(sector.content)}</ReactMarkdown>
      </article>

      {/* Company Table */}
      {sector.companies.length > 0 && (
        <section className="mb-12">
          <h2 className="text-2xl font-bold text-gray-900 mb-4">
            🏢 头部企业
            <span className="text-base font-normal text-gray-400 ml-2">
              （{sector.companies.length}家）
            </span>
          </h2>
          <CompanyTable companies={sector.companies} />
        </section>
      )}

      {/* Material Gaps */}
      {sector.materials.length > 0 && (
        <section className="mb-12">
          <h2 className="text-2xl font-bold text-gray-900 mb-4">🧩 关键材料 & 缺口</h2>
          <MaterialGapTable materials={sector.materials} />
        </section>
      )}

      {/* Supply Chain Map */}
      {sector.supplyChain && (
        <section className="mb-12">
          <h2 className="text-2xl font-bold text-gray-900 mb-4">🔗 产业链导图</h2>
          <SupplyChainMap markdown={sector.supplyChain} />
        </section>
      )}

      {/* Market Chart */}
      {sector.marketData && (
        <section className="mb-12">
          <h2 className="text-2xl font-bold text-gray-900 mb-4">📈 市场规模预测</h2>
          <MarketChart data={sector.marketData} />
        </section>
      )}

      {/* Related Sectors — Serenity chain conduction */}
      <RelatedSectors slugs={sector.meta.relatedSectors || []} />

      {/* Back to home */}
      <div className="mt-16 pt-8 border-t border-gray-200">
        <Link
          href="/"
          className="text-blue-600 hover:text-blue-800 transition-colors text-sm"
        >
          ← 返回首页查看其他板块
        </Link>
      </div>
    </main>
  );
}
