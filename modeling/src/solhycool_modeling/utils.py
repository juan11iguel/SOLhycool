import pandas as pd


from datetime import datetime
from typing import Literal


def dump_in_span(vars_dict: dict, span: tuple[int, int] | tuple[datetime, datetime], return_format: Literal["values", "series"] = "values") -> dict:
        """
        Dump variables within a given span.

        Args:
            vars_dict: A dictionary containing the variables to dump.
            span: A tuple representing the range (indices or datetimes).
            return_format: Format of the returned values ("values" or "series").

        Returns:
            A new dictionary containing the filtered data.
        """
        if isinstance(span[0], datetime):
            # Ensure all attributes are pd.Series for datetime filtering
            for name, value in vars_dict.items():
                if not isinstance(value, pd.Series) and value is not None:
                    raise TypeError(f"All attributes must be pd.Series for datetime indexing: {name} is {type(value)}")

            # Extract the range
            dt_start, dt_end = span
            span_vars_dict = {
                name: value[(value.index >= dt_start) & (value.index < dt_end)]
                for name, value in vars_dict.items() if value is not None
            }
        else:
            # Assume numeric indices
            idx_start, idx_end = span
            span_vars_dict = {
                name: value[idx_start:idx_end]
                if isinstance(value, (pd.Series, np.ndarray)) else value
                for name, value in vars_dict.items()
            }

        if return_format == "values":
            span_vars_dict = {name: value.values if isinstance(value, pd.Series) else value for name, value in span_vars_dict.items()}

        return span_vars_dict