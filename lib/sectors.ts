import fs from 'fs';
import path from 'path';
import matter from 'gray-matter';

export interface Alert {
  date: string;
  text: string;
  companies: string[];
}

export interface SectorMeta {
  sector: string;
  slug: string;
  tags: string[];
  stocks: string[];
  updated: string;
  alertCount: number;
  relatedSectors?: string[]; // slug list of related sectors
}

export interface Company {
  rank: number;
  name: string;
  business: string;
  region: string;
  advantage: string;
  hasAlert: boolean;
}

export interface MaterialGap {
  material: string;
  gapLevel: string;
  localization: string;
  suppliers: string;
}

export interface MarketData {
  years: string[];
  values: number[];
  unit: string;
  label: string;
}

export interface SectorData {
  meta: SectorMeta;
  content: string;
  alerts: Alert[];
  companies: Company[];
  materials: MaterialGap[];
  marketData: MarketData | null;
  supplyChain: string | null;
}

function formatDate(val: unknown): string {
  if (!val) return '';
  if (val instanceof Date) {
    return val.toISOString().split('T')[0];
  }
  return String(val);
}

function parseAlerts(raw: unknown): Alert[] {
  if (!Array.isArray(raw)) return [];
  return raw.map((a: Record<string, unknown>) => ({
    date: formatDate(a.date),
    text: String(a.text || ''),
    companies: Array.isArray(a.companies) ? a.companies.map(String) : [],
  }));
}

/** Only count alerts from the last 14 days for badge display */
const ALERT_DAYS = 14;
function getActiveAlerts(alerts: Alert[]): Alert[] {
  const cutoff = new Date();
  cutoff.setDate(cutoff.getDate() - ALERT_DAYS);
  return alerts.filter((a) => {
    const d = new Date(a.date);
    return !isNaN(d.getTime()) && d >= cutoff;
  });
}

const SECTORS_DIR = path.join(process.cwd(), 'content', 'sectors');

export function getAllSectors(): SectorMeta[] {
  if (!fs.existsSync(SECTORS_DIR)) return [];
  const files = fs
    .readdirSync(SECTORS_DIR)
    .filter((f) => f.endsWith('.md'));
  return files.map((file) => {
    const raw = fs.readFileSync(path.join(SECTORS_DIR, file), 'utf-8');
    const { data } = matter(raw);
    const alerts = parseAlerts(data.alerts);
    return {
      sector: data.sector || file.replace('.md', ''),
      slug: data.slug || file.replace('.md', ''),
      tags: data.tags || [],
      stocks: data.stocks || [],
      updated: formatDate(data.updated),
      alertCount: getActiveAlerts(alerts).length,
      relatedSectors: data.relatedSectors || [],
    } as SectorMeta;
  });
}

export function getSectorBySlug(slug: string): SectorData | null {
  let filePath = path.join(SECTORS_DIR, `${slug}.md`);
  if (!fs.existsSync(filePath)) {
    const files = fs.readdirSync(SECTORS_DIR).filter((f) => f.endsWith('.md'));
    for (const file of files) {
      const raw = fs.readFileSync(path.join(SECTORS_DIR, file), 'utf-8');
      const { data } = matter(raw);
      if (data.slug === slug) {
        filePath = path.join(SECTORS_DIR, file);
        break;
      }
    }
    if (!fs.existsSync(filePath)) return null;
  }

  const raw = fs.readFileSync(filePath, 'utf-8');
  const { data, content } = matter(raw);

  const alerts = parseAlerts(data.alerts);
  const activeAlerts = getActiveAlerts(alerts);
  const alertedCompanyNames = new Set(activeAlerts.flatMap((a) => a.companies));

  // Parse companies table from content
  const rawCompanies = parseTable(content, '头部企业', [
    'rank',
    'name',
    'business',
    'region',
    'advantage',
  ]) as unknown as Company[];

  // Add alert flag to companies
  const companies = rawCompanies.map((c) => ({
    ...c,
    hasAlert: alertedCompanyNames.has(c.name),
  }));

  // Parse material gaps: prefer YAML frontmatter, fallback to table parsing
  const materials =
    (data.materials as MaterialGap[] | undefined) ||
    (parseTable(content, '关键材料', [
      'material',
      'gapLevel',
      'localization',
      'suppliers',
    ]) as unknown as MaterialGap[]);

  const marketData = data.marketData || null;
  const supplyChain = data.supplyChain || null;

  return {
    meta: {
      sector: data.sector || slug,
      slug: data.slug || slug,
      tags: data.tags || [],
      stocks: data.stocks || [],
      updated: formatDate(data.updated),
      alertCount: activeAlerts.length,
      relatedSectors: data.relatedSectors || [],
    },
    content,
    alerts,
    companies,
    materials,
    marketData,
    supplyChain,
  };
}

function parseTable(
  content: string,
  sectionKeyword: string,
  columns: string[]
): Record<string, unknown>[] {
  const lines = content.split('\n');
  let inSection = false;
  const tableLines: string[] = [];

  for (const line of lines) {
    if (line.startsWith('## ' + sectionKeyword)) {
      inSection = true;
      continue;
    }
    if (inSection && line.startsWith('## ')) break;
    if (inSection && line.trim().startsWith('|') && line.trim().endsWith('|')) {
      tableLines.push(line.trim());
    }
  }

  if (tableLines.length < 3) return [];

  const dataRows = tableLines.filter((l) => {
    const stripped = l.replace(/\|/g, '').trim();
    return !/^[-:\s]+$/.test(stripped);
  });

  if (dataRows.length < 2) return [];

  return dataRows.slice(1).map((row) => {
    const cells = row
      .split('|')
      .map((c) => c.trim())
      .filter((c) => c !== '');
    const obj: Record<string, unknown> = {};
    columns.forEach((col, i) => {
      const val = cells[i] || '';
      if (col === 'rank') {
        obj[col] = parseInt(val, 10) || 0;
      } else {
        obj[col] = val;
      }
    });
    return obj;
  });
}
