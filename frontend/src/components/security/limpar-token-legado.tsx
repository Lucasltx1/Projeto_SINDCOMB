"use client";

import { useEffect } from "react";

export function LimparTokenLegado() {
  useEffect(() => {
    window.sessionStorage.removeItem("sindcomb_access_token");
    window.localStorage.removeItem("sindcomb_access_token");
  }, []);

  return null;
}
