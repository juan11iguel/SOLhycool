function [Ce_kWe, Cw_lh, detailed, valid] = evaluate_operation(Tamb_C, HR_pp, mv_kgh, qc_m3h, Rp, Rs, wdc, Tv_C, options_struct, options)
    % COMBINED_COOLER_MODEL Simulates the behavior of a cooling system.
    % The system is composed by a condenser and a combined cooler.
    %
    %   Inputs:
    %       Tamb_C      - Ambient temperature (°C)
    %       HR_pp       - Relative humidity in percentage, e.g., 50% (%)
    %       ms_kgh      - Steam mass flow rate (kg/h)
    %       qc_m3h      - Cooling flow rate (m³/h)
    %       Rs          - Series distribution ratio (-)
    %       Rp          - Parallel distribution ratio (-)
    %       wdc         - DC fan percentage (%)
    %       wwct        - WCT fan percentage (%)
    %       model_type  - Type of model to use ('first_principles' or 'data_based')
    %       parameters  - Model parameters such as limits, models data paths, etc (optional)
    %
    %   Outputs:
    %       Tv_C        - Vapour temperature in the condenser (°C)
    %       Ce_kWe      - Electrical consumption of the cooler (kWe)
    %       Cw_lh       - Water consumption (l/h)
    %       detailed    - Struct containing detailed simulation results
    %       valid       - Logical variable indicating feasibility of operation
    
    arguments (Input)
        Tamb_C (1,1) double {mustBeNonnegative, mustBeLessThanOrEqual(Tamb_C, 50)}
        HR_pp (1,1) double {mustBeNonnegative, mustBeLessThanOrEqual(HR_pp, 100)}
        mv_kgh (1,1) double {mustBePositive}
        qc_m3h (1,1) double {mustBePositive}
        Rp (1,1) double {mustBeGreaterThanOrEqual(Rp, 0.0), mustBeLessThanOrEqual(Rp, 1.0)}
        Rs (1,1) double {mustBeGreaterThanOrEqual(Rs, 0.0), mustBeLessThanOrEqual(Rs, 1.0)}
        wdc (1,1) double {mustBeGreaterThanOrEqual(wdc, 0.0), mustBeLessThanOrEqual(wdc, 100)}
        Tv_C (1,1) double {mustBeGreaterThanOrEqual(Tv_C, 20), mustBeLessThanOrEqual(Tv_C, 60)} = []

        % Using keyword arguments does not work when exporting the model to
        % python. Offer an alternative
        options_struct = []
        options.Qcc_Qc_relative_tol (1,1) double = 0.15
        options.resolution_mode (1,:) char {mustBeMember(options.resolution_mode, {'inverse', 'direct'})} = 'inverse'
        options.model_type (1,:) char {mustBeMember(options.model_type, {'physical', 'data'})} = 'data'
        % DC               "Tamb",    "Tin",   "q", "w_fan"
        options.dc_lb (1,4) double = 0.99*[3.0      25.0,    6.0,  11];
        options.dc_ub (1,4) double = 1.01*[50.0     55.0,    24.0, 99.1800];
        % wdc (%) -> Ce_dc (W)
        options.dc_ce_coeffs (1,:) double = [-0.0002431, 0.04761, -2.2, 48.63, -295.6];
        options.dc_n_dc  (1,1) double {mustBeInteger,mustBePositive} = 1;
        options.dc_nf (1,1) double {mustBePositive} = 1;
        
        % WCT                              "Tamb",     "HR",    "Tin",      "q",     "w_fan"
        options.wct_lb (1,5) double = 0.99*[3.0       1.0      25.0        6.0       21.0];
        options.wct_ub (1,5) double = 1.01*[50.0      99.0     55.0        24.0      93.4161];
        % wwct (%) -> Ce_wct (W)
        options.wct_ce_coeffs (1,:) double = [0.4118, -11.54, 189.4];
        options.wct_n_wct (1,1) double {mustBeInteger,mustBePositive} = 1;
        options.wct_model = []

        % Condenser
        options.condenser_option (1,1) int8 {mustBeInRange(options.condenser_option, 1, 9)} = 3;
        options.condenser_A (1,1) double {mustBePositive} = 19.30; % 19.967 -> https://collab.psa.es/f/174826 24/U;
        options.condenser_deltaTv_cout_min (1,1) double {mustBePositive} = 1;
        options.condenser_n_tb (1,1) double {mustBeInteger,mustBePositive} = 24;
    
        % Recirculation pump
        % w_c (%) -> Ce_c (W) 
        options.recirculation_coeffs (1,:) double = [0.1461, 5.763, -38.32, 227.8];
        
        % Paths
        options.dc_model_data_path = char(fullfile(fileparts(mfilename('fullpath')),  "/component_models", "model_data_dc_fp_gaussian.mat"));
        options.wct_model_data_path = char(fullfile(fileparts(mfilename('fullpath')), "/component_models", "model_data_wct_fp_gaussian.mat"));
        options.inverse_wct_model_data_path string = fullfile(fileparts(mfilename('fullpath')), "inverse_wct_model_data.mat")

        % Miscellaneous options
        options.raise_error_on_invalid_inputs (1,1) logical = false
        options.silence_warnings (1,1) logical = false
    end

    arguments (Output)
        Ce_kWe (1,1) double
        Cw_lh (1,1) double
        detailed (1,1) struct
        valid (1,1) logical
    end

    % Terrible
    % Apply optional arguments from the alternative options_struct if provided
    if ~isempty(options_struct)
        apply_options();
    end

    % Unpack options
    % parameters = options.parameters;
    model_type = options.model_type;
    silence_warnings = options.silence_warnings;

    % Add dependencies path
    addpath(genpath('utils'));
    addpath(genpath('component_models'));

    % Validate input parameters
    % validate_struct(default_parameters(), options);
    
    % Assign function handles
    condenser_model_fun   = @condenser_model;
    mixer_model_fun       = @mixer_model;
    wct_inverse_model_fun = @wct_inverse_model;

    switch model_type
        case "data"
            dc_model_fun = @dc_model_data;
        case "physical"
            dc_model_fun = @dc_model_physical;
        otherwise
            error("combined_cooler_model:invalid_option", ...
                  "Invalid model_type '%s'. Options are: 'data', 'physical'", model_type);
    end

    if silence_warnings
        warning('off','all') % disable all warnings
    end

    % Calculations
    valid = true;
    
    % Unit conversion
    mc_kgs = qc_m3h / 3.6;
    mv_kgs = mv_kgh / 3600;
    % Get flows from ratios
    [qdc, qwct, qwct_p, qwct_s] = ratios_to_flows(qc_m3h, Rp, Rs);

    % Calculate wwct
    % Condenser
    [Tc_in, Tc_out] = condenser_model_fun( ...
        mv_kgs, ...
        Tv_C, ...
        mc_kgs, ...
        option=options.condenser_option, ...
        A=options.condenser_A, ...
        n_tb=options.condenser_n_tb ...
    );
    Tcc_in = Tc_out;
    Tcc_out = Tc_in;
    % Validation
    if Tc_out >= Tv_C - options.condenser_deltaTv_cout_min
        valid = false;
        if ~silence_warnings
            fprintf('DEBUG: Condenser validation failed - Tc_out=%.2f >= Tv_C - deltaTv_cout_min=%.2f (Tv_C=%.2f, deltaTv_cout_min=%.2f)\n', ...
                    Tc_out, Tv_C - options.condenser_deltaTv_cout_min, Tv_C, options.condenser_deltaTv_cout_min);
        end
    end

    % DC
    Tdc_in = Tcc_in;
    [Tdc_out, ~] = dc_model_fun( ...
        Tamb_C, ...
        Tdc_in, ...
        qdc, ...
        wdc, ...
        model_data_path=options.dc_model_data_path, ...
        silence_warnings=silence_warnings, ...
        lb=options.dc_lb, ...
        ub=options.dc_ub, ...
        ce_coeffs=options.dc_ce_coeffs, ...
        n_dc=options.dc_n_dc, ...
        nf=options.dc_nf ...
    );
    
    % Solve WCT input mixer
    [~, Twct_in] = mixer_model_fun(qwct_p, qwct_s, Tcc_in, Tdc_out);
    Twct_out = mixer_inverse_model(qdc-qwct_s, qc_m3h, Tdc_out, Tcc_out);
    % print(Twct_out)

    % WCT
    [wwct, valid_] = wct_inverse_model_fun(...
        Tamb_C, ...
        HR_pp, ...
        Twct_in, ...
        qwct, ...
        Twct_out, ...
        resolution_mode=options.resolution_mode, ...
        model_type=options.model_type, ...
        model_data_path=options.wct_model_data_path, ...
        inverse_model_data_path=options.inverse_wct_model_data_path, ...
        lb=options.wct_lb, ...
        ub=options.wct_ub, ...
        silence_warnings=silence_warnings, ...
        ce_coeffs=options.wct_ce_coeffs, ...
        n_wct=options.wct_n_wct, ...
        model=options.wct_model ...
    );
    if ~valid_ % No feasible fan speed found for the given inputs
        valid = false;
        if ~silence_warnings
            fprintf('DEBUG: WCT validation failed - No feasible fan speed found for inputs: Tamb_C=%.2f, HR_pp=%.2f, Twct_in=%.2f, qwct=%.2f, Twct_out=%.2f\n', ...
                    Tamb_C, HR_pp, Twct_in, qwct, Twct_out);
        end
    end

    % With wwct, evaluate model
    [Ce_kWe, Cw_lh, detailed] = combined_cooler_model(Tamb_C, HR_pp, mv_kgh, qc_m3h, Rp, Rs, wdc, wwct, Tv_C, options);

    % Validation
    diff_rel = abs(detailed.Qcc - detailed.Qc_released) / max(abs(detailed.Qcc), abs(detailed.Qc_released));

    if diff_rel > options.Qcc_Qc_relative_tol
        valid = false;
        if ~silence_warnings
            fprintf(['DEBUG: Heat balance validation failed - ' ...
                     'Relative difference > %.0f%%: |%.2f - %.2f| / max(...) = %.2f%%\n'], ...
                     options.Qcc_Qc_relative_tol*100, detailed.Qcc, detailed.Qc_released, options.Qcc_Qc_relative_tol*100);
        end
    end

    if detailed.Qdc < 10 && detailed.qdc > 0.5 % Water circulation on inactive component
        valid = false;
        if ~silence_warnings
            fprintf('DEBUG: DC inactive component validation failed - Water circulation on inactive DC: Qdc=%.2f < 10 && qdc=%.2f > 0\n', ...
                    detailed.Qdc, detailed.qdc);
        end
    end
    if detailed.Qwct < 10 && detailed.qwct > 0.5 % Water circulation on inactive component
        valid = false;
        if ~silence_warnings
            fprintf('DEBUG: WCT inactive component validation failed - Water circulation on inactive WCT: Qwct=%.2f < 10 && qwct=%.2f > 0\n', ...
                    detailed.Qwct, detailed.qwct);
        end
    end

    function apply_options()
        for field_name = fieldnames(options)'
            field_name = string(field_name);
            % fprintf('%s\n', field_name)
            if isfield(options_struct, field_name)
                % fprintf('Using option from struct: %s: %s\n', field_name, options_struct.(field_name))
                options.(field_name) = options_struct.(field_name);
            end
        end
    end
end


