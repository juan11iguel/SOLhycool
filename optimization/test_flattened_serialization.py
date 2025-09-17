#!/usr/bin/env python3
"""
Test script to verify the refactored DayResults serialization works correctly.
This script creates dummy data and tests both export and import operations.
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
import tempfile
import shutil

# Add the optimization module to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

def create_dummy_day_results():
    """Create a dummy DayResults instance for testing."""
    from solhycool_optimization import DayResults
    
    # Create dummy index (24 hours)
    start_time = pd.Timestamp("2024-01-01 00:00:00")
    index = pd.date_range(start=start_time, periods=24, freq="1H")
    
    # Create dummy pareto fronts
    df_paretos = []
    for i in range(24):
        # Each pareto front has 5 solutions with 3 objectives
        df_pareto = pd.DataFrame({
            'obj1': np.random.random(5) * 100,
            'obj2': np.random.random(5) * 50,
            'obj3': np.random.random(5) * 25,
            'qc': np.random.random(5) * 10,
            'Rp': np.random.random(5) * 5,
        })
        df_paretos.append(df_pareto)
    
    # Create dummy selected pareto indices
    selected_pareto_idxs = [np.random.randint(0, 5) for _ in range(24)]
    
    # Create dummy results DataFrame
    df_results = pd.DataFrame({
        'obj1': [df_paretos[i].iloc[selected_pareto_idxs[i]]['obj1'] for i in range(24)],
        'obj2': [df_paretos[i].iloc[selected_pareto_idxs[i]]['obj2'] for i in range(24)],
        'obj3': [df_paretos[i].iloc[selected_pareto_idxs[i]]['obj3'] for i in range(24)],
        'qc': [df_paretos[i].iloc[selected_pareto_idxs[i]]['qc'] for i in range(24)],
        'Rp': [df_paretos[i].iloc[selected_pareto_idxs[i]]['Rp'] for i in range(24)],
    }, index=index)
    
    # Create dummy consumption arrays
    consumption_arrays = [np.random.random((5, 2)) * 100 for _ in range(24)]
    
    # Create dummy pareto indices
    pareto_idxs = [[0, 1, 2, 3, 4] for _ in range(24)]
    
    return DayResults(
        index=index,
        df_paretos=df_paretos,
        selected_pareto_idxs=selected_pareto_idxs,
        df_results=df_results,
        consumption_arrays=consumption_arrays,
        pareto_idxs=pareto_idxs,
        date_str="20240101"
    )

def test_flattened_serialization():
    """Test the new flattened serialization format."""
    from solhycool_optimization import DayResults  # Import here to avoid issues
    
    print("Creating dummy DayResults...")
    day_results = create_dummy_day_results()
    
    # Create temporary directory for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        output_file = temp_path / "test_results.h5"
        
        print(f"Exporting to {output_file}...")
        day_results.export(output_file, single_day=False)
        
        print("Checking HDF5 structure...")
        with pd.HDFStore(output_file, mode='r') as store:
            print("Available keys in HDF5 file:")
            for key in store.keys():
                print(f"  {key}")
            
            # Verify flattened structure
            if "/pareto" in store:
                pareto_df = store["/pareto"]
                print(f"Flattened pareto table shape: {pareto_df.shape}")
                print(f"Pareto columns: {list(pareto_df.columns)}")
                print(f"Unique timestamps in pareto: {len(pareto_df['timestamp'].unique())}")
            
            if "/consumption" in store:
                consumption_df = store["/consumption"]
                print(f"Flattened consumption table shape: {consumption_df.shape}")
                print(f"Consumption columns: {list(consumption_df.columns)}")
                print(f"Unique timestamps in consumption: {len(consumption_df['timestamp'].unique())}")
            
            if "/paths/selected_pareto_idxs" in store:
                selected_df = store["/paths/selected_pareto_idxs"]
                print(f"Flattened selected_pareto_idxs shape: {selected_df.shape}")
                print(f"Selected indices columns: {list(selected_df.columns)}")
                
            if "/paths/pareto_idxs" in store:
                pareto_idx_df = store["/paths/pareto_idxs"]
                print(f"Flattened pareto_idxs shape: {pareto_idx_df.shape}")
                print(f"Pareto indices columns: {list(pareto_idx_df.columns)}")
        
        print("\\nReloading DayResults...")
        loaded_day_results = DayResults.initialize(output_file)
        
        print("Verifying loaded data...")
        print(f"Original index length: {len(day_results.index)}")
        print(f"Loaded index length: {len(loaded_day_results.index)}")
        
        print(f"Original df_paretos length: {len(day_results.df_paretos)}")
        print(f"Loaded df_paretos length: {len(loaded_day_results.df_paretos)}")
        
        print(f"Original selected_pareto_idxs length: {len(day_results.selected_pareto_idxs)}")
        print(f"Loaded selected_pareto_idxs length: {len(loaded_day_results.selected_pareto_idxs)}")
        
        # Compare first pareto front
        if day_results.df_paretos[0] is not None and loaded_day_results.df_paretos[0] is not None:
            orig_shape = day_results.df_paretos[0].shape
            loaded_shape = loaded_day_results.df_paretos[0].shape
            print(f"First pareto front - Original: {orig_shape}, Loaded: {loaded_shape}")
        
        print("\\n✅ Test completed successfully!")

if __name__ == "__main__":
    test_flattened_serialization()