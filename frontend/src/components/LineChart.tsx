export interface ChartSeries {
  name: string;
  color: string;
  values: (number | null)[];
}

const WIDTH = 800;
const HEIGHT = 220;
const PADDING = 24;

function toPath(values: (number | null)[], min: number, max: number): string {
  const range = max - min || 1;
  const stepX = (WIDTH - PADDING * 2) / Math.max(values.length - 1, 1);

  let path = "";
  let drawing = false;

  values.forEach((value, i) => {
    if (value === null) {
      drawing = false;
      return;
    }
    const x = PADDING + i * stepX;
    const y = HEIGHT - PADDING - ((value - min) / range) * (HEIGHT - PADDING * 2);
    path += `${drawing ? "L" : "M"}${x.toFixed(2)},${y.toFixed(2)} `;
    drawing = true;
  });

  return path;
}

export function LineChart({ series }: { series: ChartSeries[] }) {
  const allValues = series.flatMap((s) => s.values).filter((v): v is number => v !== null);
  if (allValues.length === 0) {
    return <p>Sem dados suficientes para desenhar o gráfico.</p>;
  }

  const min = Math.min(...allValues);
  const max = Math.max(...allValues);

  return (
    <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} className="line-chart" role="img" aria-label="Gráfico de indicadores">
      <rect x={0} y={0} width={WIDTH} height={HEIGHT} className="line-chart__background" />
      {series.map((s) => (
        <path key={s.name} d={toPath(s.values, min, max)} fill="none" stroke={s.color} strokeWidth={1.5} />
      ))}
    </svg>
  );
}
