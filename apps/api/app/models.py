from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    developer: Mapped[str] = mapped_column(String(200), default="")
    city: Mapped[str] = mapped_column(String(80), default="")
    district: Mapped[str] = mapped_column(String(80), default="")
    address: Mapped[str] = mapped_column(String(300), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="draft", index=True)
    hard_cost_per_m2: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    soft_cost_per_m2: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    units: Mapped[list["UnitType"]] = relationship(back_populates="project", cascade="all, delete-orphan")


class UnitType(Base):
    __tablename__ = "unit_types"
    __table_args__ = (UniqueConstraint("project_id", "code", name="uq_unit_code"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    code: Mapped[str] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(80))
    building_area_m2: Mapped[float] = mapped_column(Numeric(8, 2))
    finish_area_override: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    bedrooms: Mapped[int] = mapped_column(Integer, default=0)
    living_rooms: Mapped[int] = mapped_column(Integer, default=0)
    kitchens: Mapped[int] = mapped_column(Integer, default=0)
    bathrooms: Mapped[int] = mapped_column(Integer, default=0)
    summary: Mapped[str] = mapped_column(String(80), default="")

    project: Mapped[Project] = relationship(back_populates="units")
    rooms: Mapped[list["Room"]] = relationship(
        back_populates="unit",
        cascade="all, delete-orphan",
        order_by="Room.sort_order",
    )


class Room(Base):
    __tablename__ = "rooms"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    unit_type_id: Mapped[str] = mapped_column(ForeignKey("unit_types.id"), index=True)
    name: Mapped[str] = mapped_column(String(40))
    area_m2: Mapped[float] = mapped_column(Numeric(8, 2))
    counts_toward_finish: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    unit: Mapped[UnitType] = relationship(back_populates="rooms")


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    unit_type_id: Mapped[str | None] = mapped_column(ForeignKey("unit_types.id"), nullable=True, index=True)
    selection_id: Mapped[str | None] = mapped_column(ForeignKey("customer_selections.id"), nullable=True, index=True)
    kind: Mapped[str] = mapped_column(String(32))
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(128), default="application/octet-stream")
    byte_size: Mapped[int] = mapped_column(Integer, default=0)
    storage_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="placeholder")
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Part(Base):
    __tablename__ = "parts"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(40))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    pricing_mode: Mapped[str] = mapped_column(String(16), default="area")
    allows_brand_tier: Mapped[bool] = mapped_column(Boolean, default=False)
    visual: Mapped[bool] = mapped_column(Boolean, default=False)


class Style(Base):
    __tablename__ = "styles"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(40))
    tagline: Mapped[str] = mapped_column(String(80), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    palette: Mapped[list] = mapped_column(JSON, default=list)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class Scheme(Base):
    __tablename__ = "schemes"
    __table_args__ = (UniqueConstraint("style_id", "part_id", "scheme_index", name="uq_scheme_slot"),)

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    style_id: Mapped[str | None] = mapped_column(ForeignKey("styles.id"), nullable=True, index=True)
    part_id: Mapped[str] = mapped_column(ForeignKey("parts.id"), index=True)
    scheme_index: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(80))
    summary: Mapped[str] = mapped_column(Text, default="")
    unit_price: Mapped[float] = mapped_column(Numeric(12, 2))
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    material: Mapped[dict] = mapped_column(JSON, default=dict)
    items: Mapped[list["SchemeItem"]] = relationship(
        back_populates="scheme",
        cascade="all, delete-orphan",
        order_by="SchemeItem.sort_order",
    )


