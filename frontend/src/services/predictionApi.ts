import { api } from "./api";
import type { FeatureImportance, Prediction, PredictionInputs, Simulation, Stage } from "./types";

export const predictionApi = {
  /** Saved prediction. Omit `inputs` to use the student's stored records (students must). */
  async predict(student_id: number, stage: Stage, inputs?: PredictionInputs) {
    const body = inputs ? { student_id, stage, inputs } : { student_id, stage };
    return (await api.post<Prediction>("/api/predictions/predict", body)).data;
  },
  /** What-if: same model, nothing is saved. */
  async simulate(stage: Stage, inputs: PredictionInputs) {
    return (await api.post<Simulation>("/api/predictions/simulate", { stage, inputs })).data;
  },
  async get(id: number) {
    return (await api.get<Prediction>(`/api/predictions/${id}`)).data;
  },
  async featureImportance() {
    return (await api.get<FeatureImportance>("/api/feature-importance")).data;
  },
};
