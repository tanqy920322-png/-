"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import { ADMIN_TOKEN, useToken } from "@/lib/session";

export default function AdminLoginPage() {
  const router = useRouter();
  const { setToken } = useToken(ADMIN_TOKEN);
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("demo1234");
  const [error, setError] = useState("");

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setError("");
    try {
      const result = await api<{ token: string }>("/api/admin/login", {
        method: "POST",
        body: JSON.stringify({ username, password }),
      });
      setToken(result.token);
      router.push("/admin");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "登录失败");
    }
  }

  return (
    <main className="landing">
      <p className="kicker">开发商后台</p>
      <h1>登录</h1>
      <form className="stack" onSubmit={submit} style={{ maxWidth: 420 }}>
        <label className="field">
          账号
          <input value={username} onChange={(event) => setUsername(event.target.value)} />
        </label>
        <label className="field">
          密码
          <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} />
        </label>
        {error ? <p className="error">{error}</p> : null}
        <button type="submit">进入后台</button>
        <p className="fine">本地默认账号 admin / demo1234，只用于演示。</p>
      </form>
    </main>
  );
}
