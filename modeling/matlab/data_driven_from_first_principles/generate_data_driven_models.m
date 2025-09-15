%%
%   This script should be run with the current path set to the path of the
%   script
%   
%   Check the different sections of the script and run the desired scenario
%   (The first section always needs to be run)
%--------------------------------------------------------------------------

%% Common parameters
% clc; clear

% Important to run this at least one time!

global data_path models_data_path results_path %#ok<*NUSED>
global visualize_validation
global trainRatio valRatio testRatio
global train_algorithm
global filter_filenames
global system_to_model input_vars_idx output_vars_idx
global output_var_names output_vars_sensor_types
global data_validation_path

%% 1.1. DC - pilot plant using experimental data

% set_common_parameters
% set_dc_common_parameters
% 
% % Parameters
% configuration_types = ["simple"];
% alternatives = ["feedforward", "cascadeforwardnet", "gaussian", "random_forest", "gradient_boosting"];
% % alternatives = ["radial_basis2"];
% auxiliary_id = "";
% filename_to_test = "dc_exp2_data"; 
% 
% run("batch_training.m")

%% 1.2. DC - pilot plant using partial experimental datasets

% set_common_parameters
% set_dc_common_parameters
% 
% % Parameters
% data_path = "data/partial_datasets";
% filter_filenames=false;
% 
% configuration_types = ["simple"];
% alternatives = ["feedforward", "cascadeforwardnet", "gaussian", "random_forest", "gradient_boosting"];
% auxiliary_id = "";
% 
% filename_to_test = "dc_exp2_data_"; 
% 
% run("batch_training.m")


%% 1.3. DC - pilot plant using generated samples from first-principles model

set_common_parameters
set_dc_common_parameters

% Parameters
configuration_types = ["cascade"];
alternatives = ["gaussian"]; %#ok<*NBRAK2> 
auxiliary_id = "fp_pilot_plant_";
filename_to_test = "pilot_plant_200kW/dc_out"; 
visualize_validation = true;

run("batch_training.m")

%% 1.4. DC - commercial CSP using generated samples from first-principles model
% Nothing to evaluate! The scaled model is the same as the pilot plant just
% with more in parallel!!
%
% set_common_parameters
% set_dc_common_parameters
% 
% % Parameters
% configuration_types = ["simple"];
% alternatives = ["gaussian"]; %#ok<*NBRAK2> 
% auxiliary_id = "fp_andasol_75_";
% filename_to_test = "andasol_75_90MW/dc_out"; % "andasol_50_90MW/dc_out"; % andasol_50_90MW andasol_50_90MW
% 
% % No validation set available
% data_validation_path = []; 
% trainRatio = 0.7;
% valRatio = 0.15;
% testRatio = 0.15;
% visualize_validation = true;
% 
% run("batch_training.m")


%% 2.1. WCT - pilot plant using experimental data

% set_common_parameters
% set_wct_common_parameters
% 
% % Parameters
% configuration_types = ["cascade", "simple"];
% alternatives = ["feedforward", "cascadeforwardnet", "gaussian", "random_forest", "gradient_boosting", "radial_basis2"];
% auxiliary_id = "";
% filename_to_test = "wct_exp2_data"; 
% 
% run("batch_training.m")

%% 2.2. WCT - pilot plant using partial experimental datasets

% set_common_parameters
% set_wct_common_parameters
% 
% % Parameters
% data_path = "data/partial_datasets";
% filter_filenames=false;
% 
% configuration_types = ["cascade", "simple"];
% alternatives = ["feedforward", "cascadeforwardnet", "gaussian", "random_forest", "gradient_boosting", "radial_basis2"];
% auxiliary_id = "";
% filename_to_test = "wct_exp2_"; 
% 
% run("batch_training.m")


%% 2.2. WCT - pilot plant using generated samples from first-principles model

set_common_parameters
set_wct_common_parameters

% Parameters
configuration_types = ["cascade"];
alternatives = ["radial_basis2"]; % ["gaussian"]; %#ok<*NBRAK2> 
auxiliary_id = "fp_pilot_plant_";
filename_to_test = "pilot_plant_200kW/wct_out"; 
visualize_validation = true;

run("batch_training.m")

%% 2.3. WCT - comercial CSP using generated samples from first-principles model

set_common_parameters
set_wct_common_parameters

% Parameters
configuration_types = ["cascade"];
alternatives = ["gaussian"]; %#ok<*NBRAK2> 
auxiliary_id = "fp_andasol_";
filename_to_test = "andasol_90MW/wct_out"; % "andasol_50_90MW/dc_out"; % andasol_50_90MW andasol_50_90MW

% No validation set available
data_validation_path = []; 
trainRatio = 0.7;
valRatio = 0.15;
testRatio = 0.15;

% Add Ce to outputs
output_vars_idx = [6, 7];%, 8];
output_var_names = ["Tout", "Mlost"]; %, "Ce"];

visualize_validation = true;

run("batch_training.m")


%% Utility functions

function set_common_parameters()
    % Declare global variables
    global data_path models_data_path results_path
    global visualize_validation
    global trainRatio valRatio testRatio
    global train_algorithm
    global filter_filenames

    % Set values
    data_path = "../../results/model_inputs_sampling/";
    models_data_path = "../../data/models_data";
    results_path = "../../results/data_driven_models";

    visualize_validation = false;

    trainRatio = 0.8;
    valRatio = 0.2;
    testRatio = 0; % Taken directly from validation set

    train_algorithm = "trainbr"; % Used in ANNs

    filter_filenames = true; % To specify a filename to read instead of all csvs in the folder
end

function set_dc_common_parameters()
    % Declare global variables
    global system_to_model input_vars_idx output_vars_idx
    global output_var_names output_vars_sensor_types
    global data_validation_path

    % Set values
    system_to_model = "dc";
    input_vars_idx  = 1:4;
    output_vars_idx = [5];
    output_var_names = ["Tout"];
    output_vars_sensor_types = ["Pt100"];

    data_validation_path = "../../data/dc_exp3_exp.csv";
end

function set_wct_common_parameters()
    % Declare global variables
    global system_to_model input_vars_idx output_vars_idx
    global output_var_names output_vars_sensor_types
    global data_validation_path

    % Set values
    system_to_model = "wct";
    input_vars_idx  = 1:5;
    output_vars_idx = [6, 7];
    output_var_names = ["Tout", "Mlost"];
    output_vars_sensor_types = ["Pt100", "paddle_flow_meter", ""];

    data_validation_path = "../../data/wct_out_exp.csv";
end