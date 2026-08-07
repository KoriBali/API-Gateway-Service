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
    stauts = Column(Enum(StatusCase), default=StatusCase.draft)
    title = Column(String, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
            DateTime, 
            default=lambda: datetime.now(timezone.utc), 
            onupdate=lambda: datetime.now(timezone.utc) 
        )

    # Self
    supersedes    = relationship("CalculationCase", remote_side=[id], back_populates="superseded_by")
    superseded_by = relationship("CalculationCase", back_populates="supersedes")

    # Parent
    conditions = relationship("Condition", back_populates="calculation_case", cascade="all, delete-orphan", passive_deletes=True)
    high_evals = relationship("HighEvaluation", back_populates="calculation_case", cascade="all, delete-orphan", passive_deletes=True)
    calculation_runs = relationship("HighEvaluation", back_populates="calculation_case", cascade="all, delete-orphan", passive_deletes=True)
    poles = relationship("Pole", back_populates="calculation_case", cascade="all, delete-orphan", passive_deletes=True)
    direct_objects = relationship("DirectObject", back_populates="calculation_case", cascade="all, delete-orphan", passive_deletes=True)

    # Child
    request = relationship("Request", back_populates="calculation_cases")
    owner_user = relationship("User", back_populates="calculation_cases")



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
    design_standard = Column(Enum(DesignStandard), nullable=False)
    wind_speed = Column(Float, nullable=False)
    air_density = Column(Float, nullable=False)

    # Child
    calculation_case = relationship("CalculationCase", back_populates="conditions")



# === High Evaluation ===
class HighEvaluation(Base):
    __tablename__ = "high_evals"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    calculation_case_id = Column(String, ForeignKey('calculation_cases.id', ondelete="CASCADE", onupdate="CASCADE"))
    name = Column(String, nullable=False)
    point_evaluate = Column(Float, nullable=False)

    # Child
    calculation_case = relationship("CalculationCase", back_populates="high_evals")

    # Parent
    calculation_results = relationship("CalculationResult", back_populates="high_eval", cascade="all, delete-orphan", passive_deletes=True)



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

    Status = Column(Enum(StatusCalculationRun), nullable=False)
    input_snapshot = Column(String)
    run_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Child
    calculation_case = relationship("CalculationCase", back_populates="calculation_runs")

    # Parent
    calculation_results = relationship("CalculationResult", back_populates="calculation_run", cascade="all, delete-orphan", passive_deletes=True)



# === Calculation Result ===
class CalculationResult(Base):
    __tablename__ = "calculation_results"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    calculation_run_id = Column(String, ForeignKey('calculation_runs.id', ondelete="CASCADE", onupdate="CASCADE"))
    high_eval_id = Column(String, ForeignKey('high_evals.id', ondelete="CASCADE", onupdate="CASCADE"))
    total_moment = Column(Float, nullable=False)
    total_windload = Column(Float, nullable=False)
    status = Column(Enum(StatusCalculationRun), nullable=False)

    # Child
    calculation_run = relationship("CalculationRun", back_populates="calculation_results")
    high_eval= relationship("HighEvaluation", back_populates="calculation_results")

    # Parent
    pole_results = relationship("PoleResult", back_populates="calculation_result", cascade="all, delete-orphan", passive_deletes=True)
    direct_object_results = relationship("DirectObjectResult", back_populates="calculation_result", cascade="all, delete-orphan", passive_deletes=True)
