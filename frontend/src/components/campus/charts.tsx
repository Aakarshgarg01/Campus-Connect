import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { Contribution } from "@/services/types";

const axisTick = { fontSize: 12, fill: "var(--muted-foreground)" };
const tooltipStyle = {
  border: "1px solid var(--border)",
  borderRadius: 6,
  boxShadow: "var(--shadow-sm)",
  fontSize: 13,
};

export function PredictionChart({
  data,
  target,
  targetLabel = "Target",
}: {
  data: { stage: string; value: number }[];
  target?: number | null;
  targetLabel?: string;
}) {
  return (
    <div className="chart-height">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 10, right: 18, left: -16, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--chart-grid)" />
          <XAxis dataKey="stage" axisLine={false} tickLine={false} tick={axisTick} />
          <YAxis domain={[0, 100]} axisLine={false} tickLine={false} tick={axisTick} />
          <Tooltip
            contentStyle={tooltipStyle}
            formatter={(v) => [`${v}%`, "Predicted final performance"]}
          />
          {target != null && (
            <ReferenceLine
              y={target}
              stroke="var(--warning)"
              strokeDasharray="5 4"
              label={{
                value: `${targetLabel} ${target}%`,
                fill: "var(--warning)",
                fontSize: 11,
                position: "insideTopRight",
              }}
            />
          )}
          <Line
            type="monotone"
            dataKey="value"
            stroke="var(--primary)"
            strokeWidth={2.5}
            dot={{ r: 4, fill: "var(--primary)", strokeWidth: 2, stroke: "var(--background)" }}
            activeDot={{ r: 5 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

const BAND_COLORS = [
  "var(--destructive)",
  "var(--warning)",
  "var(--primary)",
  "var(--primary)",
  "var(--success)",
];

export function DistributionChart({ data }: { data: { band: string; count: number }[] }) {
  return (
    <div className="chart-height">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 8, left: -20, bottom: 0 }}>
          <CartesianGrid vertical={false} stroke="var(--chart-grid)" />
          <XAxis dataKey="band" axisLine={false} tickLine={false} tick={axisTick} />
          <YAxis allowDecimals={false} axisLine={false} tickLine={false} tick={axisTick} />
          <Tooltip
            cursor={{ fill: "var(--muted)" }}
            contentStyle={tooltipStyle}
            formatter={(v) => [v, "Students"]}
          />
          <Bar dataKey="count" radius={[3, 3, 0, 0]}>
            {data.map((d, i) => (
              <Cell key={d.band} fill={BAND_COLORS[i] ?? "var(--primary)"} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/** Horizontal SHAP bar chart: how each input moves this estimate from the average prediction. */
export function ShapChart({ contributions }: { contributions: Contribution[] }) {
  const data = contributions.map((c) => ({ name: `${c.label} (${c.value}%)`, shap: c.shap_value }));
  const extent = Math.max(1, ...data.map((d) => Math.abs(d.shap)));
  return (
    <div className="shap-chart" style={{ height: 56 + data.length * 44 }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ top: 4, right: 28, left: 8, bottom: 4 }}>
          <CartesianGrid horizontal={false} stroke="var(--chart-grid)" />
          <XAxis
            type="number"
            domain={[-Math.ceil(extent), Math.ceil(extent)]}
            axisLine={false}
            tickLine={false}
            tick={axisTick}
            tickFormatter={(v: number) => (v > 0 ? `+${v}` : `${v}`)}
          />
          <YAxis
            type="category"
            dataKey="name"
            width={170}
            axisLine={false}
            tickLine={false}
            tick={axisTick}
          />
          <ReferenceLine x={0} stroke="var(--border)" />
          <Tooltip
            cursor={{ fill: "var(--muted)" }}
            contentStyle={tooltipStyle}
            formatter={(v) => [
              `${Number(v) > 0 ? "+" : ""}${Number(v).toFixed(2)} marks`,
              "Contribution",
            ]}
          />
          <Bar dataKey="shap" radius={2} barSize={20}>
            {data.map((d) => (
              <Cell key={d.name} fill={d.shap < 0 ? "var(--destructive)" : "var(--success)"} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function ImportanceChart({
  values,
}: {
  values: { label: string; mean_abs_shap: number; share: number }[];
}) {
  const data = values.map((v) => ({ name: v.label, value: v.mean_abs_shap, share: v.share }));
  return (
    <div className="shap-chart" style={{ height: 40 + data.length * 40 }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ top: 4, right: 28, left: 8, bottom: 4 }}>
          <CartesianGrid horizontal={false} stroke="var(--chart-grid)" />
          <XAxis type="number" axisLine={false} tickLine={false} tick={axisTick} />
          <YAxis
            type="category"
            dataKey="name"
            width={120}
            axisLine={false}
            tickLine={false}
            tick={axisTick}
          />
          <Tooltip
            cursor={{ fill: "var(--muted)" }}
            contentStyle={tooltipStyle}
            formatter={(v, _n, item) => [
              `${Number(v).toFixed(2)} marks (${Math.round((item.payload as { share: number }).share * 100)}%)`,
              "Mean |SHAP|",
            ]}
          />
          <Bar dataKey="value" fill="var(--primary)" radius={2} barSize={18} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
