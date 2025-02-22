function [Ce_kWe, Cw_lh, detailed] = combined_cooler_model(Tamb_C, HR_pp, mv_kgh, qc_m3h, Rp, Rs, wdc, wwct, Tv_C, options)
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
        Tv_C double {mustBeGreaterThanOrEqual(Tv_C, 35), mustBeLessThanOrEqual(Tv_C, 50)} = []

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
    end

    % Unpack options
    parameters = options.parameters;
    model_type = options.model_type;
    silence_warnings = options.silence_warnings;

    % Add utilities path
    addpath(genpath('utils\'));

    % Validate parameters
    validate_struct(default_parameters(), parameters);
    % if isnan(Rs)
    %     Rs=0;
    % end

    % Define model functions to use
    dc_model_fun = @dc_model;
    wct_model_fun = @wct_model;
    condenser_model_fun = @condenser_model;
    mixer_model_fun = @mixer_model;
    % dc_model_fun = function_handle(char(fullfile('.', 'component_models', model_type, 'dc_model.m')));
    % wct_model_fun = function_handle(char(fullfile('.', 'component_models', model_type, 'wct_model.m')));
    % condenser_model_fun = function_handle(char(fullfile('.', 'component_models', 'condenser_model.m')));
    % mixer_model_fun = function_handle(char(fullfile('.', 'component_models', 'mixer_model.m')));


    % Calculations
    % Unit conversion
    mc_kgs = qc_m3h / 3.6;
    mv_kgs = mv_kgh / 3600;
    % Get flows from ratios
    % [qdc, qwct] = ratios_to_flows(qc_m3h, Rp, Rs);
    qdc = qc_m3h*(1-Rp);
    qwct_p = qc_m3h*Rp;
    qwct_s = qdc*Rs;
    qwct = qwct_p + qwct_s;
    mwct = qwct / 3.6;
    mdc = qdc / 3.6;
    % Other
    Twct_min = parameters.wct_lb(3);

    % Here is where we should call fsolve to solve the model

    if isempty(Tv_C)
        x0 = get_initial_values();
        [lb, ub] = get_bounds();
        Aeq = [];
        beq = [];
        opt = optimoptions('fmincon', 'Algorithm', 'sqp', 'OptimalityTolerance', 1e-10, 'StepTolerance', 1e-11, 'Display','none'); 
        Tv = fmincon(@(Tv) inner_model(Tv), x0, [], [], Aeq, beq, lb, ub, [], opt);
    else
        Tv = Tv_C;
    end

    % Get outputs 
    qcc = qc_m3h;
    % Condenser
    [Tc_in, Tc_out] = condenser_model_fun(mv_kgs, Tv, mc_kgs, option=parameters.condenser_option, A=parameters.condenser_A);
    Tcc_in = Tc_out;
    % Qc = mc_kgs * (Tc_in - Tc_out) * XSteam('Cp_pT',2,(Tc_in+Tc_out)/2);
    % DC
    Tdc_in = Tcc_in;
    [Tdc_out, Ce_dc] = dc_model_fun(Tamb_C, Tdc_in, qdc, wdc, model_data_path=parameters.dc_model_data_path, silence_warnings=silence_warnings);
    % Solve WCT input mixer
    [~, Twct_in] = mixer_model_fun(qwct_p, qwct_s, Tcc_in, Tdc_out);
    % WCT
    [Twct_out, Ce_wct, Cw_wct] = wct_model_fun(Tamb_C, HR_pp, Twct_in, qwct, wwct, ...
        model_data_path=parameters.wct_model_data_path, lb=parameters.wct_lb, ub=parameters.wct_ub, silence_warnings=silence_warnings);
    % Solve CC output mixer
    [~, Tcc_out] = mixer_model_fun(qdc, qwct, Tdc_out, Twct_out);
    % Validation
    if abs(Tcc_out - Tc_in) > 1 && ~silence_warnings
        msg = sprintf("cooling system, no valid solution found, Tc_in: %.3f - %3.f", Tc_in, Tcc_out);
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
    % Tv_C = Tv;
    Ce_kWe = Ce;
    Cw_lh = Cw;

    % Condenser heat
    Q = condenser_heats_model(mv_kgs, Tv, mc_kgs, Tc_in, Tc_out, option=parameters.condenser_option, A=parameters.condenser_A);
    Qc_released = Q(1);
    Qc_absorbed = Q(2);
    Qc_transfered = Q(3);

    % Components cooling power
    Qdc  = mdc*XSteam('Cp_pT',2,(Tdc_in+Tdc_out)/2)*(Tdc_in-Tdc_out);
    Qwct = mwct*XSteam('Cp_pT',2,(Twct_in+Twct_out)/2)*(Twct_in-Twct_out);
    Qcc = mc_kgs*XSteam('Cp_pT',2,(Tcc_in+Tcc_out)/2)*(Tcc_in-Tcc_out);

    detailed = build_detailed_struct();

    function residual = inner_model(Tv)
        % Should do the bare minimum and return a residual

        % Condenser
        [Tc_in, Tc_out] = condenser_model_fun(mv_kgs, Tv, mc_kgs, option=parameters.condenser_option, A=parameters.condenser_A, Tmin=Twct_min);
        % DC
        Tdc_out = dc_model_fun(Tamb_C, Tc_out, qdc, wdc, model_data_path=parameters.dc_model_data_path, silence_warnings=silence_warnings);
        % WCT
        [~, Twct_in] = mixer_model_fun(qwct_p, qwct_s, Tc_out, Tdc_out);
        Twct_out = wct_model_fun(Tamb_C, HR_pp, Twct_in, qwct, wwct, model_data_path=parameters.wct_model_data_path, ...
            lb=parameters.wct_lb, ub=parameters.wct_ub, silence_warnings=silence_warnings);
        [~, Tcc_out] = mixer_model_fun(qdc, qwct, Tdc_out, Twct_out);
        
        % fprintf("cc model residual Tcc_out - Tc_in: %.2f for Tv=%.2f\n", abs(Tcc_out - Tc_in), Tv)
        residual = (Tcc_out - Tc_in).^2;
    end

    function x0 = get_initial_values()
        % TODO: Do not hardcode these values, compute them from input data and
        % parameters
        if isnan(options.x0)
            x0 = 43;
        else
            x0 = options.x0;
        end
    end

    function [lb, ub] = get_bounds()
        % TODO: Should use data from parameters
        if isnan(options.lb)
            lb = 40; % parameters.wct_lb(3);
        else
            lb = options.lb;
        end
        if isnan(options.lb)
            ub = 50;
        else
            ub = options.ub;
        end
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
        d.Qc_released = Qc_released;
        d.Qc_absorbed = Qc_absorbed;
        d.Qc_transfered = Qc_transfered;
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
        d.Qcc = Qcc;
        % Dry cooler
        d.qdc = qdc;
        d.Tdc_in = Tdc_in;
        d.Tdc_out = Tdc_out;
        d.Ce_dc = Ce_dc;
        d.Qdc = Qdc;
        % Wet cooling tower
        d.qwct = qwct;
        d.Twct_in = Twct_in;
        d.Twct_out = Twct_out;
        d.Ce_wct = Ce_wct;
        d.Cw_wct = Cw_wct;
        d.Qwct = Qwct;
    end

end


