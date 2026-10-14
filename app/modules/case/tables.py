from app.database.models.calculation import CalculationCase
from app.database.models.drawing import DrawingCase
from app.database.models.intake import DesignType
from app.database.models.workflow import WorkType

# Tabel case per work type. request_events.work_type menyebut tabel yang dirujuk case_id.
# Dipisah dari repository supaya workflow/gate.py bisa memakainya tanpa import melingkar.
CASE_MODEL = {
    WorkType.calculation: CalculationCase,
    WorkType.drawing: DrawingCase,
}

# work_scope putaran internal = work type case yang diperiksa.
ROUND_SCOPE = {
    WorkType.calculation: DesignType.calculation,
    WorkType.drawing: DesignType.drawing,
}