class SchemeItem(Base):
    """A piece inside a scheme. Every category uses the same kit: brand, include, quantity."""

    __tablename__ = "scheme_items"

    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    scheme_id: Mapped[str] = mapped_column(ForeignKey("schemes.id"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    room_name: Mapped[str] = mapped_column(String(40), default="")
    group_label: Mapped[str] = mapped_column(String(80), default="")
    display_part_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    unit_price: Mapped[float] = mapped_column(Numeric(12, 2))
    default_quantity: Mapped[float] = mapped_column(Numeric(8, 2), default=1)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    scheme: Mapped[Scheme] = relationship(back_populates="items")


class ProcurementTable(Base):
    __tablename__ = "procurement_tables"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id"), nullable=True, index=True)
    category: Mapped[str] = mapped_column(String(32), index=True)
    title: Mapped[str] = mapped_column(String(200))
    original_filename: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    items: Mapped[list["ProcurementItem"]] = relationship(
        back_populates="table",
        cascade="all, delete-orphan",
    )


class ProcurementItem(Base):
    __tablename__ = "procurement_items"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    table_id: Mapped[str] = mapped_column(ForeignKey("procurement_tables.id"), index=True)
    category: Mapped[str] = mapped_column(String(32), index=True)
    sku_code: Mapped[str] = mapped_column(String(64), default="")
    name: Mapped[str] = mapped_column(String(200))
    spec: Mapped[str] = mapped_column(String(200), default="")
    brand: Mapped[str] = mapped_column(String(80), default="")
    unit: Mapped[str] = mapped_column(String(20), default="")
    unit_price: Mapped[float] = mapped_column(Numeric(12, 2))
    remark: Mapped[str] = mapped_column(Text, default="")

    table: Mapped[ProcurementTable] = relationship(back_populates="items")


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    phone: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(40), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class OtpChallenge(Base):
    __tablename__ = "otp_challenges"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    phone: Mapped[str] = mapped_column(String(20), index=True)
    code: Mapped[str] = mapped_column(String(8))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CustomerSelection(Base):
    __tablename__ = "customer_selections"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    unit_type_id: Mapped[str] = mapped_column(ForeignKey("unit_types.id"), index=True)
    style_id: Mapped[str | None] = mapped_column(ForeignKey("styles.id"), nullable=True)
    ceiling_scheme_id: Mapped[str | None] = mapped_column(ForeignKey("schemes.id"), nullable=True)
    floor_scheme_id: Mapped[str | None] = mapped_column(ForeignKey("schemes.id"), nullable=True)
    wall_scheme_id: Mapped[str | None] = mapped_column(ForeignKey("schemes.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="draft", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    customer: Mapped[Customer] = relationship()
    project: Mapped[Project] = relationship()
    unit: Mapped[UnitType] = relationship()
    style: Mapped[Style | None] = relationship()
    ceiling_scheme: Mapped[Scheme | None] = relationship(foreign_keys=[ceiling_scheme_id])
    floor_scheme: Mapped[Scheme | None] = relationship(foreign_keys=[floor_scheme_id])
    wall_scheme: Mapped[Scheme | None] = relationship(foreign_keys=[wall_scheme_id])
    lines: Mapped[list["SelectionLine"]] = relationship(
        back_populates="selection",
        cascade="all, delete-orphan",
    )


class SelectionLine(Base):
    """One chosen SKU or scheme for any of the nine categories.

    Ceiling, floor, and wall are also mirrored on CustomerSelection so older
    clients and sel_demo keep working. Other categories live only here.
    """

    __tablename__ = "selection_lines"
    __table_args__ = (UniqueConstraint("selection_id", "part_id", "room_or_zone", name="uq_selection_line"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    selection_id: Mapped[str] = mapped_column(ForeignKey("customer_selections.id"), index=True)
    part_id: Mapped[str] = mapped_column(ForeignKey("parts.id"), index=True)
    room_or_zone: Mapped[str] = mapped_column(String(40), default="")
    scheme_id: Mapped[str | None] = mapped_column(ForeignKey("schemes.id"), nullable=True)
    procurement_item_id: Mapped[str | None] = mapped_column(ForeignKey("procurement_items.id"), nullable=True)
    brand_tier: Mapped[str | None] = mapped_column(String(16), nullable=True)
    quantity: Mapped[float] = mapped_column(Numeric(8, 2), default=1)

    selection: Mapped[CustomerSelection] = relationship(back_populates="lines")
    part: Mapped[Part] = relationship()
    scheme: Mapped[Scheme | None] = relationship()
    procurement_item: Mapped[ProcurementItem | None] = relationship()
    picks: Mapped[list["SelectionItemPick"]] = relationship(
        back_populates="line",
        cascade="all, delete-orphan",
    )


class SelectionItemPick(Base):
    __tablename__ = "selection_item_picks"
    __table_args__ = (UniqueConstraint("selection_line_id", "scheme_item_id", name="uq_line_item"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    selection_line_id: Mapped[str] = mapped_column(ForeignKey("selection_lines.id"), index=True)
    scheme_item_id: Mapped[str] = mapped_column(ForeignKey("scheme_items.id"), index=True)
    included: Mapped[bool] = mapped_column(Boolean, default=False)
    quantity: Mapped[float] = mapped_column(Numeric(8, 2), default=1)
    brand_tier: Mapped[str | None] = mapped_column(String(16), nullable=True)
    product_id: Mapped[str | None] = mapped_column(ForeignKey("catalog_products.id"), nullable=True)

    line: Mapped[SelectionLine] = relationship(back_populates="picks")
    item: Mapped[SchemeItem] = relationship()
    product: Mapped["CatalogProduct | None"] = relationship()


class CatalogProduct(Base):
    """Example SKU. Names and pictures are made for this prototype, not brand photography."""

    __tablename__ = "catalog_products"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    part_id: Mapped[str] = mapped_column(ForeignKey("parts.id"), index=True)
    brand: Mapped[str] = mapped_column(String(80))
    model_code: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(120))
    spec: Mapped[str] = mapped_column(String(200), default="")
    width_mm: Mapped[int] = mapped_column(Integer, default=0)
    depth_mm: Mapped[int] = mapped_column(Integer, default=0)
    height_mm: Mapped[int] = mapped_column(Integer, default=0)
    domestic_price: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    import_price: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    status: Mapped[str] = mapped_column(String(16), default="confirmed", index=True)
    example: Mapped[bool] = mapped_column(Boolean, default=True)
    source: Mapped[str] = mapped_column(String(24), default="preset")
    note: Mapped[str] = mapped_column(Text, default="")


class ProjectBinding(Base):
    """A product hung on a project room and part by the fit-out engineer."""

    __tablename__ = "project_bindings"
    __table_args__ = (
        UniqueConstraint("project_id", "unit_type_id", "room_name", "part_id", name="uq_project_binding"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    unit_type_id: Mapped[str | None] = mapped_column(ForeignKey("unit_types.id"), nullable=True)
    room_name: Mapped[str] = mapped_column(String(40), default="")
    part_id: Mapped[str] = mapped_column(ForeignKey("parts.id"), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("catalog_products.id"))
    note: Mapped[str] = mapped_column(String(200), default="")

    product: Mapped[CatalogProduct] = relationship()


class LibraryModel(Base):
    __tablename__ = "library_models"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id"), nullable=True, index=True)
    filename: Mapped[str] = mapped_column(String(255))
    format: Mapped[str] = mapped_column(String(8))
    storage_key: Mapped[str] = mapped_column(String(512))
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class VisualSubstitute(Base):
    """A customer photo on a typical-category mesh. Display only: never priced or ordered."""

    __tablename__ = "visual_substitutes"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    selection_id: Mapped[str] = mapped_column(ForeignKey("customer_selections.id"), index=True)
    part_id: Mapped[str] = mapped_column(String(32), index=True)
    room_name: Mapped[str] = mapped_column(String(40), default="")
    slot_label: Mapped[str] = mapped_column(String(40), default="")
    width_mm: Mapped[int] = mapped_column(Integer, default=0)
    depth_mm: Mapped[int] = mapped_column(Integer, default=0)
    height_mm: Mapped[int] = mapped_column(Integer, default=0)
    primary_asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id"))
    secondary_asset_id: Mapped[str | None] = mapped_column(ForeignKey("assets.id"), nullable=True)
    demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PlanSheet(Base):
    """A simplified plan the engineer marks by hand. Not a parsed construction drawing."""

    __tablename__ = "plan_sheets"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    unit_type_id: Mapped[str] = mapped_column(ForeignKey("unit_types.id"), index=True)
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id"))
    filename: Mapped[str] = mapped_column(String(255))
    media: Mapped[str] = mapped_column(String(16))
    vectors: Mapped[list] = mapped_column(JSON, default=list)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    marks: Mapped[list["PlanMark"]] = relationship(
        back_populates="plan",
        cascade="all, delete-orphan",
    )


class PlanMark(Base):
    """One click on a simplified plan: a room or a part slot. Humans mark, the system places."""

    __tablename__ = "plan_marks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    plan_id: Mapped[str] = mapped_column(ForeignKey("plan_sheets.id"), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    unit_type_id: Mapped[str] = mapped_column(ForeignKey("unit_types.id"), index=True)
    room_name: Mapped[str] = mapped_column(String(40))
    part_id: Mapped[str] = mapped_column(String(32))
    slot_label: Mapped[str] = mapped_column(String(40), default="")
    x: Mapped[float] = mapped_column(Float)
    y: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    plan: Mapped[PlanSheet] = relationship(back_populates="marks")


class WorkerJob(Base):
    __tablename__ = "worker_jobs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    kind: Mapped[str] = mapped_column(String(40), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    selection_id: Mapped[str | None] = mapped_column(ForeignKey("customer_selections.id"), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class ExportArtifact(Base):
    __tablename__ = "export_artifacts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    selection_id: Mapped[str] = mapped_column(ForeignKey("customer_selections.id"), index=True)
    kind: Mapped[str] = mapped_column(String(32))
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(128))
    storage_key: Mapped[str] = mapped_column(String(512))
    status: Mapped[str] = mapped_column(String(32), default="ready")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
