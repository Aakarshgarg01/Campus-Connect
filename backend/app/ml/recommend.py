"""Recommendations and a plain-English summary from a student's actual inputs and SHAP values.

Rules:
* Only inputs whose SHAP contribution lowers the estimate become recommendations, most
  impactful first (at most three).
* Each recommendation quotes the student's value, the training average, and a model estimate of
  what a specific change is associated with (other inputs held fixed), computed by running the
  real pipeline, never a typed-in number.
* Wording is "associated with", never "will cause/improve": the model learns associations.
"""

from __future__ import annotations

from typing import Any

from app.ml.features import ASSIGNMENT, ATTENDANCE, FEATURE_LABELS, INTERNAL1, INTERNAL2
from app.ml.model_loader import LoadedModel
from app.ml.predict import to_frame
from app.models import RiskLevel

MAX_RECOMMENDATIONS = 3
STEP = 10.0  # percentage points used when a student is already at or above the average

ACTIONS = {
    ATTENDANCE: "Aim to attend every scheduled class. If something is getting in the way, talk to a mentor "
                "or faculty advisor early.",
    INTERNAL1: "Go back over the topics assessed in Internal Test 1, especially questions where marks were "
               "lost, and ask the subject teacher for feedback.",
    INTERNAL2: "Revisit the topics from Internal Test 2 before the final exam and practise past questions "
               "under timed conditions.",
    ASSIGNMENT: "Submit every assignment on time and use the feedback on earlier assignments to improve "
                "the next ones.",
}

RISK_NOTES = {
    RiskLevel.HIGH: "The estimate is in the high-risk band. Arranging a support plan with faculty now gives the "
                    "most time to act before the final exam.",
    RiskLevel.MEDIUM: "The estimate is close to the high-risk band, so small changes in the inputs below matter.",
    RiskLevel.LOW: "The estimate is in the low-risk band. Keeping up current habits is associated with "
                   "results like this in the data.",
}


def _raw(model: LoadedModel, stage: str, values: dict[str, float]) -> float:
    return float(model.pipeline.predict(to_frame(stage, values))[0])


def build(model: LoadedModel, stage: str, values: dict[str, float], explanation: dict[str, Any],
          predicted: float, risk: RiskLevel, interval: tuple[float, float]) -> dict[str, Any]:
    means = {f["name"]: float(f["training_mean"]) for f in model.metadata["features"]}
    contributions = explanation["contributions"]
    negatives = [c for c in contributions if c["direction"] == "decreases"][:MAX_RECOMMENDATIONS]
    positives = [c for c in contributions if c["direction"] == "increases"]
    baseline = _raw(model, stage, values)

    items = []
    for priority, c in enumerate(negatives, start=1):
        feature, value, mean = c["feature"], float(values[c["feature"]]), means[c["feature"]]
        target = round(mean, 1) if mean > value else min(100.0, value + STEP)
        change = round(_raw(model, stage, {**values, feature: target}) - baseline, 2)
        label = FEATURE_LABELS[feature]
        reason = (f"{label} is {value:g}%, below the training average of {mean:.1f}%."
                  if value < mean else f"{label} is {value:g}% (training average {mean:.1f}%).")
        items.append({
            "priority": priority,
            "feature": feature,
            "label": label,
            "current_value": round(value, 2),
            "reference_value": round(mean, 2),
            "shap_value": c["shap_value"],
            "finding": f"{reason} In this model it is associated with a {abs(c['shap_value']):.2f}-mark "
                       f"lower estimate than for an average student.",
            "action": ACTIONS[feature],
            "estimated_effect": {
                "change_to": target,
                "predicted_change": change,
                "text": f"Raising {label} from {value:g}% to {target:g}% is associated with about "
                        f"{change:+.1f} marks in the model's estimate, other inputs unchanged. "
                        f"This is a model estimate, not a guarantee.",
            },
        })

    strengths = [
        {"feature": c["feature"], "label": c["label"], "current_value": c["value"],
         "reference_value": round(means[c["feature"]], 2), "shap_value": c["shap_value"],
         "text": f"{c['label']} ({c['value']:g}%) is associated with a {c['shap_value']:.2f}-mark higher estimate."}
        for c in positives
    ]

    lines = [
        f"The estimated final exam score is {predicted:.1f}% ({risk.value} risk). On held-out students, "
        f"90% of estimates were within the range shown, here {interval[0]:.1f}–{interval[1]:.1f}%.",
        f"An average student in the training data is estimated at {explanation['base_value']:.1f}%.",
    ]
    if negatives:
        lines.append("Inputs associated with a lower estimate: " + ", ".join(
            f"{c['label']} ({c['value']:g}%, {c['shap_value']:+.2f})" for c in negatives) + ".")
    if positives:
        lines.append("Inputs associated with a higher estimate: " + ", ".join(
            f"{c['label']} ({c['value']:g}%, {c['shap_value']:+.2f})" for c in positives) + ".")
    if stage == "stage1":
        lines.append("Internal Test 2 has not been included yet; the Stage 2 estimate will use it.")
    lines.append("These are associations in historical data, not proof that changing one input will change "
                 "the final result.")

    return {
        "summary": " ".join(lines),
        "risk_note": RISK_NOTES[risk],
        "items": items,
        "strengths": strengths,
        "method": "Generated from this student's inputs and their SHAP contributions; effects are computed "
                  "by re-running the trained model with one input changed.",
    }
