import type { CandleOut, SwingPoint, Zone } from "../types/market";

const WIDTH = 900;
const HEIGHT = 320;
const PADDING = 30;

export function MarketChart({
  candles,
  swingHighs,
  swingLows,
  supports,
  resistances,
}: {
  candles: CandleOut[];
  swingHighs: SwingPoint[];
  swingLows: SwingPoint[];
  supports: Zone[];
  resistances: Zone[];
}) {
  if (candles.length === 0) {
    return <p>Sem candles para desenhar o gráfico.</p>;
  }

  const timestampIndex = new Map(candles.map((c, i) => [c.timestamp, i]));
  const closes = candles.map((c) => c.close);

  const allPrices = [
    ...closes,
    ...supports.flatMap((z) => [z.lower_bound, z.upper_bound]),
    ...resistances.flatMap((z) => [z.lower_bound, z.upper_bound]),
  ];
  const min = Math.min(...allPrices);
  const max = Math.max(...allPrices);
  const range = max - min || 1;

  const stepX = (WIDTH - PADDING * 2) / Math.max(candles.length - 1, 1);
  const x = (i: number) => PADDING + i * stepX;
  const y = (price: number) => HEIGHT - PADDING - ((price - min) / range) * (HEIGHT - PADDING * 2);

  const pricePath = closes.map((c, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(2)},${y(c).toFixed(2)} `).join("");

  function zoneBand(zone: Zone, color: string, key: string) {
    return (
      <rect
        key={key}
        x={PADDING}
        y={y(zone.upper_bound)}
        width={WIDTH - PADDING * 2}
        height={Math.max(y(zone.lower_bound) - y(zone.upper_bound), 1)}
        fill={color}
        opacity={0.15}
      />
    );
  }

  // Draws BOTH the occurrence marker (hollow) and the confirmation marker
  // (filled), connected by a dashed line — the point is to never hide the gap
  // between "this happened" and "we found out" (Sprint 4 section 51).
  function swingMarkers(swings: SwingPoint[], color: string, keyPrefix: string) {
    return swings.flatMap((swing, i) => {
      const occIdx = timestampIndex.get(swing.timestamp);
      const confIdx = timestampIndex.get(swing.confirmation_timestamp);
      if (occIdx === undefined || confIdx === undefined) return [];

      const py = y(swing.price);
      return [
        <line
          key={`${keyPrefix}-line-${i}`}
          x1={x(occIdx)}
          y1={py}
          x2={x(confIdx)}
          y2={py}
          stroke={color}
          strokeDasharray="3,3"
          strokeWidth={1}
        />,
        <circle key={`${keyPrefix}-occ-${i}`} cx={x(occIdx)} cy={py} r={3} fill="none" stroke={color} strokeWidth={1.5} />,
        <circle key={`${keyPrefix}-conf-${i}`} cx={x(confIdx)} cy={py} r={3} fill={color} />,
      ];
    });
  }

  return (
    <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} className="line-chart" role="img" aria-label="Gráfico de estrutura de mercado">
      <rect x={0} y={0} width={WIDTH} height={HEIGHT} className="line-chart__background" />
      {supports.map((z, i) => zoneBand(z, "#1a7f37", `support-${i}`))}
      {resistances.map((z, i) => zoneBand(z, "#cf222e", `resistance-${i}`))}
      <path d={pricePath} fill="none" stroke="#333" strokeWidth={1.5} />
      {swingMarkers(swingHighs, "#0969da", "high")}
      {swingMarkers(swingLows, "#9a6700", "low")}
    </svg>
  );
}
