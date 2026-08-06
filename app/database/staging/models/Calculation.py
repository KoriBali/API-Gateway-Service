import uuid
import enum
from datetime import datetime, timezone
from sqlalchemy import Column, String, Float, Integer, Enum, ForeignKey, Date, DateTime, JSON
from sqlalchemy.orm import relationship
from app.core.staging_database import Base

# === Status Case ===
class StatusCase(str, enum.Enum):
    draft = "draft"
    submitted = "submitted"
    superseded = "superseded"

# === Calculation Case ===
class CalculationCase(Base):
    __tablename__ = "calculation_cases"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    request_id = Column(String, ForeignKey('requests.id', ondelete="CASCADE", onupdate="CASCADE"))
    owner_user_id = Column(String, ForeignKey('users.id', ondelete="CASCADE", onupdate="CASCADE"))
    supersedes_case_id = Column(String, ForeignKey('calculation_cases.id', ondelete="CASCADE", onupdate="CASCADE"))
    stauts = Column(StatusCase, default=StatusCase.draft)
    title = Column(String, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
            DateTime, 
            default=lambda: datetime.now(timezone.utc), 
            onupdate=lambda: datetime.now(timezone.utc) 
        )



# === Design Standard ===
class DesignStandard(str, enum.Enum):
    jil = "jil"
    haiden = "haiden"
    v60 = "v60"

# === Condition ===
class Condition(Base):
    __tablename__ = "conditions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    calculation_case_id = Column(String, ForeignKey('calculation_cases.id', ondelete="CASCADE", onupdate="CASCADE"))
    design_standard = Column(DesignStandard, nullable=False)
    wind_speed = Column(Float, nullable=False)
    air_density = Column(Float, nullable=False)



# === High Evaluation ===
class HighEvaluation(Base):
    ___tablename__ = "high_evals"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    calculation_case_id = Column(String, ForeignKey('calculation_cases.id', ondelete="CASCADE", onupdate="CASCADE"))
    name = Column(String, nullable=False)
    point_evaluate = Column(Float, nullable=False)



# === Status Calculation Run ===
class StatusCalculationRun(str, enum.Enum):
    ok = "ok"
    ng = "ng"

# === Calculation Run ===
class CalculationRun(Base):
    __tablename__ = "calculation_runs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    calculation_case_id = Column(String, ForeignKey('calculation_cases.id', ondelete="CASCADE", onupdate="CASCADE"))

    # run_type = Optional (untuk tipe kalkulasi apa?[strength, flexible, ...])
    # run_type = Column(enum)

    Status = Column(StatusCalculationRun, nullable=False)
    input_snapshot = Column(String)
    run_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))



# === Calculation Result ===
class CalculationResult(Base):
    __tablename__ = "calculation_results"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    calculation_run_id = Column(String, ForeignKey('calculation_runs.id', ondelete="CASCADE", onupdate="CASCADE"))
    high_eval_id = Column(String, ForeignKey('high_evals.id', ondelete="CASCADE", onupdate="CASCADE"))
    total_moment = Column(Float, nullable=False)
    total_windload = Column(Float, nullable=False)
    status = Column(StatusCalculationRun, nullable=False)

    