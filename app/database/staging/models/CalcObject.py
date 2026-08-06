import uuid
import enum
from datetime import datetime, timezone
from sqlalchemy import Column, String, Float, Integer, Enum, ForeignKey, Date, DateTime, JSON
from sqlalchemy.orm import relationship
from app.core.staging_database import Base



# === Pole Type ===
class PoleType(str, enum.Enum):
    lighting = "lighting"
    acemast = "acemast"

# === Pole ===
class Pole(Base):
    __tablename__ = "poles"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    calculation_case_id = Column(String, ForeignKey('calculation_cases.id', ondelete="CASCADE", onupdate="CASCADE"))
    pole_type = Column(PoleType, default=PoleType.lighting)
    standard = Column(String)
    quantity = Column(Float, nullable=False)



# === Step Pole ===
class StepPole(Base):
    __tablename__ = "step_poles"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    pole_id = Column(String, ForeignKey('poles.id', ondelete="CASCADE", onupdate="CASCADE"))
    name = Column(String, nullable=False)
    diameter = Column(Float, nullable=False)
    thickness = Column(Float, nullable=False)
    height = Column(Float, nullable=False)
    material = Column(String, nullable=False)



# === Pole Result ===
class PoleResult(Base):
    __tablename__ = "pole_results"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    step_pole_id = Column(String, ForeignKey('step_poles.id', ondelete="CASCADE", onupdate="CASCADE"))
    calculation_result_id = Column(String, ForeignKey('calculation_results.id', ondelete="CASCADE", onupdate="CASCADE"))
    windload = Column(Float, nullable=False)
    moment = Column(Float, nullable=False)



# === Direct Object ===
class DirectObject(Base):
    __tablename__ = "direct_objects"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    calculation_case_id = Column(String, ForeignKey('calculation_cases.id', ondelete="CASCADE", onupdate="CASCADE"))
    name = Column(String, nullable=False)
    front_area = Column(Float, nullable=False)
    side_area = Column(Float, nullable=False)
    coefficient = Column(Float, nullable=False)
    weight = Column(Float, nullable=False)
    height = Column(Float, nullable=False)
    quantity = Column(Float, nullable=False)



class PoleResult(Base):
    __tablename__ = "direct_object_results"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    direct_object_id = Column(String, ForeignKey('direct_objects.id', ondelete="CASCADE", onupdate="CASCADE"))
    calculation_result_id = Column(String, ForeignKey('calculation_results.id', ondelete="CASCADE", onupdate="CASCADE"))
    windload = Column(Float, nullable=False)
    moment = Column(Float, nullable=False)