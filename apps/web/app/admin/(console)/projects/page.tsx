"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { projectStatus } from "@/lib/money";
import { ADMIN_TOKEN, useToken } from "@/lib/session";
import type { Project } from "@/lib/types";

export default function ProjectsPage() {
  const { token } = useToken(ADMIN_TOKEN);
  const [projects, setProjects] = useState<Project[]>([]);

  useEffect(() => {
    if (!token) return;
    api<Project[]>("/api/admin/projects", { token }).then(setProjects);
  }, [token]);

  return (
    <div>
      <div className="row-actions" style={{ justifyContent: "space-between" }}>
        <h1>项目</h1>
        <Link className="btn" href="/admin/projects/new">
          新建项目
        </Link>
      </div>
      <table className="data">
        <thead>
          <tr>
            <th>名称</th>
            <th>编号</th>
            <th>状态</th>
            <th>户型</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {projects.map((project) => (
            <tr key={project.id}>
              <td>{project.name}</td>
              <td>{project.code}</td>
              <td>
                <span className={project.status === "published" ? "badge on" : "badge"}>{projectStatus(project.status)}</span>
              </td>
              <td>{project.unit_types.length}</td>
              <td>
                <Link href={`/admin/projects/${project.id}`}>查看</Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
