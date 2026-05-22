import uuid
import enum
from datetime import datetime, timezone
from sqlalchemy import Column, String, Float, Integer, Enum, ForeignKey, Date, DateTime, JSON
from sqlalchemy.orm import relationship
from app.core.staging_database import Base

class ProjectType(str, enum.Enum):
    lighting_pole = "lighting_pole"
    acemast = "acemast"
    sign_board = "sign_board"
    multiple = "multiple"

class StagingStatus(str, enum.Enum):
    pending = "pending"
    save = "save"
    discard = "discard"

class DesignStandard(str, enum.Enum):
    jil = "jil"
    haiden = "haiden"
    v60 = "v60"

class MaterialType(str, enum.Enum):
    stk_400 = "stk_400"
    stk_490 = "stk_490"
    stk_500 = "stk_500"

class CalculationStatus(str, enum.Enum):
    ok = "ok"
    ng = "ng"


class StagingProject(Base):
    __tablename__ = 'staging_projects'
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    title = Column(String, nullable=False)
    date = Column(Date, nullable=True)
    report_number = Column(String, nullable=True)
    project_type = Column(Enum(ProjectType), nullable=True, default=ProjectType.lighting_pole)
    status = Column(Enum(StagingStatus), default=StagingStatus.pending)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships (Cascade delete sangat penting di sini)
    condition = relationship("StagingCondition", back_populates="project", uselist=False, cascade="all, delete-orphan")
    poles = relationship("StagingStepPole", back_populates="project", cascade="all, delete-orphan")
    high_evals = relationship("StagingHighEval", back_populates="project", cascade="all, delete-orphan")
    direct_objects = relationship("StagingDirectObject", back_populates="project", cascade="all, delete-orphan")


class StagingCondition(Base):
    __tablename__ = 'staging_conditions'
    id = Column(Integer, primary_key=True, autoincrement=True)
    staging_project_id = Column(String, ForeignKey('staging_projects.id', ondelete="CASCADE"))
    design_standard = Column(Enum(DesignStandard), nullable=True)
    wind_speed = Column(Float, nullable=True)
    air_density = Column(Float, nullable=True)
    
    project = relationship("StagingProject", back_populates="condition")


class StagingHighEval(Base):
    __tablename__ = 'staging_high_evals'
    id = Column(Integer, primary_key=True, autoincrement=True)
    staging_project_id = Column(String, ForeignKey('staging_projects.id', ondelete="CASCADE"))
    name = Column(String, nullable=False)
    point_evaluate = Column(Float, nullable=False)
    
    project = relationship("StagingProject", back_populates="high_evals")

    # one to one | calculation result
    calculation_result = relationship("StagingCalculationResult", back_populates="high_eval", uselist=False, cascade="all, delete-orphan")


class StagingStepPole(Base):
    __tablename__ = 'staging_step_poles'
    id = Column(Integer, primary_key=True, autoincrement=True)
    staging_project_id = Column(String, ForeignKey('staging_projects.id', ondelete="CASCADE"))
    name = Column(String, nullable=False)
    diameter = Column(Float, nullable=False)
    thickness = Column(Float, nullable=False)
    height = Column(Float, nullable=False)
    material = Column(Enum(MaterialType), nullable=False)
    quantity = Column(Integer, nullable=True)
    
    project = relationship("StagingProject", back_populates="poles")

    # result relation
    pole_results = relationship("StagingPoleResult", back_populates="step_pole", cascade="all, delete-orphan")


class StagingDirectObject(Base):
    __tablename__ = 'staging_direct_objects'
    id = Column(Integer, primary_key=True, autoincrement=True)
    staging_project_id = Column(String, ForeignKey('staging_projects.id', ondelete="CASCADE"))
    name = Column(String, nullable=False)
    front_area = Column(Float, nullable=False)
    side_area = Column(Float, nullable=False)
    height = Column(Float, nullable=False)
    weight = Column(Float, nullable=False)
    coefficient = Column(Float, nullable=False)
    quantity = Column(Integer, nullable=True)
    
    project = relationship("StagingProject", back_populates="direct_objects")

    # result relation
    direct_object_results = relationship("StagingDirectObjectResult", back_populates="direct_object", cascade="all, delete-orphan")


# RESULT SECTIONS
class StagingCalculationResult(Base):
    __tablename__ = 'staging_calculation_results'
    id = Column(Integer, primary_key=True, autoincrement=True)
    staging_high_evals_id = Column(Integer, ForeignKey('staging_high_evals.id', ondelete="CASCADE"), unique=True)
    total_windload = Column(Float, nullable=False)
    total_moment = Column(Float, nullable=False)
    status = Column(Enum(CalculationStatus), nullable=False)
    
    high_eval = relationship("StagingHighEval", back_populates="calculation_result")
    
    # 1:M ke detail hasil
    pole_results = relationship("StagingPoleResult", back_populates="calculation_result", cascade="all, delete-orphan")
    direct_object_results = relationship("StagingDirectObjectResult", back_populates="calculation_result", cascade="all, delete-orphan")


class StagingPoleResult(Base):
    __tablename__ = 'staging_pole_results'
    id = Column(Integer, primary_key=True, autoincrement=True)
    staging_calculation_result_id = Column(Integer, ForeignKey('staging_calculation_results.id', ondelete="CASCADE"))
    staging_step_pole_id = Column(Integer, ForeignKey('staging_step_poles.id', ondelete="CASCADE"))
    windload = Column(Float, nullable=False)
    moment = Column(Float, nullable=False)
    
    calculation_result = relationship("StagingCalculationResult", back_populates="pole_results")
    step_pole = relationship("StagingStepPole", back_populates="pole_results")


class StagingDirectObjectResult(Base):
    __tablename__ = 'staging_direct_object_results'
    id = Column(Integer, primary_key=True, autoincrement=True)
    staging_calculation_result_id = Column(Integer, ForeignKey('staging_calculation_results.id', ondelete="CASCADE"))
    staging_direct_object_id = Column(Integer, ForeignKey('staging_direct_objects.id', ondelete="CASCADE"))
    windload = Column(Float, nullable=False)
    moment = Column(Float, nullable=False)
    
    calculation_result = relationship("StagingCalculationResult", back_populates="direct_object_results")
    direct_object = relationship("StagingDirectObject", back_populates="direct_object_results")