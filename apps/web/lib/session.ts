"use client";

import { useEffect, useState } from "react";

export const CUSTOMER_TOKEN = "fitout_customer_token";
export const ADMIN_TOKEN = "fitout_admin_token";

export function useToken(key: string) {
  const [token, setTokenState] = useState<string | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    setTokenState(window.localStorage.getItem(key));
    setReady(true);
  }, [key]);

  function setToken(value: string | null) {
    if (value) window.localStorage.setItem(key, value);
    else window.localStorage.removeItem(key);
    setTokenState(value);
  }

  return { token, ready, setToken };
}

export function useQueryParam(name: string): string | null {
  const [value, setValue] = useState<string | null>(null);
  useEffect(() => {
    setValue(new URLSearchParams(window.location.search).get(name));
  }, [name]);
  return value;
}
