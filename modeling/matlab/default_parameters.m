function params = default_parameters()
    % DEFAULT_PARAMETERS  Returns a struct with default parameters for the cooling system model.
    %
    % Outputs:
    %   params  - Struct containing default bounds, coefficients, and paths for all components.
    
    % Default params initialization
    params = struct();
    
    % DC               "Tamb",    "Tin",   "q", "w_fan"
    params.dc_lb = 0.99*[3.0      25.0,    6.0,  11];
    params.dc_ub = 1.01*[50.0     45.0,    24.0, 99.1800];
    % wdc (%) -> Ce_dc (W)
    params.dc_ce_coeffs = [-0.0002431, 0.04761, -2.2, 48.63, -295.6];
    
    % WCT               "Tamb",     "HR",    "Tin",      "q",     "w_fan"
    params.wct_lb = 0.99*[3.0       1.0      25.0        6.0       21.0];
    params.wct_ub = 1.01*[50.0      99.0     45.0        24.0      93.4161];
    % wwct (%) -> Ce_wct (W)
    params.wct_ce_coeffs = [0.4118, -11.54, 189.4];

    % Condenser
    params.condenser_option = 6;
    params.condenser_A = 19.30; %%19.967-> https://collab.psa.es/f/174826 24/U;
    params.condenser_deltaTv_cout_min = 1;

    % Recirculation pump
    % w_c (%) -> Ce_c (W) 
    params.recirculation_coeffs = [0.1461, 5.763, -38.32, 227.8];
    
    % Paths
    models_folder = fullfile(fileparts(mfilename('fullpath')), "/component_models");
    params.dc_model_data_path = char(fullfile(models_folder, "dc_model_data.mat"));
    params.wct_model_data_path = char(fullfile(models_folder, "wct_model_data.mat"));
end

