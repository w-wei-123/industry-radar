import Link from 'next/link';
import { getAllSectors } from '@/lib/sectors';

export default function RelatedSectors({ slugs }: { slugs: string[] }) {
  if (!slugs || slugs.length === 0) return null;

  const all = getAllSectors();
  const nameMap = new Map(all.map((s) => [s.slug, s.sector]));

  return (
    <section className="mb-12">
      <h2 className="text-2xl font-bold text-gray-900 mb-4">🔗 关联板块</h2>
      <p className="text-sm text-gray-500 mb-3">
        Serenity方法论：产业链传导——这个板块的上下游在哪里
      </p>
      <div className="flex flex-wrap gap-2">
        {slugs.map((slug) => {
          const name = nameMap.get(slug) || slug;
          return (
            <Link
              key={slug}
              href={`/sector/${slug}`}
              className="inline-flex items-center px-4 py-2 rounded-lg border border-gray-200 bg-white text-sm text-gray-700 hover:border-blue-400 hover:text-blue-600 hover:shadow-sm transition-all"
            >
              {name}
              <span className="ml-1.5 text-blue-400">→</span>
            </Link>
          );
        })}
      </div>
    </section>
  );
}
