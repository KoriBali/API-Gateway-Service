from pydantic import BaseModel, Field

class OpeningPartRequest(BaseModel):
    diameter_luar: float = Field(..., gt=0, description="Diamter in mm")
    tebal_dinding: float = Field(..., gt=0, description="Tebal dinding in mm")
    tinggi_lubang: float = Field(..., gt=0, description="Tinggi lubang in mm")
    lebar_lubang: float = Field(..., gt=0)
    posisi_lubang_dari_dasar: float = Field(..., gt=0)
    tegangan_leleh: float = Field(..., gt=0)
    modulus_elastisitas: float = Field(..., gt=0)
    faktor_keamanan: float = Field(..., gt=0)
    momen_lentur: float = Field(..., gt=0)
    gaya_aksial: float = Field(..., gt=0)
    


# class OpeningPartData(BaseModel):
#     conclusion: str
#     details: Dict[str, Any]

class OpeningPartResponse(BaseModel):
    data: dict
    success: bool
    message : str
    

class OpeningPartResponseStatus(BaseModel):
    data: dict
    status: str
    message : str
    