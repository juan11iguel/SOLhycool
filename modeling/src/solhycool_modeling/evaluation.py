"""
Python equivalent of evaluate_physical_model_wct.m

Generates output dataset using physical models to create data-driven models.
Uses parallel processing and timeout control for robust evaluation.

This script should be run from the modeling directory.

The script saves both raw and filtered results:
- wct_out_raw.csv: All evaluation results including invalid ones
- wct_out.csv: Filtered results with invalid entries removed

The filtering functionality can be used independently:
- Use WCTModelEvaluator.filter_invalid_results() static method
- Use WCTModelEvaluator.filter_from_csv() class method
- Use filter_existing_results() convenience function

Example usage:
    # Full evaluation workflow
    evaluator = WCTModelEvaluator(case_study_id="andasol_90MW")
    evaluator.run_evaluation()
    
    # Filter existing raw results without full initialization
    filtered_df = WCTModelEvaluator.filter_from_csv("path/to/wct_out_raw.csv")
    
    # Or use convenience function
    filter_existing_results("path/to/wct_out_raw.csv", "path/to/filtered_output.csv")
"""

import time
from pathlib import Path
from typing import Optional, Literal
from dataclasses import dataclass
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor, TimeoutError, as_completed

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from tqdm import tqdm
import psychrolib
from loguru import logger

# Import the MATLAB exported functions (required)
import combined_cooler

# Configure psychrolib
psychrolib.SetUnitSystem(psychrolib.SI)


