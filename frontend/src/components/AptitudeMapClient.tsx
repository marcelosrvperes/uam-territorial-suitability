"use client";

import dynamic from "next/dynamic";

// Leaflet touches `window` at import time — must load client-side only.
// `ssr: false` requires this wrapper to itself be a Client Component.
const AptitudeMap = dynamic(() => import("./AptitudeMap"), { ssr: false });

export default function AptitudeMapClient() {
  return <AptitudeMap />;
}
