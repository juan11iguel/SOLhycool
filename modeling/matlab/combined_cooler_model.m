 function [Ce_kWe, Cw_lh, detailed] = combined_cooler_model(Tamb_C, HR_pp, mv_kgh, qc_m3h, Rp, Rs, wdc, wwct, Tv_C, options_struct, options)
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
        Rp (1,1) double {mustBeGreaterThanOrEqual(Rp, 0.0), mustBeLessThanOrEqual(Rp, 1.0)}
        Rs (1,1) double {mustBeGreaterThanOrEqual(Rs, 0.0), mustBeLessThanOrEqual(Rs, 1.0)}
        wdc (1,1) double {mustBeGreaterThanOrEqual(wdc, 0.0), mustBeLessThanOrEqual(wdc, 100)}
        wwct (1,1) double {mustBeGreaterThanOrEqual(wwct, 0.0), mustBeLessThanOrEqual(wwct, 100)}
        Tv_C double {mustBeGreaterThanOrEqual(Tv_C, 20), mustBeLessThanOrEqual(Tv_C, 60)} = []
        
        % Using keyword arguments does not work when exporting the model to
        % python. Offer an alternative
        options_struct = []
        options.model_type (1,:) char {mustBeMember(options.model_type, {'physical', 'data'})} = 'data'
        % DC               "Tamb",    "Tin",   "q", "w_fan"
        options.dc_lb (1,4) double = 0.99*[3.0      25.0,    6.0,  11];
        options.dc_ub (1,4) double = 1.01*[50.0     55.0,    24.0, 99.1800];
        % wdc (%) -> Ce_dc (W)
        options.dc_ce_coeffs (1,:) double = [-0.0002431, 0.04761, -2.2, 48.63, -295.6];
        options.dc_n_dc  (1,1) double {mustBeInteger,mustBePositive} = 1;
        
        % WCT                              "Tamb",     "HR",    "Tin",      "q",     "w_fan"
        options.wct_lb (1,5) double = 0.99*[3.0       1.0      25.0        6.0       21.0];
        options.wct_ub (1,5) double = 1.01*[50.0      99.0     55.0        24.0      93.4161];
        % wwct (%) -> Ce_wct (W)
        options.wct_ce_coeffs (1,:) double = [0.4118, -11.54, 189.4];
        options.wct_n_wct (1,1) double {mustBeInteger,mustBePositive} = 1;

        % Condenser
        options.condenser_option (1,1) int8 {mustBeInRange(options.condenser_option, 1, 9)} = 6;
        options.condenser_A (1,1) double {mustBePositive} = 19.30; % 19.967 -> https://collab.psa.es/f/174826 24/U;
        options.condenser_deltaTv_cout_min (1,1) double {mustBePositive} = 1;
        options.condenser_n_tb (1,1) double {mustBeInteger,mustBePositive} = 24;
    
        % Recirculation pump
        % w_c (%) -> Ce_c (W) 
        options.recirculation_coeffs (1,:) double = [0.1461, 5.763, -38.32, 227.8];
        
        % Paths
        options.dc_model_data_path = char(fullfile(fileparts(mfilename('fullpath')),  "/component_models", "model_data_dc_fp_gaussian.mat"));
        options.wct_model_data_path = char(fullfile(fileparts(mfilename('fullpath')), "/component_models", "model_data_wct_fp_gaussian.mat"));

        % Miscellaneous options
        options.raise_error_on_invalid_inputs (1,1) logical = false
        options.silence_warnings (1,1) logical = false
    end

    arguments (Output)
        Ce_kWe (1,1) double
        Cw_lh (1,1) double
        detailed (1,1) struct
    end

    % Terrible
    % Apply optional arguments from the alternative options_struct if provided
    if ~isempty(options_struct)
        apply_options();
    end

    % Unpack options
    model_type = options.model_type;
    silence_warnings = options.silence_warnings;

    % Add dependencies path
    addpath(genpath('utils'));
    addpath(genpath('component_models'));

    % Validate input parameters
    % validate_struct(default_parameters(), parameters);
    
    % Assign function handles
    condenser_model_fun = @condenser_model;
    mixer_model_fun     = @mixer_model;

    switch model_type
        case "data"
            dc_model_fun        = @dc_model_data;
            wct_model_fun       = @wct_model_data;
        case "physical"
            dc_model_fun        = @dc_model_physical;
            wct_model_fun       = @wct_model_physical;
        otherwise
            error("combined_cooler_model:invalid_option", ...
                  "Invalid model_type '%s'. Options are: 'data', 'physical'", model_type);
    end

    if silence_warnings
        warning('off','all') % disable all warnings
    end

    % Calculations
    % Unit conversion
    mc_kgs = qc_m3h / 3.6;
    mv_kgs = mv_kgh / 3600;
    % Get flows from ratios
    [qdc, qwct, qwct_p, qwct_s] = ratios_to_flows(qc_m3h, Rp, Rs);
    mwct = qwct / 3.6; % m3/h -> kg/s
    mdc = qdc / 3.6; % m3/h -> kg/s
    % Other
    Twct_min = options.wct_lb(3);

    % Here is where we should call fsolve to solve the model

    % if isempty(Tv_C)
    %     x0 = get_initial_values();
    %     [lb, ub] = get_bounds();
    %     Aeq = [];
    %     beq = [];
    %     opt = optimoptions('fmincon', 'Algorithm', 'sqp', 'OptimalityTolerance', 1e-10, 'StepTolerance', 1e-11, 'Display','none'); 
    %     Tv = fmincon(@(Tv) inner_model(Tv), x0, [], [], Aeq, beq, lb, ub, [], opt);
    % else
        Tv = Tv_C;
    % end

    % Get outputs 
    qcc = qc_m3h;

    % Condenser
    [Tc_in, Tc_out] = condenser_model_fun( ...
        mv_kgs, ...
        Tv, ...
        mc_kgs, ...
        option=options.condenser_option, ...
        A=options.condenser_A, ...
        n_tb=options.condenser_n_tb ...
    );
    Tcc_in = Tc_out;
    % Qc = mc_kgs * (Tc_in - Tc_out) * XSteam('Cp_pT',2,(Tc_in+Tc_out)/2);

    % DC
    Tdc_in = Tcc_in;
    [Tdc_out, Ce_dc] = dc_model_fun( ...
        Tamb_C, ...
        Tdc_in, ...
        qdc, ...
        wdc, ...
        model_data_path=options.dc_model_data_path, ...
        silence_warnings=silence_warnings, ...
        lb=options.dc_lb, ...
        ub=options.dc_ub, ...
        ce_coeffs=options.dc_ce_coeffs, ...
        n_dc=options.dc_n_dc  ...
    );

    % Solve WCT input mixer
    [~, Twct_in] = mixer_model_fun(qwct_p, qwct_s, Tcc_in, Tdc_out);

    % WCT
    [Twct_out, Ce_wct, Cw_wct] = wct_model_fun(...
        Tamb_C, ...
        HR_pp, ...
        Twct_in, ...
        qwct, ...
        wwct, ...
        model_data_path=options.wct_model_data_path, ...
        lb=options.wct_lb, ...
        ub=options.wct_ub, ...
        silence_warnings=silence_warnings, ...
        ce_coeffs=options.wct_ce_coeffs, ...
        n_wct=options.wct_n_wct ...
    );

    % Solve CC output mixer
    [~, Tcc_out] = mixer_model_fun(qdc, qwct, Tdc_out, Twct_out);

    % Validation
    if abs(Tcc_out - Tc_in) > 1 && ~silence_warnings
        warning("combined_cooler_model:solution_not_found", "cooling system, no valid solution found, Tc_in: %.3f - %3.f", Tc_in, Tcc_out)
        % throw(MException("combined_cooler_model:invalid_solution", msg))
    end
    
    % Additional outputs
    Ce_c = recirculation_pump_consumption(qc_m3h, options.recirculation_coeffs);

    % Validate consumptions
    % UPDATE: Not needed anymore, as the functions already validate for non-negative values
    Ce_c = max(0, Ce_c);
    Ce_dc = max(0, Ce_dc); 
    Ce_wct = max(0, Ce_wct);
    Cw_wct = max(0, Cw_wct);

    % Validate fan frequencies
    if Ce_dc < 1e-6
        wdc = 0; % DC not operating
    end
    if Ce_wct < 1e-6
        wwct = 0; % WCT not operating
    end

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
    [Q, U] = condenser_heats_model(mv_kgs, Tv, mc_kgs, Tc_in, Tc_out, option=options.condenser_option, A=options.condenser_A, n_tb=options.condenser_n_tb);
    Qc_released = Q(1);
    Qc_absorbed = Q(2);
    Qc_transfered = Q(3);

    % Components cooling power
    Qdc  = mdc*XSteam('Cp_pT',2,(Tdc_in+Tdc_out)/2)*(Tdc_in-Tdc_out);
    Qwct = mwct*XSteam('Cp_pT',2,(Twct_in+Twct_out)/2)*(Twct_in-Twct_out);
    Qcc = Qdc+Qwct;
    % Qcc = mc_kgs*XSteam('Cp_pT',2,(Tcc_in+Tcc_out)/2)*(Tcc_in-Tcc_out);

    detailed = build_detailed_struct();

    function residual = inner_model(Tv)
        % Should do the bare minimum and return a residual
        warning("This function has not been updated for a while, it should not be used without checking")

        % Condenser
        [Tc_in, Tc_out] = condenser_model_fun(mv_kgs, Tv, mc_kgs, option=options.condenser_option, A=options.condenser_A, n_tb=options.condenser_n_tb, Tmin=Twct_min);
        % DC
        Tdc_out = dc_model_fun(Tamb_C, Tc_out, qdc, wdc, model_data_path=options.dc_model_data_path, silence_warnings=silence_warnings);
        % WCT
        [~, Twct_in] = mixer_model_fun(qwct_p, qwct_s, Tc_out, Tdc_out);
        Twct_out = wct_model_fun(Tamb_C, HR_pp, Twct_in, qwct, wwct, model_data_path=options.wct_model_data_path, ...
            lb=options.wct_lb, ub=options.wct_ub, silence_warnings=silence_warnings);
        [~, Tcc_out] = mixer_model_fun(qdc, qwct, Tdc_out, Twct_out);
        
        % fprintf("cc model residual Tcc_out - Tc_in: %.2f for Tv=%.2f\n", abs(Tcc_out - Tc_in), Tv)
        residual = (Tcc_out - Tc_in).^2;
    end

    function x0 = get_initial_values()
        % TODO: Do not hardcode these values, compute them from input data and
        % options
        if isnan(options.x0)
            x0 = 43;
        else
            x0 = options.x0;
        end
    end

    function [lb, ub] = get_bounds()
        % TODO: Should use data from options
        if isnan(options.lb)
            lb = 40; % options.wct_lb(3);
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
        d.Uc = U;
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


