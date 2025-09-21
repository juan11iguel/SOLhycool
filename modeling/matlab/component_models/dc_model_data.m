function [Tout, Ce] = dc_model_data(Tamb, Tin, q, w_fan, options_struct, options)
    % DC_MODEL  Predicts outlet temperature and electrical consumption for the WASCOP dry cooler.
    %
    % Inputs:
    %   Tamb    - Ambient temperature (ºC)
    %   Tin     - Inlet temperature (ºC)
    %   q       - Volumetric flow rate (m³/h)
    %   w_fan   - Fan load (%)
    %   n_dc    - Number of DCs in parallel
    %   options - Struct with optional fields:
    %       .raise_error_on_invalid_inputs (logical)
    %       .model_data_path (string)
    %       .lb, .ub (double vectors)
    %       .silence_warnings (logical)
    %       .ce_coeffs (double vector)
    %
    % Outputs:
    %   Tout    - Outlet temperature (ºC)
    %   Ce      - Electrical consumption (kWe)
    %
    % Notes:
    %   Uses a data-driven model that can be called with the predict function
    %   loaded from dc_model_data.mat.

    arguments (Input)
        Tamb (1,1) double
        Tin (1,1) double
        q (1,1) double
        w_fan (1,1) double
        % Using keyword arguments does not work when exporting the model to
        % python. Offer an alternative
        options_struct = []
        options.n_dc (1,1) double {mustBeInteger,mustBePositive} = 1
        options.nf (1,1) double {mustBePositive} = 1; % N fans (1 is equivalent to 2 fans of the pilot plant), for 1 fan write 0.5
        options.raise_error_on_invalid_inputs (1,1) logical = false
        options.model_data_path string = fullfile(fileparts(mfilename('fullpath')), "dc_model_data.mat")
        options.silence_warnings logical = false
        options.lb (1,4) double = 0.99*[3.0      25.0,    6.0,  11];
        options.ub (1,4) double = 1.01*[50.0     55.0,    24.0, 99.1800];
        options.ce_coeffs (1,:) double = [-0.0002431, 0.04761, -2.2, 48.63, -295.6];
    end

    arguments (Output)
        Tout (1,1) double % ºC
        Ce (1,1) double % kW
    end

    % Limits of flow rate considering the number of DCs in parallel
    options.ub(3)=options.ub(3)*options.n_dc;
    options.lb(3)=options.lb(3)*options.n_dc;

    persistent model

    if isempty(model)
        load(options.model_data_path, "model");
    end
    
    % fprintf("wct model path: %s\n", options.model_data_path)

    max_values = options.ub;
    min_values = options.lb;
    vars = ["Tamb", "Tin", "q", "w_fan"];

    valid_inputs = true;
    for idx=1:length(vars)
        var = vars(idx); value = eval(var);
        if value > ceil(max_values(idx)) || value < floor(min_values(idx))
            if options.raise_error_on_invalid_inputs
                raise_error(var, value, min_values(idx), max_values(idx))
            else
                if ~options.silence_warnings
                    warning("%s outside limits (%.2f <! %.2f <! %.2f)", var, min_values(idx), value, max_values(idx))
                end
                valid_inputs = false;
            end
        end
    end

    if valid_inputs
        [Tout, ~, ~] = predict(model, [Tamb, Tin, w_fan, q/options.n_dc]);
        Ce = options.n_dc * options.nf * power_consumption(w_fan) * 1e-3; % kW
    else
        Tout = Tin;
        Ce = 0;
    end

    function P_fan_W = power_consumption(w_fan)
        P_fan_W = max(0, polyval(options.ce_coeffs, w_fan)); % W
    end

    function raise_error(variable, value, lower_limit, upper_limit)
        msg = sprintf("Input %s=%.2f is outside limits (%.2f < %s < %.2f)", string(variable), value, lower_limit, string(variable), upper_limit);
        throw(MException('model:invalid_input', msg))
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