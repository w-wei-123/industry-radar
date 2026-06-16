import { getAllSectors } from '@/lib/sectors';
import SectorCard from '@/components/SectorCard';

export default function Home() {
  const sectors = getAllSectors();

  return (
    <main className="max-w-7xl mx-auto px-4 py-12">
      {/* Hero */}
      <div className="text-center mb-12">
        <h1 className="text-4xl font-bold tracking-tight text-gray-900 sm:text-5xl">
          行业雷达
        </h1>
        <p className="mt-4 text-lg text-gray-500 max-w-2xl mx-auto">
          聚焦 A 股前沿行业 · 头部企业 · 产业链全景 · 材料缺口 · 市场前景
        </p>
      </div>

      {/* Sector Grid */}
      {sectors.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {sectors.map((sector) => (
            <SectorCard key={sector.slug} sector={sector} />
          ))}
        </div>
      ) : (
        <div className="text-center py-20">
          <div className="text-6xl mb-4">📡</div>
          <p className="text-xl text-gray-400 font-medium">暂无行业数据</p>
          <p className="mt-2 text-sm text-gray-400">
            在 <code className="bg-gray-100 px-1.5 py-0.5 rounded text-gray-600">content/sectors/</code> 目录下添加 Markdown 文件即可
          </p>
        </div>
      )}

      {/* Footer */}
      <footer className="mt-20 pt-8 border-t border-gray-200 text-center text-sm text-gray-400">
        <p>数据来源：公开研报、政府协会、行业榜单 · 仅供参考，不构成投资建议</p>
      </footer>
    </main>
  );
}
