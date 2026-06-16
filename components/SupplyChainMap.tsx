'use client';

import { useEffect, useRef } from 'react';

interface SupplyChainMapProps {
  markdown: string;
}

export default function SupplyChainMap({ markdown }: SupplyChainMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement | null>(null);

  useEffect(() => {
    let mounted = true;

    async function renderMap() {
      if (!containerRef.current) return;

      try {
        const { Transformer } = await import('markmap-lib');
        const { Markmap } = await import('markmap-view');

        const transformer = new Transformer();
        const { root } = transformer.transform(markdown);

        // Clear previous content
        containerRef.current!.innerHTML = '';

        const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        svg.setAttribute('style', 'width:100%; height:100%;');
        containerRef.current!.appendChild(svg);

        if (mounted) {
          svgRef.current = svg;
          Markmap.create(svg, { autoFit: true } as Parameters<typeof Markmap.create>[1], root);
        }
      } catch (err) {
        console.error('Failed to render markmap:', err);
      }
    }

    renderMap();

    return () => {
      mounted = false;
    };
  }, [markdown]);

  return (
    <div
      ref={containerRef}
      className="w-full h-[500px] border border-gray-200 rounded-xl bg-white overflow-hidden"
    />
  );
}
