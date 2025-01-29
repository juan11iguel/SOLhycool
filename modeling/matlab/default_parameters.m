function params = default_parameters()
    % Default params initialization
    params = struct();
    
    % DC               "Tamb",    "Tin",   "q", "w_fan"
    params.dc_lb = 0.9*[9.0600    33.1600, 5.2211,  11];
    params.dc_ub = 1.1*[38.7500   41.9200, 24.1543, 99.1800];
    
    
    % WCT               "Tamb",     "HR",    "Tin",      "q",     "w_fan"
    params.wct_lb = 0.9*[9.0600    10.3300   31.1700    5.7049         0];
    params.wct_ub = 1.1*[38.7500   89.2500   40.9400   24.8400   93.4161];


    % Condenser
    params.condenser_option = 3;
    params.condenser_A = 19.30; %%19.967-> https://collab.psa.es/f/174826 24/U;
    
    % Paths
    models_folder = fullfile(fileparts(mfilename('fullpath')), "/component_models/data");
    params.dc_model_data_path = char(fullfile(models_folder, "dc_model_data.mat"));
    params.wct_model_data_path = char(fullfile(models_folder, "wct_model_data.mat"));
end

