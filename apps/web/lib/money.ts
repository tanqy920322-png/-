import type { Scheme, Selection } from "./types";

export function yuan(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—";
  return new Intl.NumberFormat("zh-CN", {
    style: "currency",
    currency: "CNY",
    minimumFractionDigits: 2,
  }).format(value);
}

export function mulMoney(unitPrice: number, area: number): number {
  const priceCents = Math.round(unitPrice * 100);
  const areaHundredths = Math.round(area * 100);
  return Math.round((priceCents * areaHundredths) / 100) / 100;
}

export function projectStatus(status: string): string {
  return status === "published" ? "已发布" : "草稿";
}

export function selectionStatus(status: string): string {
  return status === "submitted" ? "已提交" : "选配中";
}

export function formatWhen(value: string): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("zh-CN", { hour12: false });
}

export function withScheme(selection: Selection, scheme: Scheme): Selection {
  const next: Selection = {
    ...selection,
    ceiling: scheme.part_id === "ceiling" ? scheme : selection.ceiling,
    floor: scheme.part_id === "floor" ? scheme : selection.floor,
    wall: scheme.part_id === "wall" ? scheme : selection.wall,
  };
  const area = selection.quote.finish_area_m2;
  const parts = [
    ["ceiling", "天花", next.ceiling],
    ["floor", "地面", next.floor],
    ["wall", "墙面", next.wall],
  ] as const;
  const finishLines = parts.map(([id, name, item]) => {
    const unit = item?.unit_price ?? 0;
    return {
      part_id: id,
      part_name: name,
      scheme_id: item?.id ?? null,
      scheme_name: item?.name ?? null,
      unit_price: item ? unit : null,
      area_m2: area,
      amount: item ? mulMoney(unit, area) : 0,
      pricing: "area" as const,
      quantity: 1,
    };
  });
  const extras = selection.quote.lines.filter((line) => line.pricing === "each");
  const lines = [...finishLines, ...extras];
  const total = Math.round(lines.reduce((sum, line) => sum + line.amount, 0) * 100) / 100;
  return { ...next, quote: { ...selection.quote, lines, total } };
}
