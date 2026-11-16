"""Independent API checks for the CampusConnect FastAPI service."""

from pathlib import Path
import sys

from fastapi.testclient import TestClient

SERVICE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_ROOT))

from main import app


def main() -> None:
    with TestClient(app) as client:
        health = client.get("/health")
        assert health.status_code == 200, health.text
        assert health.json() == {
            "status": "ok",
            "service": "CampusConnect ML Service",
        }

        stage1 = client.post(
            "/predict/stage1",
            json={"attendance": 85, "internal1": 75, "assignment": 80},
        )
        assert stage1.status_code == 200, stage1.text
        assert stage1.json() == {
            "stage": "stage1",
            "predicted_final_performance": 65.06,
        }

        stage2 = client.post(
            "/predict/stage2",
            json={
                "attendance": 85,
                "internal1": 75,
                "internal2": 80,
                "assignment": 80,
            },
        )
        assert stage2.status_code == 200, stage2.text
        assert stage2.json() == {
            "stage": "stage2",
            "predicted_final_performance": 63.19,
        }

        what_if_stage1 = client.post(
            "/predict/what-if",
            json={
                "stage": "stage1",
                "attendance": 90,
                "internal1": 85,
                "assignment": 90,
            },
        )
        assert what_if_stage1.status_code == 200, what_if_stage1.text
        assert what_if_stage1.json()["simulation_only"] is True

        what_if_stage2 = client.post(
            "/predict/what-if",
            json={
                "stage": "stage2",
                "attendance": 90,
                "internal1": 85,
                "internal2": 88,
                "assignment": 90,
            },
        )
        assert what_if_stage2.status_code == 200, what_if_stage2.text
        assert what_if_stage2.json()["simulation_only"] is True

        invalid_input = client.post(
            "/predict/stage1",
            json={"attendance": 101, "internal1": 75, "assignment": 80},
        )
        assert invalid_input.status_code == 422, invalid_input.text

        invalid_stage = client.post(
            "/predict/what-if",
            json={
                "stage": "stage3",
                "attendance": 90,
                "internal1": 85,
                "assignment": 90,
            },
        )
        assert invalid_stage.status_code == 422, invalid_stage.text

        missing_stage2_input = client.post(
            "/predict/what-if",
            json={
                "stage": "stage2",
                "attendance": 90,
                "internal1": 85,
                "assignment": 90,
            },
        )
        assert missing_stage2_input.status_code == 422, missing_stage2_input.text

    print("API tests passed: health, stage1, stage2, both what-if stages, and validation errors.")


if __name__ == "__main__":
    main()