@dataclass
class WCTModelEvaluator:
    """Wet Cooling Tower Model Evaluator with parallel processing."""
    
    # Input parameters with defaults
    case_study_id: str = "andasol_90MW"
    timeout: float = 3.0
    n_processes: Optional[int] = None
    base_path: Optional[Path] = None
    
    # Computed attributes (initialized in __post_init__)
    model_type: Literal["pilot_plant", "andasol"] = None
    save_electrical_consumption: bool = None
    input_data_path: Path = None
    output_data_path: Path = None
    cc_model: object = None  # MATLAB combined_cooler model instance
    
    def __post_init__(self):
        """Initialize computed attributes after dataclass construction."""
        # Validate case_study_id and set model configuration
        if self.case_study_id == "pilot_plant_200kW":
            self.model_type = "pilot_plant"
            self.save_electrical_consumption = False
        elif self.case_study_id == "andasol_90MW":
            self.model_type = "andasol"
            self.save_electrical_consumption = True
        else:
            raise ValueError(f"Invalid case_study_id '{self.case_study_id}'. "
                           "Options are: 'pilot_plant_200kW', 'andasol_90MW'")
        
        # Set default for n_processes
        if self.n_processes is None:
            self.n_processes = max(1, mp.cpu_count() - 1)
        
        # Initialize MATLAB model (required)
        self.cc_model = combined_cooler.initialize()
        logger.info("Successfully initialized combined_cooler model")
        
        # Set up paths
        if self.base_path is None:
            self.base_path = Path(f"../results/model_inputs_sampling/{self.case_study_id}")
        self.input_data_path = self.base_path / "wct_in.csv"
        self.output_data_path = self.base_path / "wct_out.csv"
        
        # Log initialization
        logger.info("Initialized WCT Model Evaluator:")
        logger.info(f"  Case study: {self.case_study_id}")
        logger.info(f"  Model type: {self.model_type}")
        logger.info(f"  Timeout: {self.timeout}s")
        logger.info(f"  Parallel processes: {self.n_processes}")
        logger.info("  MATLAB model initialized: True")
    
    def generate_parameter_combinations(self) -> pd.DataFrame:
        """
        Generate all combinations of parameters for evaluation.
        
        Returns:
            DataFrame with all parameter combinations
        """
        logger.info("Generating parameter combinations...")
        
        # Define parameter ranges
        Tamb = np.linspace(5, 50, 10)  # Ambient temperature (°C)
        HR = np.linspace(10, 90, 5)    # Relative humidity (%)
        deltaTwct_in = np.linspace(3, 20, 5)  # Delta above wet bulb (°C)
        Mwct = np.linspace(1152, 3960, 7)     # Water flow rate (m³/h)
        SC_fan_wct = np.linspace(20, 100, 7)  # Fan control (%)
        
        # Create all combinations using meshgrid
        tamb_grid, hr_grid, delta_grid, mwct_grid, fan_grid = np.meshgrid(
            Tamb, HR, deltaTwct_in, Mwct, SC_fan_wct, indexing='ij'
        )
        
        # Flatten arrays
        tamb_vec = tamb_grid.ravel()
        hr_vec = hr_grid.ravel()
        delta_vec = delta_grid.ravel()
        mwct_vec = mwct_grid.ravel()
        fan_vec = fan_grid.ravel()
        
        # Calculate wet bulb temperature and inlet temperature
        logger.info("Calculating wet bulb temperatures...")
        twb_vec = np.zeros_like(tamb_vec)
        twct_in_vec = np.zeros_like(tamb_vec)
        
        for i in tqdm(range(len(tamb_vec)), desc="Computing Twb"):
            twb_vec[i] = psychrolib.GetTWetBulbFromTDryBulb(tamb_vec[i], hr_vec[i]/100, 101325)
            twct_in_vec[i] = twb_vec[i] + delta_vec[i]
        
        # Create DataFrame
        wct_df = pd.DataFrame({
            'Tamb': tamb_vec,
            'HR': hr_vec,
            'Twct_in': twct_in_vec,
            'qwct': mwct_vec,
            'wwct': fan_vec,
            'Twb': twb_vec,
            'mw_ma_ratio': np.ones_like(tamb_vec)  # Placeholder
        })
        
        logger.info(f"Created {len(wct_df)} parameter combinations")
        logger.info("Parameter ranges:")
        logger.info(f"  Tamb: {wct_df.Tamb.min():.1f} to {wct_df.Tamb.max():.1f} °C")
        logger.info(f"  HR: {wct_df.HR.min():.1f} to {wct_df.HR.max():.1f} %")
        logger.info(f"  Twct_in: {wct_df.Twct_in.min():.1f} to {wct_df.Twct_in.max():.1f} °C")
        logger.info(f"  qwct: {wct_df.qwct.min():.0f} to {wct_df.qwct.max():.0f} m³/h")
        logger.info(f"  wwct: {wct_df.wwct.min():.1f} to {wct_df.wwct.max():.1f} %")
        
        return wct_df
    
    def load_input_data(self) -> pd.DataFrame:
        """Load input data from CSV file."""
        if not self.input_data_path.exists():
            raise FileNotFoundError(f"Input file not found: {self.input_data_path}")
        
        logger.info(f"Loading input data from: {self.input_data_path}")
        wct_df = pd.read_csv(self.input_data_path)
        
        # Remove first column if it's an index
        if wct_df.columns[0].lower() in ['index', 'unnamed: 0']:
            wct_df = wct_df.iloc[:, 1:]
        
        logger.info(f"Loaded {len(wct_df)} parameter combinations")
        return wct_df
    
    @staticmethod
    def evaluate_single_point(params: tuple) -> tuple[float, float, float, bool]:
        """
        Evaluate a single parameter combination using MATLAB functions.
        
        Args:
            params: Tuple of (tamb, hr, twct_in, qwct, wwct, model_type, cc_model)
            
        Returns:
            Tuple of (twct_out, mw_lost_lh, ce_kwe, success)
        """
        tamb, hr, twct_in, qwct, wwct, model_type, cc_model = params
        
        try:
            # Use MATLAB functions
            if model_type == "andasol":
                # Call wct_model_physical_andasol with 5 inputs
                twct_out, ce_kwe, mw_lost_lh = cc_model.wct_model_physical_andasol(
                    tamb, hr, twct_in, qwct, wwct
                )
            else:  # pilot_plant
                # Call wct_model_physical with 5 inputs
                twct_out, ce_kwe, mw_lost_lh = cc_model.wct_model_physical(
                    tamb, hr, twct_in, qwct, wwct
                )
            
            return float(twct_out), float(mw_lost_lh), float(ce_kwe), True
            
        except Exception as e:
            logger.error(f"Error in MATLAB model evaluation: {e}")
            return np.nan, np.nan, np.nan, False
    
    def evaluate_with_timeout(self, params: tuple) -> tuple[float, float, float, bool]:
        """
        Evaluate with timeout control.
        
        Args:
            params: Parameters for evaluation
            
        Returns:
            Evaluation results with success flag
        """
        try:
            with ProcessPoolExecutor(max_workers=1) as executor:
                future = executor.submit(self.evaluate_single_point, params)
                result = future.result(timeout=self.timeout)
                return result
        except TimeoutError:
            return np.nan, np.nan, np.nan, False
        except Exception:
            return np.nan, np.nan, np.nan, False
    
    def evaluate_all_combinations(self, wct_df: pd.DataFrame) -> pd.DataFrame:
        """
        Evaluate all parameter combinations in parallel.
        
        Args:
            wct_df: DataFrame with parameter combinations
            
        Returns:
            DataFrame with evaluation results
        """
        logger.info(f"Starting parallel evaluation with {self.n_processes} processes...")
        
        # Prepare parameters for parallel evaluation
        param_list = [
            (row.Tamb, row.HR, row.Twct_in, row.qwct, row.wwct, self.model_type, self.cc_model)
            for _, row in wct_df.iterrows()
        ]
        
        # Initialize result arrays
        n_points = len(wct_df)
        tout_simu = np.full(n_points, np.nan)
        mw_lost_lh = np.full(n_points, np.nan)
        ce_kwe = np.full(n_points, np.nan)
        
        # Parallel evaluation with progress bar
        start_time = time.time()
        
        with ProcessPoolExecutor(max_workers=self.n_processes) as executor:
            # Submit all tasks
            future_to_idx = {
                executor.submit(self.evaluate_with_timeout, params): idx
                for idx, params in enumerate(param_list)
            }
            
            # Collect results with progress bar
            with tqdm(total=n_points, desc="Evaluating combinations") as pbar:
                for future in as_completed(future_to_idx):
                    idx = future_to_idx[future]
                    try:
                        twct_out, mw_lost, ce, success = future.result()
                        
                        if success:
                            tout_simu[idx] = twct_out
                            mw_lost_lh[idx] = mw_lost
                            ce_kwe[idx] = ce
                        
                        # Update progress bar with detailed info
                        row = wct_df.iloc[idx]
                        pbar.set_postfix({
                            'q': f"{row.qwct:.0f}",
                            'w': f"{row.wwct:.0f}",
                            'Tout': f"{twct_out:.2f}" if success else "NaN"
                        })
                        
                    except Exception as e:
                        logger.warning(f"Error processing index {idx}: {e}")
                    
                    pbar.update(1)
        
        elapsed_time = time.time() - start_time
        logger.info(f"Evaluation completed in {elapsed_time:.1f} seconds")
        
        # Create output DataFrame
        wct_out = wct_df.copy()
        wct_out['Tout'] = tout_simu
        wct_out['m_w_lost'] = mw_lost_lh
        
        if self.save_electrical_consumption:
            wct_out['Ce'] = ce_kwe
        
        return wct_out
    
    @staticmethod
    def filter_invalid_results(wct_out: pd.DataFrame, x_std: float = 0.5) -> pd.DataFrame:
        """
        Filter invalid results based on physical constraints.
        
        Args:
            wct_out: DataFrame with evaluation results
            x_std: Threshold parameter for outlier detection (default: 0.5)
            
        Returns:
            Filtered DataFrame
        """
        logger.info("Filtering invalid results...")
        
        tol = 1e-10
        
        # Calculate statistics for water consumption filtering
        m_w_lost_all = wct_out['m_w_lost'].dropna()
        if len(m_w_lost_all) > 0:
            median_mw = m_w_lost_all.median()
            std_mw = m_w_lost_all.std()
            threshold_mw = median_mw + x_std * std_mw
        else:
            threshold_mw = np.inf
        
        # Detect invalid conditions
        invalid_nan = wct_out.isnull().any(axis=1)
        
        # Physical validity checks
        invalid_phys = (
            (np.abs(np.imag(wct_out['Tout'])) > tol) |
            (wct_out['Tout'] < 0) |
            (wct_out['m_w_lost'] < 0)
        )
        
        # Excessive water consumption
        invalid_mw = wct_out['m_w_lost'] > threshold_mw
        
        # Combine conditions
        invalid = invalid_nan | invalid_phys | invalid_mw
        
        logger.info(f"Invalid rows detected: {invalid.sum()} of {len(wct_out)}")
        
        # Filter DataFrame
        wct_out_filtered = wct_out[~invalid].copy()
        
        logger.info(f"Remaining valid rows: {len(wct_out_filtered)}")
        
        return wct_out_filtered
    
    def save_results(self, wct_out_raw: pd.DataFrame, wct_out_filtered: pd.DataFrame) -> None:
        """Save both raw and filtered results to CSV files."""
        # Ensure output directory exists
        self.output_data_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Define file paths for raw and filtered results
        raw_output_path = self.base_path / "wct_out_raw.csv"
        filtered_output_path = self.output_data_path  # This keeps the original name for filtered results
        
        # Save raw results
        wct_out_raw.to_csv(raw_output_path, index=False)
        logger.info(f"Raw results saved to {raw_output_path}, n={len(wct_out_raw)}")
        
        # Save filtered results
        wct_out_filtered.to_csv(filtered_output_path, index=False)
        logger.info(f"Filtered results saved to {filtered_output_path}, n={len(wct_out_filtered)}")
    
    @classmethod
    def filter_from_csv(cls, raw_csv_path: Path, x_std: float = 0.5) -> pd.DataFrame:
        """
        Load raw results from CSV and return filtered DataFrame.
        
        Args:
            raw_csv_path: Path to the raw CSV file
            x_std: Threshold parameter for outlier detection (default: 0.5)
            
        Returns:
            Filtered DataFrame
        """
        logger.info(f"Loading raw results from {raw_csv_path}")
        wct_out_raw = pd.read_csv(raw_csv_path)
        
        # Remove index column if present
        if wct_out_raw.columns[0].lower() in ['index', 'unnamed: 0']:
            wct_out_raw = wct_out_raw.iloc[:, 1:]
        
        logger.info(f"Loaded {len(wct_out_raw)} raw results")
        
        # Apply filtering
        return cls.filter_invalid_results(wct_out_raw, x_std)
    
    def create_visualization(self, wct_out_raw: pd.DataFrame, 
                           wct_out_filtered: pd.DataFrame) -> None:
        """
        Create interactive visualization of results.
        
        Args:
            wct_out_raw: Raw results before filtering
            wct_out_filtered: Filtered results
        """
        logger.info("Creating visualization...")
        
        # Create subplots
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=[
                'Temperature Results (Raw vs Filtered)',
                'Water Loss Results (Raw vs Filtered)',
                'Temperature vs Water Loss (Filtered)',
                'Parameter Distribution'
            ],
            specs=[[{"secondary_y": False}, {"secondary_y": False}],
                   [{"secondary_y": False}, {"secondary_y": False}]]
        )
        
        # Plot 1: Temperature results
        indices = np.arange(len(wct_out_raw))
        valid_indices = wct_out_raw.index.isin(wct_out_filtered.index)
        
        fig.add_trace(
            go.Scatter(
                x=indices,
                y=wct_out_raw['Tout'],
                mode='markers',
                name='Tout (raw)',
                marker=dict(color='blue', size=4, opacity=0.6),
                showlegend=True
            ),
            row=1, col=1
        )
        
        fig.add_trace(
            go.Scatter(
                x=indices[valid_indices],
                y=wct_out_filtered['Tout'],
                mode='markers',
                name='Tout (filtered)',
                marker=dict(color='darkblue', size=6, symbol='circle-open'),
                showlegend=True
            ),
            row=1, col=1
        )
        
        # Plot 2: Water loss results
        fig.add_trace(
            go.Scatter(
                x=indices,
                y=wct_out_raw['m_w_lost'],
                mode='markers',
                name='m_w_lost (raw)',
                marker=dict(color='red', size=4, opacity=0.6),
                showlegend=True
            ),
            row=1, col=2
        )
        
        fig.add_trace(
            go.Scatter(
                x=indices[valid_indices],
                y=wct_out_filtered['m_w_lost'],
                mode='markers',
                name='m_w_lost (filtered)',
                marker=dict(color='darkred', size=6, symbol='circle-open'),
                showlegend=True
            ),
            row=1, col=2
        )
        
        # Plot 3: Scatter plot of filtered results
        fig.add_trace(
            go.Scatter(
                x=wct_out_filtered['Tout'],
                y=wct_out_filtered['m_w_lost'],
                mode='markers',
                name='Tout vs m_w_lost',
                marker=dict(
                    color=wct_out_filtered['wwct'],
                    colorscale='Viridis',
                    colorbar=dict(title="Fan Control (%)", x=0.47),
                    size=6
                ),
                showlegend=True
            ),
            row=2, col=1
        )
        
        # Plot 4: Parameter distribution
        fig.add_trace(
            go.Histogram(
                x=wct_out_filtered['Tamb'],
                name='Tamb distribution',
                opacity=0.7,
                nbinsx=20
            ),
            row=2, col=2
        )
        
        # Update layout
        fig.update_layout(
            title=f'WCT Model Evaluation Results - {self.case_study_id}',
            height=800,
            showlegend=True
        )
        
        # Update axes labels
        fig.update_xaxes(title_text="Index", row=1, col=1)
        fig.update_yaxes(title_text="Temperature (°C)", row=1, col=1)
        fig.update_xaxes(title_text="Index", row=1, col=2)
        fig.update_yaxes(title_text="Water Loss (L/h)", row=1, col=2)
        fig.update_xaxes(title_text="Outlet Temperature (°C)", row=2, col=1)
        fig.update_yaxes(title_text="Water Loss (L/h)", row=2, col=1)
        fig.update_xaxes(title_text="Ambient Temperature (°C)", row=2, col=2)
        fig.update_yaxes(title_text="Count", row=2, col=2)
        
        # Save plot
        plot_path = self.base_path / 'wct_evaluation_results.html'
        fig.write_html(plot_path)
        logger.info(f"Visualization saved to {plot_path}")
        
        # Also create a simple summary plot
        self._create_summary_plot(wct_out_filtered)
    
    def _create_summary_plot(self, wct_out_filtered: pd.DataFrame) -> None:
        """Create a simple summary plot."""
        fig = px.scatter_3d(
            wct_out_filtered,
            x='Tamb',
            y='HR',
            z='Tout',
            color='m_w_lost',
            size='wwct',
            title=f'3D Parameter Space - {self.case_study_id}',
            labels={
                'Tamb': 'Ambient Temperature (°C)',
                'HR': 'Relative Humidity (%)',
                'Tout': 'Outlet Temperature (°C)',
                'm_w_lost': 'Water Loss (L/h)',
                'wwct': 'Fan Control (%)'
            }
        )
        
        # Save 3D plot
        plot_3d_path = self.base_path / 'wct_3d_results.html'
        fig.write_html(plot_3d_path)
        logger.info(f"3D visualization saved to {plot_3d_path}")
    
    def run_evaluation(self, use_existing_input: bool = True) -> None:
        """
        Run the complete evaluation process.
        
        Args:
            use_existing_input: If True, load input from CSV; if False, generate new combinations
        """
        logger.info(f"Starting WCT model evaluation for {self.case_study_id}")
        logger.info("=" * 60)
        
        # Load or generate input data
        if use_existing_input and self.input_data_path.exists():
            wct_df = self.load_input_data()
        else:
            wct_df = self.generate_parameter_combinations()
        
        # Evaluate all combinations
        wct_out_raw = self.evaluate_all_combinations(wct_df)
        
        # Filter invalid results
        wct_out_filtered = self.filter_invalid_results(wct_out_raw)
        
        # Save both raw and filtered results
        self.save_results(wct_out_raw, wct_out_filtered)
        
        # Create visualization
        self.create_visualization(wct_out_raw, wct_out_filtered)
        
        logger.info("=" * 60)
        logger.info("Evaluation completed successfully!")


def filter_existing_results(raw_csv_path: str, output_path: str = None, x_std: float = 0.5) -> None:
    """
    Convenience function to filter existing raw results without initializing the full evaluator.
    
    Args:
        raw_csv_path: Path to the raw CSV file
        output_path: Path to save filtered results (optional, defaults to same dir as raw with _filtered suffix)
        x_std: Threshold parameter for outlier detection (default: 0.5)
    """
    raw_path = Path(raw_csv_path)
    
    # Generate output path if not provided
    if output_path is None:
        output_path = raw_path.parent / f"{raw_path.stem}_filtered{raw_path.suffix}"
    else:
        output_path = Path(output_path)
    
    # Filter results using the static method
    filtered_df = WCTModelEvaluator.filter_from_csv(raw_path, x_std)
    
    # Save filtered results
    output_path.parent.mkdir(parents=True, exist_ok=True)
    filtered_df.to_csv(output_path, index=False)
    logger.info(f"Filtered results saved to {output_path}, n={len(filtered_df)}")
