"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import { CUSTOMER_TOKEN, useToken } from "@/lib/session";

export default function LoginPage() {
  const router = useRouter();
  const { setToken } = useToken(CUSTOMER_TOKEN);
  const [phone, setPhone] = useState("13800138000");
  const [code, setCode] = useState("");
  const [hint, setHint] = useState("测试环境不发短信。点获取验证码后会填入 123456。");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function requestCode() {
    setError("");
    setBusy(true);
    try {
      const result = await api<{ dev_code: string; message: string }>("/api/auth/otp/request", {
        method: "POST",
        body: JSON.stringify({ phone }),
      });
      setCode(result.dev_code);
      setHint(result.message);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "获取验证码失败");
    } finally {
      setBusy(false);
    }
  }

  async function verify() {
    setError("");
    setBusy(true);
    try {
      const result = await api<{ token: string }>("/api/auth/otp/verify", {
        method: "POST",
        body: JSON.stringify({ phone, code }),
      });
      setToken(result.token);
      router.push("/c/match");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "登录失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="stack">
      <header className="phone-bar">
        <span />
        <h1>手机号登录</h1>
        <span />
      </header>
      <p className="muted">用手机号进入选配。演示客户 13800138000 已经有一套轻奢方案。</p>
      <label className="field">
        手机号
        <input inputMode="numeric" maxLength={11} value={phone} onChange={(event) => setPhone(event.target.value)} />
      </label>
      <label className="field">
        验证码
        <input inputMode="numeric" maxLength={6} value={code} onChange={(event) => setCode(event.target.value)} />
      </label>
      <p className="fine">{hint}</p>
      {error ? <p className="error">{error}</p> : null}
      <div className="row-actions">
        <button className="secondary" type="button" disabled={busy} onClick={requestCode}>
          获取验证码
        </button>
        <button type="button" disabled={busy || code.length < 4} onClick={verify}>
          进入选配
        </button>
      </div>
    </div>
  );
}
