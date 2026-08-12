import uuid
import enum
from datetime import datetime, timezone
from sqlalchemy import Column, String, Float, Integer, Enum, ForeignKey, Date, DateTime, JSON
from sqlalchemy.orm import relationship
from app.core.staging_database import Base

# === Status Case ===
class StatusCalculationCase(str, enum.Enum):
    draft = "draft"
    submitted = "submitted"
    superseded = "superseded"

# === Pole Family ===
class PoleFamily(str, enum.Enum):
    taper = "taper"
    straight = "straight"

# === Ground Position ===
class GroundPosition(str, enum.Enum):
    embedment = "embedment"
    on_GL = "on_GL"
    under_GL = "under_GL"

# === Calculation Case ===
class CalculationCase(Base):
    __tablename__ = "calculation_cases"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    request_id = Column(String, ForeignKey('requests.id', ondelete="CASCADE", onupdate="CASCADE"))
    owner_user_id = Column(String, ForeignKey('users.id', ondelete="CASCADE", onupdate="CASCADE"))
    supersedes_case_id = Column(String, ForeignKey('calculation_cases.id', ondelete="CASCADE", onupdate="CASCADE"))
    pole_standard_id = Column(String, ForeignKey('pole_standards.id', ondelete="CASCADE", onupdate="CASCADE"), nullable=True)
    selected_height_id = Column(String, ForeignKey('pole_standard_height.id', ondelete="CASCADE", onupdate="CASCADE"), nullable=True)
    selected_combination_id = Column(String, ForeignKey('pole_combinations.id', ondelete="CASCADE", onupdate="CASCADE"), nullable=True)
    status = Column(Enum(StatusCalculationCase), default=StatusCalculationCase.draft)
    pole_family = Column(Enum(PoleFamily), nullable=True)
    ground_position = Column(Enum(GroundPosition), nullable=True)
    lowest_height = Column(Float, nullable=True)
    embedment_length = Column(Float, nullable=True)
    overdesign_factor = Column(Float, nullable=True)
    title = Column(String, nullable=False)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
            DateTime, 
            default=lambda: datetime.now(timezone.utc), 
            onupdate=lambda: datetime.now(timezone.utc),
            nullable=False 
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
# class DesignStandard(str, enum.Enum):
#     jil = "jil"
#     haiden = "haiden"
#     v60 = "v60"

# === Condition ===
class Condition(Base):
    __tablename__ = "conditions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    calculation_case_id = Column(String, ForeignKey('calculation_cases.id', ondelete="CASCADE", onupdate="CASCADE"))
    # design_standard = Column(Enum(DesignStandard), nullable=False)
    design_standard_id = Column(String, ForeignKey('design_standards.id', ondelete="CASCADE", onupdate="CASCADE"))
    wind_speed = Column(Float, nullable=False)
    air_density = Column(Float, nullable=False)

    # Child
    calculation_case = relationship("CalculationCase", back_populates="conditions")



# # === High Evaluation ===
# class HighEvaluation(Base):
#     __tablename__ = "high_evals"

#     id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
#     calculation_case_id = Column(String, ForeignKey('calculation_cases.id', ondelete="CASCADE", onupdate="CASCADE"))
#     name = Column(String, nullable=False)
#     evaluation_point = Column(Float, nullable=False)

#     # Child
#     calculation_case = relationship("CalculationCase", back_populates="high_evals")

#     # Parent
#     calculation_results = relationship("CalculationResult", back_populates="high_eval", cascade="all, delete-orphan", passive_deletes=True)



# === Status Calculation Run ===
class StatusCalculationRun(str, enum.Enum):
    ok = "ok"
    ng = "ng"

# === Calculation Run ===
class CalculationRun(Base):
    __tablename__ = "calculation_runs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    calculation_case_id = Column(String, ForeignKey('calculation_cases.id', ondelete="CASCADE", onupdate="CASCADE"))

    # run_type = Optional (untuk tipe kalkulasi apa?[strength, flexible, ...])
    # run_type = Column(enum)

    status = Column(Enum(StatusCalculationRun), nullable=False)
    input_snapshot = Column(JSON)
    run_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Child
    calculation_case = relationship("CalculationCase", back_populates="calculation_runs")

    # Parent
    calculation_results = relationship("CalculationResult", back_populates="calculation_run", cascade="all, delete-orphan", passive_deletes=True)



# === Calculation Result ===
class CalculationResult(Base):
    __tablename__ = "calculation_results"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    calculation_run_id = Column(String, ForeignKey('calculation_runs.id', ondelete="CASCADE", onupdate="CASCADE"))
    # high_eval_id = Column(String, ForeignKey('high_evals.id', ondelete="CASCADE", onupdate="CASCADE"))
    total_moment = Column(Float, nullable=False)
    total_windload = Column(Float, nullable=False)
    status = Column(Enum(StatusCalculationRun), nullable=False)

    # Child
    calculation_run = relationship("CalculationRun", back_populates="calculation_results")
    # high_eval= relationship("HighEvaluation", back_populates="calculation_results")

    # Parent
    pole_results = relationship("PoleResult", back_populates="calculation_result", cascade="all, delete-orphan", passive_deletes=True)
    direct_object_results = relationship("DirectObjectResult", back_populates="calculation_result", cascade="all, delete-orphan", passive_deletes=True)
