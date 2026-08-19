# app/mappers/staging_entity_mapper.py
import uuid
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from datetime import datetime
from app.modules.load_object.schemas import LoadObjectRequest
from app.database.models import (
    StagingProject, StagingCondition, StagingStepPole, 
    StagingHighEval, StagingDirectObject, 
    StagingCalculationResult,StagingPoleResult, StagingDirectObjectResult
)

from app.modules.load_object.schemas import StagingDataResponseSchema

class StagingEntityMapper:
    @staticmethod
    def map_to_entities(payload: LoadObjectRequest, calc_result: dict) -> StagingProject:
        # Parsing date dari string ke Date object (YYYY-MM-DD)
        proj_date = datetime.strptime(payload.project.project_date, "%Y-%m-%d").date() if payload.project.project_date else None

        # Check apakah ada session_id in payload
        current_id = payload.session_id if payload.session_id else str(uuid.uuid4())

        # 1. Buat Parent (project)
        project_entity = StagingProject(
            id = current_id,
            title=payload.project.project_title,
            date=proj_date,
            report_number=payload.project.report_number,
        )

        # 2. Buat Relasi Condition 1:1
        project_entity.condition = StagingCondition(
            design_standard=payload.condition.design_standard,
            wind_speed=payload.condition.design_wind_speed,
            air_density=payload.condition.design_air_density
        )

        # 3. mapping input & simpan referensi dictionary
        poles_map = {} 
        for p in payload.poles:
            pole_entity = StagingStepPole(
                name=p.name, diameter=p.diameter, thickness=p.thickness,
                height=p.z_height, material=p.material, quantity=1 
            )
          
            project_entity.poles.append(pole_entity)
            poles_map[p.name] = pole_entity 

        direct_objs_map = {} 
        if payload.direct_objects:
            for obj in payload.direct_objects:
                do_entity = StagingDirectObject(
                    name=obj.name, front_area=obj.area, side_area=obj.area,
                    height=obj.z_height, weight=obj.weight, coefficient=obj.cf, quantity=1
                )
                project_entity.direct_objects.append(do_entity)
                direct_objs_map[obj.name] = do_entity
            

        # 4. arrange evaluasi dan hasil kalkulasi
        for eval_name, eval_point in payload.high_evaluation.items():
            
            # A. Buat Entitas High Eval (Input)
            eval_entity = StagingHighEval(name=eval_name, point_evaluate=eval_point)
            
            # B. Ambil data hasil kalkulasi dari Flask untuk evaluasi ini
            eval_result_data = calc_result.get(eval_name, {})
            
            # C. Buat Entitas Result Utama
            calc_result_entity = StagingCalculationResult(
                total_windload=eval_result_data.get("total_windload", 0.0),
                total_moment=eval_result_data.get("total_moment", 0.0),
                status=eval_result_data.get("status", "ok").lower()
            )
            
            # D. Mapping Pole Results (Relasi Berlian)
            for obj_res in eval_result_data.get("objects", []):
                obj_name = obj_res.get("name")
                
                # check pole
                related_pole = poles_map.get(obj_name) 
                if related_pole:
                    pole_res_entity = StagingPoleResult(
                        windload=obj_res.get("windload", 0.0),
                        moment=obj_res.get("moment", 0.0)
                    )
                    pole_res_entity.step_pole = related_pole 
                    calc_result_entity.pole_results.append(pole_res_entity)
                    continue 

                # check direct object
                related_do = direct_objs_map.get(obj_name) 
                if related_do:
                    do_res_entity = StagingDirectObjectResult(
                        windload=obj_res.get("windload", 0.0),
                        moment=obj_res.get("moment", 0.0)
                    )
                    do_res_entity.direct_object = related_do 
                    calc_result_entity.direct_object_results.append(do_res_entity)

            # F. Sambungkan semua dan masukkan ke Project
            eval_entity.calculation_result = calc_result_entity
            project_entity.high_evals.append(eval_entity)


        return project_entity
    

    @staticmethod
    def build_load_object_query(session_id: str):
        """Menyusun query relasi spesifik untuk tiang (load object)."""
        stmt = select(StagingProject).where(StagingProject.id == session_id).options(
            selectinload(StagingProject.condition),
            selectinload(StagingProject.high_evals)
                .selectinload(StagingHighEval.calculation_result)
                    .selectinload(StagingCalculationResult.pole_results)
                        .selectinload(StagingPoleResult.step_pole), 
            selectinload(StagingProject.high_evals)
                .selectinload(StagingHighEval.calculation_result)
                    .selectinload(StagingCalculationResult.direct_object_results)
                        .selectinload(StagingDirectObjectResult.direct_object) 
        )
        return stmt

    @staticmethod
    def format_load_object_response(project) -> StagingDataResponseSchema:
        """Translasi data mentah DB menjadi Pydantic Response."""
        
        # Helper function kita jadikan inner function agar rapi
        def map_pole_result(p):
            pole = p.step_pole
            return {
                "type": "pole",
                "name": pole.name if pole else "Unknown Pole",
                "moment": p.moment,
                "windload": p.windload,
                "diameter": pole.diameter if pole else None,
                "thickness": pole.thickness if pole else None,
                "material": pole.material if pole else None,
                "height": pole.height if pole else None,
                "quantity": pole.quantity if pole else None,
            }

        def map_direct_object_result(d):
            obj = d.direct_object
            return {
                "type": "direct_object",
                "name": obj.name if obj else "Unknown Object",
                "moment": d.moment,
                "windload": d.windload,
                "front_area": obj.front_area if obj else None,
                "side_area": obj.side_area if obj else None,
                "coefficient": obj.coefficient if obj else None,
                "weight": obj.weight if obj else None,
                "quantity": obj.quantity if obj else None,
            }

        high_eval_list = []
        for h in project.high_evals:
            calc = h.calculation_result
            objects = []
            if calc:
                objects.extend(map_pole_result(p) for p in calc.pole_results)
                objects.extend(map_direct_object_result(p) for p in calc.direct_object_results)

            high_eval_list.append({
                "name": h.name,
                "status": calc.status if calc else "N/A",
                "totalMoment": calc.total_moment if calc else 0.0,
                "totalWindload": calc.total_windload if calc else 0.0,
                "zRef": h.point_evaluate, 
                "objects": objects
            })

        return StagingDataResponseSchema(
            project={
                "title": project.title,
                "report_number": project.report_number,
                "date": project.date, 
                "project_type": project.project_type
            },
            condition={
                "design_standard": project.condition.design_standard,
                "wind_speed": project.condition.wind_speed,
                "air_density": project.condition.air_density
            },
            high_evaluations=high_eval_list
        )