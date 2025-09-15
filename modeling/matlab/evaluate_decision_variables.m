function [dv_list, consumption_list] = evaluate_decision_variables(step_idx, env_vars, dv_values, date_str, options_struct, options)
    % EVALUATE_DECISION_VARIABLES Evaluates decision variables for a given step
    %
    % Inputs:
    %   step_idx        - Step index (integer)
    %   env_vars        - Structure containing environment variables:
    %                     .Tamb_C  - Ambient temperature (°C)
    %                     .HR_pp   - Relative humidity (%)
    %                     .mv_kgh  - Steam mass flow rate (kg/h)
    %                     .Tv_C    - Vapour temperature (°C)
    %   dv_values       - Structure containing decision variable arrays:
    %                     .qc      - Array of cooling flow rates (m³/h)
    %                     .Rp      - Array of parallel distribution ratios (-)
    %                     .Rs      - Array of series distribution ratios (-)
    %                     .wdc     - Array of DC fan percentages (%)
    %   total_num_evals - Total number of evaluations (for progress display)
    %   date_str        - Date string for display purposes
    %   options         - Optional parameters (struct)
    %
    % Outputs:
    %   dv_list         - Cell array of valid decision variable structures
    %   consumption_list- Cell array with two elements:
    %                     {1} - Array of water consumption values (l/h)
    %                     {2} - Array of electrical consumption values (kWe)
    
    arguments (Input)
        step_idx (1,1) double {mustBeNonnegative}
        env_vars (1,1) struct
        dv_values (1,1) struct
        date_str (1,:) char
        options_struct = []
        options.show_progress (1,1) logical = true
    end
    
    arguments (Output)
        dv_list (1,:) cell
        consumption_list (1,2) cell
    end
    
    % Add dependencies
    % addpath(genpath('utils'));
    % addpath(genpath('component_models'));

    wct_model = [];
    if ~isempty(options_struct)
        if isfield(options_struct, "wct_model_data_path")
            wct_model=load(options_struct.wct_model_data_path, "model");
        end
    end
    
    % Initialize output variables
    dv_list = {};
    consumption_list = {[], []};  % {water_consumption, electrical_consumption}
    
    % Extract environment variables
    Tamb_C = env_vars.Tamb_C;
    HR_pp = env_vars.HR_pp;
    mv_kgh = env_vars.mv_kgh;
    Tv_C = env_vars.Tv_C;
    
    % Extract decision variable arrays
    qc_array = dv_values.qc;
    Rp_array = dv_values.Rp;
    Rs_array = dv_values.Rs;
    wdc_array = dv_values.wdc;
    
    % Calculate total combinations
    n_qc = length(qc_array);
    n_Rp = length(Rp_array);
    n_Rs = length(Rs_array);
    n_wdc = length(wdc_array);
    total_combinations = n_qc * n_Rp * n_Rs * n_wdc;
    
    % Initialize progress tracking
    valid_candidates = 0;
    current_eval = 0;
    start_time = tic;  % Start timing
    
    if options.show_progress
        fprintf('%s | Step %02d: Starting evaluation of %d combinations\n', ...
                date_str, step_idx, total_combinations);
    end
    
    % Nested loops to evaluate all combinations
    for i_qc = 1:n_qc
        qc_val = qc_array(i_qc);
        
        for i_Rp = 1:n_Rp
            Rp_val = Rp_array(i_Rp);
            
            for i_Rs = 1:n_Rs
                Rs_val = Rs_array(i_Rs);
                
                for i_wdc = 1:n_wdc
                    wdc_val = wdc_array(i_wdc);
                    current_eval = current_eval + 1;
                    
                    % Evaluate operation point
                    % try
                        [Ce_kWe, Cw_lh, detailed, valid] = evaluate_operation(...
                            Tamb_C, HR_pp, mv_kgh, qc_val, Rp_val, Rs_val, wdc_val, Tv_C, options_struct, wct_model=wct_model.model);
                        
                        if valid
                            % Create decision variables structure with actual values
                            dv_struct = struct();
                            dv_struct.qc = detailed.qc;
                            dv_struct.Rp = detailed.Rp;
                            dv_struct.Rs = detailed.Rs;
                            dv_struct.wdc = detailed.wdc;
                            dv_struct.wwct = detailed.wwct;
                            
                            % Add to valid list
                            dv_list{end+1} = dv_struct;
                            consumption_list{1}(end+1) = Cw_lh;
                            consumption_list{2}(end+1) = Ce_kWe;
                            valid_candidates = valid_candidates + 1;
                        end
                        
                    % catch ME
                    %    if ~options.silence_warnings
                    %        warning('evaluate_decision_variables:evaluation_failed', ...
                    %                'Evaluation failed for qc=%.2f, Rp=%.2f, Rs=%.2f, wdc=%.2f: %s', ...
                    %                qc_val, Rp_val, Rs_val, wdc_val, ME.message);
                        % end
                    % end
                end
            end
        end
        
        % Update progress periodically
        if options.show_progress && mod(i_qc, max(1, floor(n_qc/10))) == 0
            progress_pct = (i_qc / n_qc) * 100;
            elapsed_time = toc(start_time);
            evals_completed = (i_qc - 1) * n_Rp * n_Rs * n_wdc + n_Rp * n_Rs * n_wdc;
            evals_per_sec = evals_completed / elapsed_time;
            fprintf('%s | Step %02d: %.1f%% complete, %d valid candidates found, %.1f evals/sec\n', ...
                    date_str, step_idx, progress_pct, valid_candidates, evals_per_sec);
        end
    end
    
    if options.show_progress
        total_elapsed_time = toc(start_time);
        final_evals_per_sec = total_combinations / total_elapsed_time;
        fprintf('%s | Step %02d: Completed! Found %d valid candidates out of %d combinations (%.1f%%) in %.2f sec (%.1f evals/sec)\n', ...
                date_str, step_idx, valid_candidates, total_combinations, ...
                (valid_candidates/total_combinations)*100, total_elapsed_time, final_evals_per_sec);
    end
    
    % Convert consumption lists to column vectors for consistency
    consumption_list{1} = consumption_list{1}(:);
    consumption_list{2} = consumption_list{2}(:);
end