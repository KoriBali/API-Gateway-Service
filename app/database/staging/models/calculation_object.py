import uuid
import enum
from datetime import datetime, timezone
from sqlalchemy import Column, String, Float, Integer, Enum, ForeignKey, Date, DateTime, JSON
from sqlalchemy.orm import relationship
from app.core.staging_database import Base



# # === Pole Type ===
# class PoleType(str, enum.Enum):
#     lighting = "lighting"
#     acemast = "acemast"

# # === Pole ===
# class Pole(Base):
#     __tablename__ = "poles"

#     id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
#     calculation_case_id = Column(String, ForeignKey('calculation_cases.id', ondelete="CASCADE", onupdate="CASCADE"))
#     pole_type = Column(Enum(PoleType), default=PoleType.lighting)
#     standard = Column(String)
#     quantity = Column(Float, nullable=False)

#     # Child
#     calculation_case = relationship("CalculationCase", back_populates="poles")

#     # Parent
#     step_poles = relationship("StepPole", back_populates="pole", cascade="all, delete-orphan", passive_deletes=True)


# === Step Pole ===
class StepPole(Base):
    __tablename__ = "step_poles"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    # pole_id = Column(String, ForeignKey('poles.id', ondelete="CASCADE", onupdate="CASCADE"))
    calculation_case_id = Column(String, ForeignKey('calculation_cases.id', ondelete="CASCADE", onupdate="CASCADE"))
    material_id = Column(String, ForeignKey('materials.id', ondelete="CASCADE", onupdate="CASCADE"))

    name = Column(String, nullable=False)
    order = Column(String, nullable=False)
    diameter = Column(Float, nullable=False)
    thickness = Column(Float, nullable=False)
    height = Column(Float, nullable=False)
    quantity = Column(Float, nullable=False)
    # material = Column(String, nullable=False)

    # Child
    # pole = relationship("Pole", back_populates="step_poles")

    # Parent
    pole_results = relationship("PoleResult", back_populates="step_pole")



# === Pole Result ===
class PoleResult(Base):
    __tablename__ = "pole_results"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    step_pole_id = Column(String, ForeignKey('step_poles.id', ondelete="CASCADE", onupdate="CASCADE"))
    calculation_result_id = Column(String, ForeignKey('calculation_results.id', ondelete="CASCADE", onupdate="CASCADE"))
    windload = Column(Float, nullable=False)
    moment = Column(Float, nullable=False)

    # Child
    step_pole = relationship("StepPole", back_populates="pole_results")
    calculation_result = relationship("CalculationResult", back_populates="pole_results")




# === Direct Object ===
class DirectObject(Base):
    __tablename__ = "direct_objects"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    calculation_case_id = Column(String, ForeignKey('calculation_cases.id', ondelete="CASCADE", onupdate="CASCADE"))
    obejct_type_id = Column(String, ForeignKey('obejct_types.id', ondelete="CASCADE", onupdate="CASCADE"))
    name = Column(String, nullable=False)
    front_area = Column(Float, nullable=False)
    height = Column(Float, nullable=False)
    nnc = Column(Float, nullable=False)
    weight = Column(Float, nullable=False)
    # height = Column(Float, nullable=False)
    quantity = Column(Float, nullable=False)

    # Child
    calculation_case = relationship("CalculationCase", back_populates="direct_objects")

    # Parent
    direct_object_results = relationship("DirectObjectResult", back_populates="direct_object", cascade="all, delete-orphan", passive_deletes=True)




class DirectObjectResult(Base):
    __tablename__ = "direct_object_results"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    direct_object_id = Column(String, ForeignKey('direct_objects.id', ondelete="CASCADE", onupdate="CASCADE"))
    calculation_result_id = Column(String, ForeignKey('calculation_results.id', ondelete="CASCADE", onupdate="CASCADE"))
    windload = Column(Float, nullable=False)
    moment = Column(Float, nullable=False)

    # Child
    direct_object = relationship("DirectObject", back_populates="direct_object_results")
    calculation_result = relationship("CalculationResult", back_populates="direct_object_results")



# === Overhead Wires ===
class OverheadWire(Base):
    __tablename__ = "overhead_wires"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    calculation_case_id = Column(String, ForeignKey('calculation_cases.id', ondelete="CASCADE", onupdate="CASCADE"))
    # obejct_type_id = Column(String, ForeignKey('obejct_types.id', ondelete="CASCADE", onupdate="CASCADE"))
    name = Column(String, nullable=False)
    weight = Column(Float, nullable=False)
    diameter = Column(Float, nullable=False)
    fix_height = Column(Float, nullable=False)
    span = Column(Float, nullable=False)
    sagging_ration = Column(Float, nullable=False)
    nnc = Column(Float, nullable=False)
    fix_angle = Column(Float, nullable=False)
    vertical_angle = Column(Float, nullable=False)



