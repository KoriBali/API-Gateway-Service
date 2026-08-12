import uuid
import enum
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean ,Float, Integer, Enum, ForeignKey, Date, DateTime, JSON
from sqlalchemy.orm import relationship
from app.core.staging_database import Base



# === Material ===
class Material(Base):
    __tablename__ = 'materials'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)



# === Pole Category ===
class PoleCategory(Base):
    __tablename__ = 'pole_categories'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)



# === Design Standard ===
class DesignStandard(Base):
    __tablename__ = 'design_standards'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    pole_category_id = Column(String, ForeignKey('pole_categories.id', ondelete='CASCADE', onupdate='CASCADE'))
    name = Column(String, nullable=False)
    default_wind_speed = Column(Float, nullable=True)
    default_air_density = Column(Float, nullable=True)
    is_active = Column(Boolean, default=True)  



# === Pole Standard Type ===
class PoleStandardType(str, enum.Enum):
    taper = "taper"
    straight = "straight"

# === Pole Standard ===
class PoleStandard(Base):
    __tablename__ = 'pole_standards'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    pole_category_id = Column(String, ForeignKey('pole_categories.id', ondelete='CASCADE', onupdate='CASCADE'))
    name = Column(String, nullable=False)
    type = Column(Enum(PoleStandardType), nullable=False)

    geometry = Column(JSON, nullable=True)
    is_active = Column(Boolean, default=True)      



# === Pole Standard Height ===
class PoleStandardHeight(Base):
    __tablename__ = 'pole_standard_heights'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    pole_standard_id = Column(String, ForeignKey('pole_standards.id', ondelete='CASCADE', onupdate='CASCADE'))
    height = Column(Float, nullable=False)
    is_active = Column(Boolean, default=True)      



# === Pole Diameter ===
class PoleDiameter(Base):
    __tablename__ = 'pole_diameters'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    pole_standard_id = Column(String, ForeignKey('pole_standards.id', ondelete='CASCADE', onupdate='CASCADE'))
    diameter = Column(Float, nullable=False)
    is_active = Column(Boolean, default=True)      



# === Pole Combination ===
class PoleCombination(Base):
    __tablename__ = 'pole_combinations'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    pole_diameter_id = Column(String, ForeignKey('pole_diameters.id', ondelete='CASCADE', onupdate='CASCADE'))
    name = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)    



# === Pole Thickness Position ===
class PoleThicknessPosition(str, enum.Enum):
    upper = "upper"
    lower = "lower"

# === Pole Thickness ===
class PoleThickness(Base):
    __tablename__ = 'pole_thicknesses'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    pole_diameter_id = Column(String, ForeignKey('pole_diameters.id', ondelete='CASCADE', onupdate='CASCADE'))
    position = Column(Enum(PoleThicknessPosition), nullable=False)
    thickness = Column(Float, nullable=False)
    is_active = Column(Boolean, default=True)  



# === Region Code ===
class RegionCode(Base):
    __tablename__ = 'region_codes'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    code = Column(String, nullable=False)
    label = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)    



# === Department Code ===
class DepartmentCode(Base):
    __tablename__ = 'department_codes'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    code = Column(String, nullable=False)
    label = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)   



# === Author Code ===
class AuthorCode(Base):
    __tablename__ = 'author_codes'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    code = Column(String, nullable=False)
    label = Column(String, nullable=False)
    is_active = Column(Boolean, default=True) 



# === Lighting Company Code ===
class LightingCompanyCode(Base):
    __tablename__ = 'lighting_company_codes'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    code = Column(String, nullable=False)
    label = Column(String, nullable=False)
    is_active = Column(Boolean, default=True) 