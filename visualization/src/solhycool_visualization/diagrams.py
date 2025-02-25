from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from lxml import etree
from cairosvg import svg2png
from loguru import logger

from phd_visualizations.diagrams import (change_text,
                                         change_icon,
                                         find_object,
                                         change_line_width)
from phd_visualizations.diagrams.utils import get_y, round_to_nonzero_decimal

from solhycool_modeling import OperationPoint

@dataclass
class OperationLimits:
    # var_id: tuple[float, float]
    Tamb: tuple[float, float] = (0, 50)
    HR: tuple[float, float] = (0, 100)
    
    Ce: tuple[float, float] = (0, 14)
    Ce_dc: tuple[float, float] = (0, 4)
    Ce_wct: tuple[float, float] = (0, 4)
    Cw_wct: tuple[float, float] = (0, 350)
    Qc_released: tuple[float, float] = (0, 350)
    
    Tdc_out: tuple[float, float] = (15, 40)
    Twct_out: tuple[float, float] = (10, 40)
    
    qc: tuple[float, float] = (0, 25)
    qdc: tuple[float, float] = (0, 25)
    qdc_only: tuple[float, float] = (0, 25)
    qwct: tuple[float, float] = (0.0, 25)
    qwct_p: tuple[float, float] = (0.0, 25)
    qwct_s: tuple[float, float] = (0.0, 25)
    
    Rp: tuple[float, float] = (0., 1.)
    Rs: tuple[float, float] = (0., 1.)
    wdc: tuple[float, float] = (0, 100)
    wwct: tuple[float, float] = (0., 100)
    
class VarIdToLineId(Enum):
    qc = ['line_c_in', 'line_c_out', "line_pump_in"]
    qdc = ["line_dc_in", "line_dc_out"]
    qwct_p = ["line_r1"]
    qwct_s = ["line_r2_out2"]
    qdc_only = ["line_r2_out1"]
    qwct = ["line_wct_in", "line_wct_out"]
    
class VarIdToIconId(Enum):
    Ce_dc = "cost_e_dc"
    Ce_wct = "cost_e_wct"
    Cw_wct = "cost_w_wct"
    Qc_released = "cooling_req"
    wdc = "fan_dc"
    wwct = "fan_wct"
    Tamb = "temp_amb"
    HR = "hr_amb"
    Tdc_out = "temp_dc"
    Twct_out = "temp_wct"
    Rp = "valve_r1"
    Rs = "valve_r2"
    
class VarIdToTextId(Enum):
    Twct_in = "Twct_in"
    qwct = "qwct"
    qdc = "qdc"
    qc = "pump_c_text"
    Tc_in = "line_c_in_text"
    Tc_out = "line_c_out_text"
    

@dataclass
class WascopStateVisualizer:
    
    operation_point: OperationPoint
    
    operation_limits: OperationLimits = field(default_factory=OperationLimits)
    max_line_width:int = 15
    min_line_width:int = 1
    max_icon_size = 70
    min_icon_size = 30

    required_ids_in_diagram: list[str] = None
    diagram: etree.ElementTree = None
    operation_point_id: str = None
    
    def __post_init__(self,) -> None:
        
        self.required_ids_in_diagram = [
            *[line_id for item in VarIdToLineId for line_id in item.value],
            *[item.value for item in VarIdToIconId],
            *[item.value for item in VarIdToTextId]
        ]
        
        # Alias
        self.op = self.operation_point
        
        # TODO: Create id for operation point
        self.operation_point_id = "opXXX"
        
    def set_lines(self, diagram: etree.ElementTree = None) -> None:
        diagram = self.diagram if diagram is None else diagram

        for item in VarIdToLineId:
            var_id = item.name
            for line_id in item.value:
                line_width = get_y(
                    x = getattr(self.op, var_id),
                    xmin = getattr(self.operation_limits, var_id)[0],
                    xmax = getattr(self.operation_limits, var_id)[1],
                    ymin = self.min_line_width,
                    ymax = self.max_line_width
                )
                change_line_width(line_id, diagram=diagram, width=line_width, group=True, not_inplace=False)
            
            
    def set_icons(self, diagram: etree.ElementTree = None) -> None:
        diagram = self.diagram if diagram is None else diagram

        for item in VarIdToIconId:
            var_id = item.name
            icon_id = item.value
            value = getattr(self.op, var_id)
            max_value = getattr(self.operation_limits, var_id)[1]
            size = get_y(
                x = value,
                xmin = getattr(self.operation_limits, var_id)[0],
                xmax = max_value,
                ymin = self.min_icon_size,
                ymax = self.max_icon_size
            )
            unit = self.op.__dataclass_fields__[var_id].metadata.get('units', '')
            
            # Change text
            if var_id == "Qc_released":
                var_ids = ["Qc_released", "mv", "Tv"]
                units = [self.op.__dataclass_fields__[var_id].metadata.get('units', '') for var_id in var_ids]
                values = [getattr(self.op, var_id) for var_id in var_ids]
                text = " | ".join([f'{round_to_nonzero_decimal(value)} {unit}' for value, unit in zip(values, units)])
            elif isinstance(value, str):
                text = f'{value} {unit}'
            elif isinstance(value, int):
                text = f'{value} {unit}'
            else:
                text = f'{round_to_nonzero_decimal(value)} {unit}'

            change_icon(icon_id, diagram=diagram, size=size,  text=text, 
                        max_size=self.max_icon_size, max_value=max_value, 
                        include_boundary=True, group=True, not_inplace=False)
            
    def set_text_boxes(self, diagram: etree.ElementTree = None) -> None:
        diagram = self.diagram if diagram is None else diagram

        for item in VarIdToTextId:
            var_id = item.name
            text_id = item.value
            value = getattr(self.op, var_id)
            unit = self.op.__dataclass_fields__[var_id].metadata.get('units', '')
            text = f'{round_to_nonzero_decimal(value)} {unit}'
            change_text(text_id, diagram=diagram, new_text=text, not_inplace=False)
    
    def create_diagram(self, diagram: etree._Element | Path, output_path: Path = None, filename: str = None) -> str:
        
        assert isinstance(diagram, (etree._Element, Path)), 'diagram must be an instance of etree.ElementTree or Path'
        if isinstance(diagram, Path):
            diagram = etree.parse(diagram)
        self.diagram = diagram
            
        # Check all elements are available in the diagram
        # Really needed? It's already going to be "checked" in the set methods
        [find_object(object_id, diagram) for object_id in self.required_ids_in_diagram]
        
        self.set_lines()
        self.set_icons()
        self.set_text_boxes()
        
        # Export diagram
        if output_path is not None:
            output_path.mkdir(exist_ok=True)
            filename = filename or self.operation_point_id
            
            output_path = output_path / filename
            
            # Export to SVG
            diagram.write( output_path.with_suffix(".svg"), pretty_print=True )
            
            # Export to PNG
            svg2png(
                bytestring=etree.tostring(diagram),
                write_to=str(output_path.with_suffix(".png")), 
                output_width=1200, output_height=787, dpi=300, background_color='white'
            )
            
            logger.info(f'Diagram created and saved in {output_path}')
            
        return etree.tostring(self.diagram)