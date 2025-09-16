% EXAMPLE_EVALUATE_DECISION_VARIABLES
% Example script showing how to use the evaluate_decision_variables function

clear; clc;

clear wct_model_data

% Add required paths
addpath(genpath('utils'));
addpath(genpath('component_models'));

%% Define environment variables for a single time step
env_vars = struct();
env_vars.Tamb_C = 25.0;  % Ambient temperature (°C)
env_vars.HR_pp = 50.0;   % Relative humidity (%)
env_vars.mv_kgh = 170;  % Steam mass flow rate (kg/h)
env_vars.Tv_C = 36.0;    % Vapour temperature (°C)

%% Define decision variable arrays (values to test)
dv_values = struct();
dv_values.qc = linspace(6, 24, 5);      % Cooling flow rates (m³/h) - 5 values
dv_values.Rp = linspace(0, 1, 5);       % Parallel distribution ratios (-) - 3 values
dv_values.Rs = linspace(0, 1, 5);       % Series distribution ratios (-) - 3 values  
dv_values.wdc = linspace(20, 90, 4);    % DC fan percentages (%) - 4 values

% Total combinations: 5 * 3 * 3 * 4 = 180

%% Set evaluation parameters
step_idx = 1;
total_num_evals = length(dv_values.qc) * length(dv_values.Rp) * ...
                  length(dv_values.Rs) * length(dv_values.wdc);
date_str = datestr(now, 'yyyymmdd');

% Options
options_struct = struct("silence_warnings", true, ...
    "wct_model_data_path", "/home/patomareao/development/SOLhycool/modeling/data/models_data/model_data_wct_fp_pilot_plant_radial_basis2_cascade.mat", ...
    "inverse_wct_model_data_path", "/home/patomareao/development/SOLhycool/modeling/data/models_data/model_data_wct_inverse_fp_pilot_plant_radial_basis2_cascade.mat"); %"/home/patomareao/development/SOLhycool/modeling/matlab/component_models/model_data_wct_fp_gaussian.mat");

%% Run evaluation
fprintf('Starting evaluation of decision variables...\n');
tic;

[dv_list, consumption_list] = evaluate_decision_variables(...
    step_idx, env_vars, dv_values, date_str, options_struct, show_progress=true);

elapsed_time = toc;

%% Display results
fprintf('\n=== RESULTS ===\n');
fprintf('Evaluation completed in %.2f seconds\n', elapsed_time);
fprintf('Found %d valid operating points out of %d total combinations\n', ...
        length(dv_list), total_num_evals);

if ~isempty(dv_list)
    fprintf('\nValid operating points summary:\n');
    fprintf('Water consumption range: %.2f - %.2f l/h\n', ...
            min(consumption_list{1}), max(consumption_list{1}));
    fprintf('Electrical consumption range: %.2f - %.2f kWe\n', ...
            min(consumption_list{2}), max(consumption_list{2}));
    
    % Display first few valid points
    n_display = min(5, length(dv_list));
    fprintf('\nFirst %d valid decision variable combinations:\n', n_display);
    fprintf('%-8s %-8s %-8s %-8s %-8s %-12s %-12s\n', ...
            'qc', 'Rp', 'Rs', 'wdc', 'wwct', 'Cw (l/h)', 'Ce (kWe)');
    fprintf('%-8s %-8s %-8s %-8s %-8s %-12s %-12s\n', ...
            repmat('-', 1, 8), repmat('-', 1, 8), repmat('-', 1, 8), ...
            repmat('-', 1, 8), repmat('-', 1, 8), repmat('-', 1, 12), repmat('-', 1, 12));
    
    for i = 1:n_display
        dv = dv_list{i};
        fprintf('%-8.2f %-8.2f %-8.2f %-8.2f %-8.2f %-12.2f %-12.2f\n', ...
                dv.qc, dv.Rp, dv.Rs, dv.wdc, dv.wwct, ...
                consumption_list{1}(i), consumption_list{2}(i));
    end
    
    %% Create a simple scatter plot of the results
    if length(consumption_list{1}) > 1
        figure('Name', 'Decision Variables Evaluation Results');
        scatter(consumption_list{1}, consumption_list{2}, 50, 'filled');
        xlabel('Water Consumption (l/h)');
        ylabel('Electrical Consumption (kWe)');
        title('Valid Operating Points - Water vs Electrical Consumption');
        grid on;
        
        % Add some statistics to the plot
        mean_Cw = mean(consumption_list{1});
        mean_Ce = mean(consumption_list{2});
        hold on;
        plot(mean_Cw, mean_Ce, 'rx', 'MarkerSize', 15, 'LineWidth', 3);
        legend('Valid Points', 'Mean Point', 'Location', 'best');
        hold off;
    end
    
else
    fprintf('No valid operating points found!\n');
    fprintf('Try adjusting the environment variables or decision variable ranges.\n');
end

%% Example of how to access individual results
if ~isempty(dv_list)
    fprintf('\n=== ACCESSING INDIVIDUAL RESULTS ===\n');
    fprintf('Example - First valid point:\n');
    first_dv = dv_list{1};
    fprintf('  Decision Variables: qc=%.2f, Rp=%.2f, Rs=%.2f, wdc=%.2f, wwct=%.2f\n', ...
            first_dv.qc, first_dv.Rp, first_dv.Rs, first_dv.wdc, first_dv.wwct);
    fprintf('  Consumptions: Water=%.2f l/h, Electrical=%.2f kWe\n', ...
            consumption_list{1}(1), consumption_list{2}(1));
end