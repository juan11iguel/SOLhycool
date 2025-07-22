function [Ce_kWe, Cw_lh, detailed, valid] = evaluate_operation(Tamb_C, HR_pp, mv_kgh, qc_m3h, Rp, Rs, wdc, Tv_C, options)
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
        Rp (1,1) double {mustBeLessThanOrEqual(Rp, 1)}
        Rs (1,1) double {mustBeLessThanOrEqual(Rs, 1)}
        wdc (1,1) double {mustBeNonnegative, mustBeLessThanOrEqual(wdc, 100)}
        Tv_C (1,1) double {mustBeGreaterThanOrEqual(Tv_C, 20), mustBeLessThanOrEqual(Tv_C, 60)} = []

        % Using keyword arguments does not work when exporting the model to
        % python
        options = struct('model_type', 'data', 'lb', nan, 'ub', nan, 'x0', nan, 'silence_warnings', true, 'parameters', default_parameters()); % Default values
        % options.model_type (1,:) char {mustBeMember(options.model_type, {'physical', 'data'})}
        % options.parameters struct = default_parameters() % Default optional input
        % options.x0 = nan
        % options.lb = nan
        % options.ub = nan
    end

    arguments (Output)
        Ce_kWe (1,1) double
        Cw_lh (1,1) double
        detailed (1,1) struct
        valid (1,1) logical
    end

    % Unpack options
    parameters = options.parameters;
    model_type = options.model_type;
    silence_warnings = options.silence_warnings;

    % Add dependencies path
    addpath(genpath('utils'));
    addpath(genpath('component_models'));

    % Validate input parameters
    validate_struct(default_parameters(), parameters);
    
    % Assign function handles
    condenser_model_fun = @condenser_model;
    mixer_model_fun     = @mixer_model;

    switch model_type
        case "data"
            dc_model_fun                = @dc_model_data;
            wct_inverse_model_fun       = @wct_inverse_model_data;
        case "physical"
            dc_model_fun                = @dc_model_physical;
            wct_inverse_model_fun       = @wct_inverse_model_physical;
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
    [Tc_in, Tc_out] = condenser_model_fun(mv_kgs, Tv_C, mc_kgs, option=parameters.condenser_option, A=parameters.condenser_A);
    Tcc_in = Tc_out;
    Tcc_out = Tc_in;
    % Validation
    if Tc_out >= Tv_C - parameters.condenser_deltaTv_cout_min
        valid = false;
    end

    % DC
    Tdc_in = Tcc_in;
    Tdc_out = dc_model_fun( ...
        Tamb_C, ...
        Tdc_in, ...
        qdc, ...
        wdc, ...
        model_data_path=parameters.dc_model_data_path, ...
        silence_warnings=silence_warnings, ...
        lb=parameters.dc_lb, ...
        ub=parameters.dc_ub, ...
        ce_coeffs=parameters.dc_ce_coeffs ...
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
        model_data_path=parameters.wct_model_data_path, ...
        lb=parameters.wct_lb, ...
        ub=parameters.wct_ub, ...
        silence_warnings=silence_warnings, ...
        ce_coeffs=parameters.wct_ce_coeffs ...
    );
    if ~valid_ % No feasible fan speed found for the given inputs
        valid = false;
    end

    % With wwct, evaluate model
    [Ce_kWe, Cw_lh, detailed] = combined_cooler_model(Tamb_C, HR_pp, mv_kgh, qc_m3h, Rp, Rs, wdc, wwct, Tv_C, options);

    % Validation
    if abs( detailed.Qcc - detailed.Qc_released ) > 10
        valid = false;
    end

    if detailed.Qdc < 10 && detailed.qdc > 0 % Water circulation on inactive component
        valid = false;
    end
    if detailed.Qwct < 10 && detailed.qwct > 0 % Water circulation on inactive component
        valid = false;
    end
end


