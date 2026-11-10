export default function CustomerLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="stage">
      <div className="phone">{children}</div>
    </div>
  );
}