# === Opening Type ===
class OpeningType(str, enum.Enum):
    box = "box"
    r = "r" 

# === Opening Part ===
class OpeningPart(Base):
    __tablename__ = "opening_parts"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    calculation_case_id = Column(String, ForeignKey('calculation_cases.id', ondelete="CASCADE", onupdate="CASCADE"))
    # obejct_type_id = Column(String, ForeignKey('obejct_types.id', ondelete="CASCADE", onupdate="CASCADE"))
    type = Column(Enum(OpeningType), nullable=False)
    opening_width = Column(Float, nullable=False)
    box_width = Column(Float, nullable=False)
    opening_suerface_height = Column(Float, nullable=False)
    box_thickness = Column(Float, nullable=False)
    opening_length = Column(Float, nullable=False)



# === Base Plates Type ===
class BasePlateType(str, enum.Enum):
    four_rib = "four_rib"
    eight_rib = "eight_rib"

# === Base Plate ===
class BasePlate(Base):
    __tablename__ = "base_plates"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    calculation_case_id = Column(String, ForeignKey('calculation_cases.id', ondelete="CASCADE", onupdate="CASCADE"))
    # obejct_type_id = Column(String, ForeignKey('obejct_types.id', ondelete="CASCADE", onupdate="CASCADE"))
    type = Column(Enum(BasePlateType), nullable=False)
    base_plate_width = Column(Float, nullable=False)
    anchor_pitch = Column(Float, nullable=False)
    achor_bolt_diameter = Column(Float, nullable=False)
    base_plate_thickness = Column(Float, nullable=False)
    rib_plate_height = Column(Float, nullable=False)
    rib_plate_length = Column(Float, nullable=False)
    rib_plate_thickness = Column(Float, nullable=False)
    rib_plate_scallop = Column(Float, nullable=False)
    rib_plate_angle = Column(Float, nullable=True)
    weld_leg_length = Column(Float, nullable=False)



# === Foundation Type ===
class FoundationType(str, enum.Enum):
    square = "square"
    circle = "circle"

# === Foundation ===
class Foundation(Base):
    __tablename__ = "foundation"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    calculation_case_id = Column(String, ForeignKey('calculation_cases.id', ondelete="CASCADE", onupdate="CASCADE"))
    # obejct_type_id = Column(String, ForeignKey('obejct_types.id', ondelete="CASCADE", onupdate="CASCADE"))
    type = Column(Enum(FoundationType), nullable=False)
    embedment_depth = Column(Float, nullable=False)
    n_value = Column(Float, nullable=False)
    gamma_c = Column(Float, nullable=False)
    gamma = Column(Float, nullable=False)
    alpha = Column(Float, nullable=False)
    foundation_width_x = Column(Float, nullable=True)
    foundation_width_y = Column(Float, nullable=True)
    foundation_width = Column(Float, nullable=True)



# === Arm ===
class Arm(Base):
    __tablename__ = "arms"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    calculation_case_id = Column(String, ForeignKey('calculation_cases.id', ondelete="CASCADE", onupdate="CASCADE"))
    material_id = Column(String, ForeignKey('materials.id', ondelete="CASCADE", onupdate="CASCADE"))
    name = Column(String, nullable=False)
    diameter = Column(Float, nullable=False)
    thickness = Column(Float, nullable=False)
    length = Column(Float, nullable=False)
    exp_length = Column(Float, nullable=False)
    height = Column(Float, nullable=True)
    distance = Column(Float, nullable=True)
    nnc = Column(Float, nullable=True)
    fix_angle = Column(Float, nullable=True)
    quantity = Column(Float, nullable=True)



# === Arm Object ===
class ArmObject(Base):
    __tablename__ = "arm_objects"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    arm_id = Column(String, ForeignKey('arms.id', ondelete="CASCADE", onupdate="CASCADE"))
    object_type_id = Column(String, ForeignKey('object_types.id', ondelete="CASCADE", onupdate="CASCADE"))
    name = Column(String, nullable=False)
    front_area = Column(Float, nullable=False)
    weight = Column(Float, nullable=False)
    distance = Column(Float, nullable=False)
    nnc = Column(Float, nullable=False)
    quantity = Column(Float, nullable=False)