"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { ADMIN_TOKEN, useToken } from "@/lib/session";

const LINKS = [
  { href: "/admin", label: "概览" },
  { href: "/admin/projects", label: "项目" },
  { href: "/admin/prices", label: "集采价表" },
  { href: "/admin/selections", label: "客户方案" },
];

export default function ConsoleLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { token, ready, setToken } = useToken(ADMIN_TOKEN);

  useEffect(() => {
    if (ready && !token) router.replace("/admin/login");
  }, [ready, token, router]);

  if (!ready || !token) return <p className="muted" style={{ padding: 24 }}>正在进入后台…</p>;

  return (
    <div className="admin-shell">
      <aside className="admin-side">
        <strong>精装选配</strong>
        {LINKS.map((link) => {
          const on = link.href === "/admin" ? pathname === "/admin" : pathname.startsWith(link.href);
          return (
            <Link key={link.href} href={link.href} className={on ? "on" : ""}>
              {link.label}
            </Link>
          );
        })}
        <button
          className="logout"
          type="button"
          onClick={() => {
            setToken(null);
            router.replace("/admin/login");
          }}
        >
          退出
        </button>
      </aside>
      <div className="admin-main">{children}</div>
    </div>
  );
}
