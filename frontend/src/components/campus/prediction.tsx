import type { ReactNode } from "react";
import { AlertTriangle, Info, Lightbulb, RotateCw, ThumbsUp } from "lucide-react";
import { Button } from "@/components/ui/button";
import { DataState, SectionTitle, StatusBadge } from "./core";
import { ShapChart } from "./charts";
import { getApiErrorMessage } from "@/lib/api-error";
import type {
  Prediction,
  Recommendations,
  RiskLevel,
  ShapExplanation,
  Simulation,
} from "@/services/types";
import { formatDate, riskLabel } from "@/utils/academic";

/** Loading / error-with-retry wrapper for react-query results. */
export function Loadable({
  isLoading,
  error,
  onRetry,
  loadingTitle,
  children,
}: {
  isLoading: boolean;
  error: unknown;
  onRetry: () => void;
  loadingTitle?: string;
  children: ReactNode;
}) {
  if (isLoading)
    return (
      <div className="state-box">
        <DataState
          type="loading"
          title={loadingTitle ?? "Loading…"}
          detail="If the server was idle this can take up to a minute."
        />
      </div>
    );
  if (error)
    return (
      <div className="state-box">
        <DataState type="error" title="Unable to load data" detail={getApiErrorMessage(error)} />
        <Button variant="outline" size="sm" onClick={onRetry}>
          <RotateCw />
          Try again
        </Button>
      </div>
    );
  return <>{children}</>;
}

export function RiskBadge({ risk }: { risk: RiskLevel }) {
  return <span className={`status-badge risk-${risk}`}>{riskLabel(risk)}</span>;
}

export function ShapPanel({ explanation }: { explanation: ShapExplanation }) {
  return (
    <div className="shap-panel">
      <SectionTitle
        title="Why this estimate"
        description={`Starts from the average prediction (${explanation.base_value.toFixed(1)}%). Red bars lower the estimate, green bars raise it.`}
      />
      <ShapChart contributions={explanation.contributions} />
      <p className="method-caption">
        {explanation.method} · base {explanation.base_value.toFixed(2)} + contributions ={" "}
        {explanation.raw_prediction.toFixed(2)}. {explanation.note}
      </p>
    </div>
  );
}

export function RecommendationsPanel({ recommendations }: { recommendations: Recommendations }) {
  return (
    <div className="recs-panel">
      <SectionTitle title="What the data suggests" description={recommendations.risk_note} />
      <p className="recs-summary">{recommendations.summary}</p>
      {recommendations.items.length === 0 ? (
        <div className="inline-notice">
          <ThumbsUp />
          No input is lowering this estimate. Keeping up current habits is associated with results
          like this.
        </div>
      ) : (
        <ol className="recs-list">
          {recommendations.items.map((item) => (
            <li key={item.feature}>
              <span className="recs-priority">{item.priority}</span>
              <div>
                <b>{item.label}</b>
                <p>{item.finding}</p>
                <p className="recs-action">
                  <Lightbulb />
                  {item.action}
                </p>
                <small>{item.estimated_effect.text}</small>
              </div>
            </li>
          ))}
        </ol>
      )}
      {recommendations.strengths.length > 0 && (
        <div className="recs-strengths">
          <b>Strengths</b>
          {recommendations.strengths.map((s) => (
            <span key={s.feature}>{s.text}</span>
          ))}
        </div>
      )}
    </div>
  );
}

/** Full result: estimate, risk, range, warnings, SHAP chart and recommendations. */
export function PredictionResult({
  result,
  title,
}: {
  result: Prediction | Simulation;
  title?: string;
}) {
  const saved = "id" in result;
  return (
    <section className="prediction-result">
      <SectionTitle
        title={title ?? (saved ? "Prediction result" : "Simulation result")}
        description={
          saved
            ? `${result.stage === "stage1" ? "Stage 1" : "Stage 2"} · ${formatDate(result.created_at)} · inputs from ${
                result.input_source === "records" ? "stored records" : "manual entry"
              }`
            : `${result.stage === "stage1" ? "Stage 1" : "Stage 2"} · not saved`
        }
        aside={<RiskBadge risk={result.risk_level} />}
      />
      <div className="result-headline">
        <div>
          <strong>{result.predicted_marks.toFixed(1)}%</strong>
          <span>Estimated final exam performance</span>
        </div>
        {result.interval && (
          <div>
            <strong className="result-range">
              {result.interval.low.toFixed(1)}–{result.interval.high.toFixed(1)}%
            </strong>
            <span>{result.interval.description}</span>
          </div>
        )}
      </div>
      {result.warnings.map((w) => (
        <div className="warning-note" key={w}>
          <AlertTriangle />
          {w}
        </div>
      ))}
      <div className="result-grid">
        {result.shap_explanation && <ShapPanel explanation={result.shap_explanation} />}
        {result.recommendations && (
          <RecommendationsPanel recommendations={result.recommendations} />
        )}
      </div>
      <p className="prediction-note">
        <Info />
        {"disclaimer" in result ? result.disclaimer : ""} Model {result.model_version}.
      </p>
    </section>
  );
}

export function StatusFromRisk({ risk }: { risk: RiskLevel | undefined }) {
  return risk ? <RiskBadge risk={risk} /> : <StatusBadge status="No prediction yet" />;
}
