"""
Simplified evaluation module that closely matches the optimization pattern.
"""

import time
from pathlib import Path
from typing import Optional, Literal
from dataclasses import dataclass
import billiard as multiprocessing
from billiard import Pool
import numpy as np
import pandas as pd
from tqdm.auto import tqdm
import psychrolib
from loguru import logger

# Configure psychrolib
psychrolib.SetUnitSystem(psychrolib.SI)


def evaluate_single_point(params: tuple) -> tuple[int, float, float, float, bool]:
    """
    Evaluate a single parameter combination using MATLAB functions.
    
    Args:
        params: Tuple of (idx, tamb, hr, twct_in, qwct, wwct, model_type)
        
    Returns:
        Tuple of (idx, twct_out, mw_lost_lh, ce_kwe, success)
    """
    idx, tamb, hr, twct_in, qwct, wwct, model_type = params
    
    try:
        # Import MATLAB model in this process (exactly like optimization code)
        import combined_cooler
        cc_model = combined_cooler.initialize()
        
        # Use MATLAB functions
        if model_type == "andasol":
            twct_out, ce_kwe, mw_lost_lh = cc_model.wct_model_physical_andasol(
                tamb, hr, twct_in, qwct, wwct, {"silence_warnings": True}, nargout=3
            )
        else:  # pilot_plant
            twct_out, ce_kwe, mw_lost_lh = cc_model.wct_model_physical(
                tamb, hr, twct_in, qwct, wwct, {"silence_warnings": True}, nargout=3
            )
        
        return idx, float(twct_out), float(mw_lost_lh), float(ce_kwe), True
        
    except Exception as e:
        print(f"Error in MATLAB model evaluation for {model_type}: {e}")
        return idx, np.nan, np.nan, np.nan, False


def test_matlab_worker():
    """Test if MATLAB initialization works in a worker process."""
    try:
        import combined_cooler
        cc_model = combined_cooler.initialize()
        print(f"MATLAB initialization successful in worker process: {type(cc_model)}")
        return True
    except Exception as e:
        print(f"MATLAB initialization failed in worker process: {e}")
        return False


