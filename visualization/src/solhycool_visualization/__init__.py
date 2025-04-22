from enum import Enum

class ComponentColors(Enum):
    DC = "#83b366"
    WCT = "#9573a6"
    CONDENSER = "#CCCCCC"
    ELECTRICITY = "#FECB52"
    WATER = "#5AA9A2"
    TRANSPARENT = "rgba(0,0,0,0)"
    WATER1 = "#36D7F3"
    WATER2 = "#6c8ebf"
    
    
def reorder_dict(d: dict, key_to_move: str, new_position: int) -> dict:
    if key_to_move not in d:
        return d  # Return unchanged if the key is not in the dictionary
    
    items = list(d.items())  # Convert to list of tuples
    item = (key_to_move, d[key_to_move])  # Get the key-value pair
    items.remove(item)  # Remove it from the list
    items.insert(new_position, item)  # Insert it at the new position
    
    return dict(items)  # Convert back to dict


def insert_key_in_dict_at(d: dict, key: str, value, index: int) -> dict:
    items = list(d.items())
    items.insert(index, (key, value))
    return dict(items)