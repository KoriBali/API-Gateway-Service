from pydantic import BaseModel

class Mapper:
    
    @staticmethod
    def to_pure_calculation_payload(payload: BaseModel) -> dict:
        """
        Memisahkan metadata bisnis dan hanya mengambil payload murni 
        Project dan Condition
        """
        
        full_dict = payload.model_dump()

        # Keluarkan project karena itu adalah meta data
        full_dict.pop("project", None)
        return full_dict

    @staticmethod
    def to_frontend_response_layout(calculation_result: dict, session_id: str) -> dict:
        """
        Menyusun layout response akhir untuk frontend dengan menyisipkan session_id.
        """
        response_data = calculation_result.copy() if calculation_result else {}
        response_data["session_id"] = session_id
        return response_data