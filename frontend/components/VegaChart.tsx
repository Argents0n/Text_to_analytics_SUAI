"use client";

import dynamic from "next/dynamic";

// react-vega v8 exposes VegaEmbed (vega-embed wrapper). Load client-only.
const VegaEmbed = dynamic(() => import("react-vega").then((m) => m.VegaEmbed), { ssr: false });

export function VegaChart({ spec }: { spec: object }) {
  const responsive = { ...(spec as Record<string, unknown>), width: "container" };
  return (
    <div className="w-full overflow-x-auto">
      <VegaEmbed
        spec={responsive as never}
        options={{ actions: false, renderer: "svg" }}
        className="w-full"
      />
    </div>
  );
}
