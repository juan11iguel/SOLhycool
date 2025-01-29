function [Tv_C, Ce_kWe, Cw_lh, detailed] = combined_cooler_model_v0(Tamb_C, HR_pp, mv_kgh, qc_m3h, Rp, Rs, wdc, wwct, options)
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
    
    arguments (Input)
        Tamb_C (1,1) double {mustBeNonnegative, mustBeLessThanOrEqual(Tamb_C, 50)}
        HR_pp (1,1) double {mustBeNonnegative, mustBeLessThanOrEqual(HR_pp, 100)}
        mv_kgh (1,1) double {mustBePositive}
        qc_m3h (1,1) double {mustBePositive}
        Rp (1,1) double {mustBeLessThanOrEqual(Rp, 1)}
        Rs (1,1) double {mustBeLessThanOrEqual(Rs, 1)}
        wdc (1,1) double {mustBeNonnegative, mustBeLessThanOrEqual(wdc, 100)}
        wwct (1,1) double {mustBeNonnegative, mustBeLessThanOrEqual(wwct, 100)}
        options.model_type (1,:) char {mustBeMember(options.model_type, {'physical', 'data'})}
        options.parameters struct = default_parameters() % Default optional input
        options.x0 = nan
        options.lb = nan
        options.ub = nan
    end

    arguments (Output)
        Tv_C (1,1) double
        Ce_kWe (1,1) double
        Cw_lh (1,1) double
        detailed (1,1) struct
    end

    % Unpack options
    parameters = options.parameters;
    model_type = options.model_type;

    % Add utilities path
    addpath(genpath('utils\'));

    % Validate parameters
    validate_struct(default_parameters(), parameters);
    % if isnan(Rs)
    %     Rs=0;
    % end

    % Define model functions to use
    dc_model_fun = function_handle(char(fullfile('.', 'component_models', model_type, 'dc_model.m')));
    wct_model_fun = function_handle(char(fullfile('.', 'component_models', model_type, 'wct_model.m')));
    condenser_model_fun = function_handle(char(fullfile('.', 'component_models', 'condenser_model_residuals.m')));
    mixer_model_fun = function_handle(char(fullfile('.', 'component_models', 'mixer_model.m')));


    % Calculations
    % Unit conversion
    mc_kgs = qc_m3h / 3.6;
    ms_kgs = mv_kgh / 3600;
    % Get flows from ratios
    % [qdc, qwct] = ratios_to_flows(qc_m3h, Rp, Rs);
    qdc = qc_m3h*(1-Rp);
    qwct_p = qc_m3h*Rp;
    qwct_s = qdc*Rs;
    qwct = qwct_p + qwct_s;
    % Other
    Twct_min = parameters.wct_lb(3);

    % Here is where we should call fsolve to solve the model
    x0 = get_initial_values();
    [lb, ub] = get_bounds();
    Aeq = [];
    beq = [];
    options = optimoptions('fmincon', 'Algorithm', 'sqp', 'OptimalityTolerance', 1e-10, 'StepTolerance', 1e-11, 'Display','none'); 
    x = fmincon(@(x) inner_model(x), x0, [], [], Aeq, beq, lb, ub, [], options);
    Qc = x(1);
    Tv = x(2);
    Tc_out = x(3);
    Tc_in = x(4);

    % Get outputs 
    qcc = qc_m3h;
    Tcc_in = Tc_out;
    % DC
    Tdc_in = Tcc_in;
    [Tdc_out, Ce_dc] = dc_model_fun(Tamb_C, Tdc_in, qdc, wdc, model_data_path=parameters.dc_model_data_path);
    % Solve WCT input mixer
    [~, Twct_in] = mixer_model_fun(qwct_p, qwct_s, Tcc_in, Tdc_out);
    % WCT
    [Twct_out, Ce_wct, Cw_wct] = wct_model_fun(Tamb_C, HR_pp, Twct_in, qwct, wwct, model_data_path=parameters.wct_model_data_path);
    % Solve CC output mixer
    [~, Tcc_out] = mixer_model_fun(qdc, qwct, Tdc_out, Twct_out);
    % Validation
    if abs(Tcc_out - Tc_in) > 1
        msg = sprintf("no valid solution found, Tc_in: %.3f - %3.f", Tc_in, Tcc_out);
        warning(msg)
        % throw(MException("combined_cooler_model:invalid_solution", msg))
    end
    % Additional outputs
    Ce_c = recirculation_pump_consumption(qc_m3h);
    Ce_cc = Ce_dc + Ce_wct;
    Ce = Ce_cc + Ce_c;
    Cw = Cw_wct;
    Cw_cc = Cw_wct;
    Tcond = Tv;
    
    % Define this function outputs with units for clarity
    Tv_C = Tv;
    Ce_kWe = Ce;
    Cw_lh = Cw;
    detailed = build_detailed_struct();

    function error = inner_model(x)
        % Should do the bare minimum and return an error
        Qc = x(1);
        Tv = x(2);
        Tc_out = x(3);
        Tc_in = x(4);

        % Condenser
        Q_ = condenser_model_fun(ms_kgs, Tv, mc_kgs, Tc_in, Tc_out, parameters.condenser_option, parameters.condenser_A);
        % DC
        Tdc_out = dc_model_fun(Tamb_C, Tc_out, qdc, wdc, model_data_path=parameters.dc_model_data_path);
        % WCT
        [~, Twct_in] = mixer_model_fun(qwct_p, qwct_s, Tc_out, Tdc_out);
        Twct_out = wct_model_fun(Tamb_C, HR_pp, Twct_in, qwct, wwct, model_data_path=parameters.wct_model_data_path);
        [~, Tc_in_] = mixer_model_fun(qdc, qwct, Tdc_out, Twct_out);
        
        % error = thermal power error + Tc_in error
        error_Q = sum((Q_ - Qc).^2);
        error_T = (Tc_in_ - Tc_in).^2 * 50;
        fprintf("Q: %.2f T: %.2f \n", error_Q, error_T)

        error = error_Q + error_T;
    end

    function x0 = get_initial_values()
        % TODO: Do not hardcode these values, compute them from input data and
        % parameters
        x0 = [150,44,42,30];
    end

    function [lb, ub] = get_bounds()
        % TODO: Should use data from parameters
        lb = [10,40,29.84,Tamb_C-10]; % los límites de Tv hay que ajustarlos mucho o ponerlo como restricción
        ub = [350,45,43,43];
    end

    function d = build_detailed_struct()
        % Build detailed results structure
        d = struct;
        
        % Inputs
        % Environment
        d.Tamb = Tamb_C;
        d.HR = HR_pp;
        % Cooling load
        d.mv = mv_kgh;
        % Combined cooler operation
        d.qc = qc_m3h;
        d.Rp = Rp;
        d.Rs = Rs;
        d.wdc = wdc;
        d.wwct = wwct;

        % Outputs
        % Main outputs
        d.Ce = Ce;
        d.Cw = Cw;
        d.Tv = Tv;
        % Condenser
        d.Qc = Qc;
        d.Tc_in = Tc_in;
        d.Tc_out = Tc_out;
        d.Tcond = Tcond;
        d.Ce_c = Ce_c;
        % Combined cooler
        d.qcc = qcc;
        d.Tcc_in = Tcc_in;
        d.Tcc_out = Tcc_out;
        d.Ce_cc = Ce_cc;
        d.Cw_cc = Cw_cc;
        d.qwct_p = qwct_p;
        d.qwct_s = qwct_s;
        % Dry cooler
        d.qdc = qdc;
        d.Tdc_in = Tdc_in;
        d.Tdc_out = Tdc_out;
        d.Ce_dc = Ce_dc;
        % Wet cooling tower
        d.qwct = qwct;
        d.Twct_in = Twct_in;
        d.Twct_out = Twct_out;
        d.Ce_wct = Ce_wct;
        d.Cw_wct = Cw_wct;
    end

end