@dataclass
class WCTModelEvaluator:
    """Wet Cooling Tower Model Evaluator with parallel processing."""
    
    # Input parameters with defaults
    case_study_id: str = "andasol_90MW"
    timeout: float = 30.0
    n_processes: Optional[int] = None
    base_path: Optional[Path] = None
    save_interval: int = 50  # Robust evaluation. Save every 50 successful evaluations
    timeout_duration: float = 60.  # Robust evaluation. 1 minute timeout
    
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
            self.n_processes = max(1, multiprocessing.cpu_count() - 1)
        
        # Initialize MATLAB model (required)
        try:
            import combined_cooler
            self.cc_model = combined_cooler.initialize()
            logger.info("Successfully initialized combined_cooler model")
        except Exception as e:
            logger.error(f"Failed to initialize MATLAB model: {e}")
            raise
        
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

    def check_existing_results(self, wct_df: pd.DataFrame) -> tuple[pd.DataFrame, np.ndarray, np.ndarray]:
        """
        Check for existing results and determine which evaluations still need to be completed.
        
        Args:
            wct_df: Input parameter DataFrame
            
        Returns:
            Tuple of (existing_results_df, indices_to_evaluate, evaluation_status)
        """
        raw_output_path = self.base_path / "wct_out_raw.csv"
        n_total = len(wct_df)
        evaluation_status = np.zeros(n_total, dtype=int)  # 0=not evaluated, 1=failed, 2=success
        
        if not raw_output_path.exists():
            logger.info("No existing results found, will evaluate all combinations")
            return pd.DataFrame(), np.arange(n_total), evaluation_status
        
        try:
            existing_results = pd.read_csv(raw_output_path)
            logger.info(f"Found existing results file with {len(existing_results)} rows")
            
            # Remove first column if it's an unnamed index (but keep eval_index if present)
            if existing_results.columns[0].lower() in ['unnamed: 0']:
                existing_results = existing_results.iloc[:, 1:]
            
            # Check if we have evaluation_status column
            if 'evaluation_status' in existing_results.columns and 'eval_index' in existing_results.columns:
                # New format with explicit status tracking
                n_existing = min(len(existing_results), n_total)
                
                for i in range(n_existing):
                    if i < len(existing_results):
                        try:
                            # Safely convert eval_index to integer
                            eval_idx_val = existing_results.iloc[i]['eval_index']
                            if pd.isna(eval_idx_val):
                                continue  # Skip rows with NaN eval_index
                            
                            eval_idx = int(float(eval_idx_val))  # Convert via float first to handle decimal strings
                            if 0 <= eval_idx < n_total:
                                # Safely get evaluation_status
                                status_val = existing_results.iloc[i]['evaluation_status']
                                if not pd.isna(status_val):
                                    evaluation_status[eval_idx] = int(status_val)
                        except (ValueError, TypeError, OverflowError) as e:
                            logger.warning(f"Error processing row {i}: eval_index={existing_results.iloc[i]['eval_index']}, status={existing_results.iloc[i]['evaluation_status']}, error={e}")
                            continue
                
                # Only re-evaluate points that haven't been attempted (status 0)
                remaining_indices = np.where(evaluation_status == 0)[0]
                
                successful = (evaluation_status == 2).sum()
                failed = (evaluation_status == 1).sum()
                not_evaluated = (evaluation_status == 0).sum()
                
                logger.info(f"Existing results: {successful} successful, {failed} failed, {not_evaluated} not evaluated")
                logger.info(f"Will only evaluate {len(remaining_indices)} unattempted combinations")
                
            elif 'Tout' in existing_results.columns:
                # Legacy format - convert to new status system
                n_existing = min(len(existing_results), n_total)
                
                for i in range(n_existing):
                    if pd.isna(existing_results.iloc[i]['Tout']):
                        evaluation_status[i] = 1  # Assume NaN means failed
                    else:
                        evaluation_status[i] = 2  # Valid result means success
                
                # Only re-evaluate points that haven't been attempted
                remaining_indices = np.where(evaluation_status == 0)[0]
                logger.info(f"Converted legacy format: {len(remaining_indices)} remaining combinations")
                
            else:
                logger.warning("Existing results file missing required columns, will re-evaluate all")
                remaining_indices = np.arange(n_total)
            
            return existing_results, remaining_indices, evaluation_status
                
        except Exception as e:
            logger.warning(f"Error reading existing results: {e}, will re-evaluate all")
            return pd.DataFrame(), np.arange(n_total), evaluation_status

    def save_partial_results(self, wct_df: pd.DataFrame, tout_simu: np.ndarray, 
                           mw_lost_lh: np.ndarray, ce_kwe: np.ndarray, 
                           evaluation_status: np.ndarray) -> None:
        """
        Save current evaluation results to wct_out_raw.csv.
        
        Args:
            wct_df: Input parameter DataFrame
            tout_simu: Array of outlet temperatures
            mw_lost_lh: Array of water mass lost
            ce_kwe: Array of electrical consumption
            evaluation_status: Array indicating evaluation status (0=not evaluated, 1=failed, 2=success)
        """
        # Create output DataFrame
        wct_out = wct_df.copy()
        wct_out.insert(0, 'eval_index', range(len(wct_df)))  # Add explicit index column
        wct_out['Tout'] = tout_simu
        wct_out['m_w_lost'] = mw_lost_lh
        wct_out['evaluation_status'] = evaluation_status  # 0=not evaluated, 1=failed, 2=success
        
        if self.save_electrical_consumption:
            wct_out['Ce'] = ce_kwe
        
        # Save to file
        raw_output_path = self.base_path / "wct_out_raw.csv"
        raw_output_path.parent.mkdir(parents=True, exist_ok=True)
        wct_out.to_csv(raw_output_path, index=False)
        
        # Count results by status
        not_evaluated = (evaluation_status == 0).sum()
        failed = (evaluation_status == 1).sum()
        successful = (evaluation_status == 2).sum()
        logger.info(f"Saved partial results: {successful} successful, {failed} failed, {not_evaluated} not evaluated")

    def evaluate_all_combinations_robust(self, wct_df: pd.DataFrame, 
                                       indices_to_evaluate: np.ndarray = None) -> pd.DataFrame:
        """
        Robust evaluation with automatic restarts, timeout handling, and periodic saving.
        
        Args:
            wct_df: Input parameter DataFrame
            indices_to_evaluate: Optional array of indices to evaluate (if None, evaluates all)
            
        Returns:
            Complete results DataFrame
        """
        n_total = len(wct_df)
        
        # Initialize result arrays for the full dataset
        tout_simu = np.full(n_total, np.nan)
        mw_lost_lh = np.full(n_total, np.nan)
        ce_kwe = np.full(n_total, np.nan)
        evaluation_status = np.zeros(n_total, dtype=int)  # 0=not evaluated, 1=failed, 2=success
        
        # Load existing results if any
        existing_results, remaining_indices, existing_status = self.check_existing_results(wct_df)
        evaluation_status = existing_status.copy()
        
        if len(existing_results) > 0:
            # Pre-fill arrays with existing results based on eval_index if available
            if 'eval_index' in existing_results.columns:
                for _, row in existing_results.iterrows():
                    try:
                        # Safely convert eval_index to integer
                        eval_idx_val = row['eval_index']
                        if pd.isna(eval_idx_val):
                            continue
                        
                        eval_idx = int(float(eval_idx_val))
                        if 0 <= eval_idx < n_total:
                            # Only load data if the evaluation was successful (status = 2)
                            if 'evaluation_status' in existing_results.columns:
                                status_val = row['evaluation_status']
                                if pd.isna(status_val) or int(status_val) != 2:
                                    continue  # Skip failed or unevaluated entries
                            
                            # Safely load numerical results
                            if 'Tout' in existing_results.columns and not pd.isna(row['Tout']):
                                tout_simu[eval_idx] = float(row['Tout'])
                            if 'm_w_lost' in existing_results.columns and not pd.isna(row['m_w_lost']):
                                mw_lost_lh[eval_idx] = float(row['m_w_lost'])
                            if 'Ce' in existing_results.columns and self.save_electrical_consumption and not pd.isna(row['Ce']):
                                ce_kwe[eval_idx] = float(row['Ce'])
                    except (ValueError, TypeError, OverflowError) as e:
                        logger.warning(f"Error loading data for eval_index {row['eval_index']}: {e}")
                        continue
            else:
                # Legacy format - assume sequential indices
                n_existing = min(len(existing_results), n_total)
                if 'Tout' in existing_results.columns:
                    tout_simu[:n_existing] = existing_results['Tout'].values[:n_existing]
                if 'm_w_lost' in existing_results.columns:
                    mw_lost_lh[:n_existing] = existing_results['m_w_lost'].values[:n_existing]
                if 'Ce' in existing_results.columns and self.save_electrical_consumption:
                    ce_kwe[:n_existing] = existing_results['Ce'].values[:n_existing]
        
        # Use remaining indices if not explicitly provided
        if indices_to_evaluate is None:
            indices_to_evaluate = remaining_indices
        else:
            # Intersect provided indices with remaining indices
            indices_to_evaluate = np.intersect1d(indices_to_evaluate, remaining_indices)
        
        if len(indices_to_evaluate) == 0:
            logger.info("All evaluations already completed or attempted!")
            wct_out = wct_df.copy()
            wct_out.insert(0, 'eval_index', range(len(wct_df)))
            wct_out['Tout'] = tout_simu
            wct_out['m_w_lost'] = mw_lost_lh
            wct_out['evaluation_status'] = evaluation_status
            if self.save_electrical_consumption:
                wct_out['Ce'] = ce_kwe
            return wct_out
        
        logger.info(f"Starting robust evaluation of {len(indices_to_evaluate)} remaining combinations")
        
        # Set multiprocessing start method for MATLAB compatibility
        multiprocessing.set_start_method("spawn", force=True)
        
        # Tracking variables
        save_interval = self.save_interval
        timeout_duration = self.timeout_duration 
        successful_evaluations = 0
        
        # Convert indices to evaluate into parameter list
        param_list = [
            (idx, wct_df.iloc[idx].Tamb, wct_df.iloc[idx].HR, wct_df.iloc[idx].Twct_in, 
             wct_df.iloc[idx].qwct, wct_df.iloc[idx].wwct, self.model_type)
            for idx in indices_to_evaluate
        ]
        
        # Track which parameters still need evaluation
        remaining_params = param_list.copy()
        
        while remaining_params:
            logger.info(f"Starting pool with {len(remaining_params)} remaining evaluations")
            
            try:
                with Pool(processes=self.n_processes) as pool:
                    # Submit all jobs to the pool
                    async_results = [pool.apply_async(evaluate_single_point, (param,)) for param in remaining_params]
                    
                    # Track progress with periodic timeout checking
                    completed_in_this_batch = []
                    last_progress_time = time.time()
                    check_interval = 5.0  # Check every 5 seconds
                    
                    with tqdm(total=len(remaining_params), desc="Evaluating combinations") as pbar:
                        while async_results:
                            current_time = time.time()
                            
                            # Check for completed results (non-blocking)
                            completed_results = []
                            for i, async_result in enumerate(async_results):
                                if async_result.ready():
                                    try:
                                        result_idx, twct_out, mw_lost, ce, success = async_result.get()
                                        completed_results.append(i)
                                        
                                        # Update results and status based on success
                                        if success:
                                            tout_simu[result_idx] = twct_out
                                            mw_lost_lh[result_idx] = mw_lost
                                            ce_kwe[result_idx] = ce
                                            evaluation_status[result_idx] = 2  # Success
                                            successful_evaluations += 1
                                            last_progress_time = current_time
                                        else:
                                            # Mark as failed - don't re-evaluate
                                            evaluation_status[result_idx] = 1  # Failed
                                        
                                        completed_in_this_batch.append(result_idx)
                                        
                                        # Periodic saving
                                        if successful_evaluations > 0 and successful_evaluations % save_interval == 0:
                                            self.save_partial_results(wct_df, tout_simu, mw_lost_lh, ce_kwe, evaluation_status)
                                        
                                        pbar.update(1)
                                        pbar.set_postfix({
                                            'Success': success,
                                            'Tout': f"{twct_out:.2f}" if success else "NaN",
                                            'Total Success': successful_evaluations
                                        })
                                        
                                    except Exception as e:
                                        logger.error(f"Error getting result: {e}")
                                        completed_results.append(i)
                                        # Mark as failed
                                        param_idx = remaining_params[i][0]
                                        evaluation_status[param_idx] = 1
                                        pbar.update(1)
                            
                            # Remove completed results (in reverse order to maintain indices)
                            for i in reversed(completed_results):
                                async_results.pop(i)
                            
                            # Periodic timeout check - independent of result completion
                            if current_time - last_progress_time > timeout_duration:
                                logger.warning(f"No progress for {timeout_duration}s, terminating pool")
                                pool.terminate()
                                pool.join()
                                # Mark remaining jobs as not evaluated (they'll be retried)
                                for async_result in async_results:
                                    if not async_result.ready():
                                        # Find the corresponding parameter and mark as not evaluated
                                        for param in remaining_params:
                                            if evaluation_status[param[0]] == 0:  # Still not evaluated
                                                break  # Leave as 0 for retry
                                break
                            
                            # Sleep briefly to avoid busy waiting
                            if async_results:  # Only sleep if there are still pending results
                                time.sleep(min(check_interval, 1.0))
                        
                        # Update remaining parameters (remove completed ones)
                        remaining_params = [
                            param for param in remaining_params 
                            if param[0] not in completed_in_this_batch
                        ]
                        
                        if not remaining_params:
                            logger.info("All evaluations completed successfully!")
                            break
                            
            except Exception as e:
                logger.error(f"Pool error: {e}, restarting...")
                # Save current progress before restarting
                self.save_partial_results(wct_df, tout_simu, mw_lost_lh, ce_kwe, evaluation_status)
                time.sleep(2)  # Brief pause before restart
        
        # Final save
        self.save_partial_results(wct_df, tout_simu, mw_lost_lh, ce_kwe, evaluation_status)
        
        # Create final output DataFrame
        wct_out = wct_df.copy()
        wct_out.insert(0, 'eval_index', range(len(wct_df)))
        wct_out['Tout'] = tout_simu
        wct_out['m_w_lost'] = mw_lost_lh
        wct_out['evaluation_status'] = evaluation_status
        if self.save_electrical_consumption:
            wct_out['Ce'] = ce_kwe
        
        successful = (evaluation_status == 2).sum()
        failed = (evaluation_status == 1).sum()
        logger.info(f"Robust evaluation completed! Successful: {successful}, Failed: {failed}")
        return wct_out

    def evaluate_all_combinations(self, wct_df: pd.DataFrame) -> pd.DataFrame:
        """
        Evaluate all parameter combinations in parallel.
        Follows the exact pattern from optimization code.
        """
        # Set multiprocessing start method for MATLAB compatibility (like optimization code)
        multiprocessing.set_start_method("spawn", force=True)
        
        logger.info(f"Starting parallel evaluation with {self.n_processes} processes...")
        
        # Prepare parameters for parallel evaluation
        param_list = [
            (idx, row.Tamb, row.HR, row.Twct_in, row.qwct, row.wwct, self.model_type)
            for idx, (_, row) in enumerate(wct_df.iterrows())
        ]
        
        # Initialize result arrays
        n_points = len(wct_df)
        tout_simu = np.full(n_points, np.nan)
        mw_lost_lh = np.full(n_points, np.nan)
        ce_kwe = np.full(n_points, np.nan)
        
        # Use billiard Pool directly (exactly like optimization code)
        start_time = time.time()
        
        with Pool(processes=self.n_processes) as pool:
            # Use imap_unordered for parallel execution with real-time progress
            # This yields results as they become available, allowing real-time progress tracking
            with tqdm(total=n_points, desc="Evaluating combinations") as pbar:
                for result_idx, twct_out, mw_lost, ce, success in pool.imap_unordered(
                    evaluate_single_point, param_list
                ):
                    if success:
                        tout_simu[result_idx] = twct_out
                        mw_lost_lh[result_idx] = mw_lost
                        ce_kwe[result_idx] = ce
                    
                    pbar.update(1)
                    # Show current result in progress bar
                    pbar.set_postfix({
                        'Success': success,
                        'Tout': f"{twct_out:.2f}" if success else "NaN"
                    })
        
        elapsed_time = time.time() - start_time
        logger.info(f"Evaluation completed in {elapsed_time:.1f} seconds")
        
        # Create output DataFrame
        wct_out = wct_df.copy()
        wct_out['Tout'] = tout_simu
        wct_out['m_w_lost'] = mw_lost_lh
        
        if self.save_electrical_consumption:
            wct_out['Ce'] = ce_kwe
        
        return wct_out

    def run_evaluation(self, use_existing_input: bool = True, use_robust_evaluation: bool = True) -> None:
        """
        Run the complete evaluation process.
        
        Args:
            use_existing_input: Whether to use existing input file
            use_robust_evaluation: Whether to use robust evaluation with restarts and progress saving
        """
        logger.info(f"Starting WCT model evaluation for {self.case_study_id}")
        logger.info(f"Robust evaluation mode: {use_robust_evaluation}")
        logger.info("=" * 60)
        
        # Load input data
        if use_existing_input and self.input_data_path.exists():
            wct_df = self.load_input_data()
        else:
            raise NotImplementedError("Parameter generation not implemented in simplified version")
        
        # Evaluate all combinations
        if use_robust_evaluation:
            wct_out_raw = self.evaluate_all_combinations_robust(wct_df)
        else:
            wct_out_raw = self.evaluate_all_combinations(wct_df)
        
        # Save final results (robust evaluation already saves to wct_out_raw.csv)
        raw_output_path = self.base_path / "wct_out_raw.csv"
        if not use_robust_evaluation:
            raw_output_path.parent.mkdir(parents=True, exist_ok=True)
            wct_out_raw.to_csv(raw_output_path, index=False)
        
        logger.info(f"Final results available at {raw_output_path}, n={len(wct_out_raw)}")
        
        # Summary statistics
        if 'evaluation_status' in wct_out_raw.columns:
            successful = (wct_out_raw['evaluation_status'] == 2).sum()
            failed = (wct_out_raw['evaluation_status'] == 1).sum()
            not_evaluated = (wct_out_raw['evaluation_status'] == 0).sum()
            logger.info(f"Evaluation summary: {successful} successful, {failed} failed, {not_evaluated} not evaluated")
        else:
            valid_results = ~wct_out_raw['Tout'].isna()
            n_valid = valid_results.sum()
            logger.info(f"Evaluation summary: {n_valid}/{len(wct_out_raw)} successful evaluations")
        
        logger.info("=" * 60)
        logger.info("Evaluation completed successfully!")


def test():
    """Main function to run the evaluation."""
    # Test MATLAB in a separate process first
    logger.info("Testing MATLAB initialization in separate process...")
    
    with Pool(processes=1) as pool:
        result = pool.apply_async(test_matlab_worker)
        try:
            success = result.get(timeout=60)
            if not success:
                logger.error("MATLAB test failed, aborting evaluation")
                return
        except Exception as e:
            logger.error(f"MATLAB test error: {e}")
            return
    
    logger.info("MATLAB test passed, proceeding with evaluation...")
    
    # Configuration
    case_study_id = "andasol_90MW"
    timeout = 30.0
    n_processes = 2  # Use fewer processes for testing
    base_path = Path(f"/workspaces/SOLhycool/modeling/results/model_inputs_sampling/{case_study_id}")
    
    logger.info(f"Starting evaluation with {n_processes} processes and {timeout}s timeout")
    
    # Create evaluator
    evaluator = WCTModelEvaluator(
        case_study_id=case_study_id,
        timeout=timeout,
        n_processes=n_processes,
        base_path=base_path
    )
    
    # Run evaluation with robust mode enabled by default
    evaluator.run_evaluation(use_existing_input=True, use_robust_evaluation=True)