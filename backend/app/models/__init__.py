"""Import every model so Base.metadata (used by Alembic) knows all tables."""

from app.models.academic_record import AcademicRecord
from app.models.attendance import Attendance
from app.models.base import Base
from app.models.faculty_benchmark import FacultyBenchmark
from app.models.monitoring import Monitoring, MonitoringStatus
from app.models.prediction import Prediction, PredictionStage, RiskLevel
from app.models.student import Student
from app.models.student_target import StudentTarget
from app.models.user import User, UserRole

__all__ = [
    "AcademicRecord",
    "Attendance",
    "Base",
    "FacultyBenchmark",
    "Monitoring",
    "MonitoringStatus",
    "Prediction",
    "PredictionStage",
    "RiskLevel",
    "Student",
    "StudentTarget",
    "User",
    "UserRole",
]
