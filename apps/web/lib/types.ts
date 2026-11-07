export type MaterialSpec = {
  color: string;
  roughness: number;
  metalness: number;
  accent: string;
  feature: string;
};

export type SchemeItem = {
  id: string;
  name: string;
  room_name?: string;
  group_label?: string;
  display_part_id?: string | null;
  unit_price: number;
  default_quantity: number;
  sort_order: number;
};

export type Scheme = {
  id: string;
  style_id: string | null;
  part_id: string;
  index: number;
  name: string;
  summary: string;
  unit_price: number;
  is_default: boolean;
  items?: SchemeItem[];
  material: MaterialSpec;
};

export type ItemPick = {
  id: string;
  scheme_item_id: string;
  name: string;
  room_name?: string;
  group_label?: string;
  display_part_id?: string;
  unit_price: number;
  included: boolean;
  quantity: number;
  brand_tier: "domestic" | "import" | null;
};

export type PartGroup = {
  id: string;
  name: string;
  schemes: Scheme[];
};

export type Style = {
  id: string;
  name: string;
  tagline: string;
  description: string;
  palette: string[];
  parts: PartGroup[];
};

export type Room = {
  id: string;
  name: string;
  area_m2: number;
  counts_toward_finish: boolean;
};

export type Asset = {
  id: string;
  project_id: string;
  unit_type_id: string | null;
  selection_id: string | null;
  kind: string;
  kind_label: string;
  filename: string;
  content_type: string;
  byte_size: number;
  status: string;
  note: string;
  created_at: string;
};

export type UnitType = {
  id: string;
  project_id: string;
  code: string;
  name: string;
  building_area_m2: number;
  finish_area_m2: number;
  area_basis: string;
  area_note: string;
  bedrooms: number;
  living_rooms: number;
  kitchens: number;
  bathrooms: number;
  summary: string;
  excluded_rooms: string[];
  rooms: Room[];
  assets: Asset[];
};

export type Project = {
  id: string;
  code: string;
  name: string;
  developer: string;
  city: string;
  district: string;
  address: string;
  description: string;
  status: string;
  hard_cost_per_m2: number;
  soft_cost_per_m2: number;
  unit_types: UnitType[];
};

export type QuoteLine = {
  part_id: string;
  part_name: string;
  scheme_id: string | null;
  scheme_name: string | null;
  unit_price: number | null;
  area_m2: number;
  amount: number;
  pricing?: "area" | "each";
  quantity?: number;
  brand_tier?: "domestic" | "import" | null;
};

export type CatalogPart = {
  id: string;
  name: string;
  sort_order: number;
  pricing: "area" | "each";
  visual: boolean;
  allows_brand_tier: boolean;
  schemes: Scheme[];
};

export type SelectionLine = {
  id: string;
  part_id: string;
  part_name: string;
  room_or_zone: string;
  scheme_id: string | null;
  scheme_name: string | null;
  procurement_item_id: string | null;
  brand_tier: "domestic" | "import" | null;
  quantity: number;
  picks?: ItemPick[];
};

export type Quote = {
  finish_area_m2: number;
  area_basis: string;
  area_note: string;
  excluded_rooms: string[];
  lines: QuoteLine[];
  total: number;
  reference: {
    building_area_m2: number;
    hard_cost_per_m2: number;
    soft_cost_per_m2: number;
    hard_total: number;
    soft_total: number;
    note: string;
  };
};

export type Selection = {
  id: string;
  status: string;
  customer_phone: string;
  customer_name: string;
  project: {
    id: string;
    code: string;
    name: string;
    developer: string;
    city: string;
    district: string;
    address: string;
    status: string;
    hard_cost_per_m2: number;
    soft_cost_per_m2: number;
  };
  unit: UnitType;
  style: Style | null;
  ceiling: Scheme | null;
  floor: Scheme | null;
  wall: Scheme | null;
  parts: CatalogPart[];
  lines: SelectionLine[];
  quote: Quote;
  created_at: string;
  updated_at: string;
};

export type SelectionListItem = {
  id: string;
  status: string;
  customer_phone: string;
  customer_name: string;
  project_id: string;
  project_code: string;
  project_name: string;
  unit_id: string;
  unit_name: string;
  style_id: string | null;
  style_name: string | null;
  total: number;
  updated_at: string;
};

export type Overview = {
  projects: number;
  published_projects: number;
  selections: number;
  submitted_selections: number;
  procurement_tables: number;
  procurement_items: number;
  placeholder_drawings: number;
  recent_selections: SelectionListItem[];
};

export type ProcurementItem = {
  id: string;
  category: string;
  category_label: string;
  sku_code: string;
  name: string;
  spec: string;
  brand: string;
  unit: string;
  unit_price: number;
  remark: string;
};

export type ProcurementTable = {
  id: string;
  project_id: string | null;
  category: string;
  category_label: string;
  title: string;
  original_filename: string;
  row_count: number;
  created_at: string;
  items?: ProcurementItem[];
};

export type AiJob = {
  id: string;
  kind: string;
  status: string;
  selection_id: string | null;
  message: string;
  provider: string;
  result: Record<string, unknown>;
};

export type Meta = {
  procurement_categories: { id: string; name: string }[];
  asset_kinds: { id: string; name: string }[];
};

export type ExportTicket = {
  id: string;
  kind: string;
  filename: string;
  content_type: string;
  status: string;
};
