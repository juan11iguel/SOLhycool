function [wwct, valid] = wct_inverse_model(Tamb, HR, Tin, q, Tout, options_struct, options)
    % WCT_INVERSE_MODEL  Solves for WCT fan speed to achieve a target outlet temperature.
    %
    % Inputs:
    %   Tamb    - Ambient temperature (ºC)
    %   HR      - Relative humidity (%)
    %   Tin     - Inlet temperature (ºC)
    %   q       - Volumetric flow rate (m³/h)
    %   Tout    - Target outlet temperature (ºC)
    %   options - Struct with optional fields:
    %       .lb, .ub (double, bounds for fan speed)
    %       .silence_warnings (logical)
    %       .tolerance (double)
    %       .model_data_path (string)
    %       .ce_coeffs (double vector)
    %       .lb_wct, .ub_wct (double vectors)
    %       .raise_error_on_invalid_inputs (logical)
    %
    % Outputs:
    %   wwct    - Fan speed (%)
    %   valid   - Logical indicating if a valid solution was found

    arguments (Input)
        Tamb (1,1) double
        HR (1,1) double
        Tin (1,1) double
        q (1,1) double
        Tout (1,1) double

        % Using keyword arguments does not work when exporting the model to
        % python. Offer an alternative
        options_struct = []
        options.resolution_mode (1,:) char {mustBeMember(options.resolution_mode, {'inverse', 'direct'})} = 'direct'
        options.model_type (1,:) char {mustBeMember(options.model_type, {'physical', 'data', 'data_direct'})} = 'data'
        options.n_wct (1,1) double {mustBeInteger,mustBePositive} = 1
        options.ce_coeffs (1,:) double = [0.4118, -11.54, 189.4]; % Default quadratic coefficients
        options.model_data_path string = fullfile(fileparts(mfilename('fullpath')), "wct_model_data.mat")
        options.inverse_model_data_path string = fullfile(fileparts(mfilename('fullpath')), "inverse_wct_model_data.mat")
        options.lb (1,5) double = [0.1    0.1     5.0    5.0       0.];
        options.ub (1,5) double = [50.0   99.99   55.0   24.8400   95.];
        options.tolerance (1,1) double = 0.5
        options.raise_error_on_invalid_inputs (1,1) logical = false
        options.silence_warnings logical = false
        options.model = []
    end

    arguments (Output)
        wwct (1,1) double
        valid (1,1) logical
    end

    % Terrible
    % Apply optional arguments from the alternative struct if provided
    if ~isempty(options_struct)
        apply_options();
    end

    % Limits of flow rate considering the number of WCTs in parallel
    options.ub(4)=options.ub(4)*options.n_wct;
    options.lb(4)=options.lb(4)*options.n_wct;

    if q < options.lb(4)
        wwct = 0;
        valid = true;
        return 
    end

    lb_x = options.lb(end);
    ub_x = options.ub(end);

    switch options.model_type
        case "data"
            wct_model_fun       = @wct_model_data;
        case "physical"
            wct_model_fun       = @wct_model_physical;
        otherwise
            error("wct_inverse:invalid_option", ...
                  "Invalid model_type '%s'. Options are: 'data', 'physical'", model_type);
    end

    if strcmp(options.resolution_mode, "direct")
        % Obtainfan speed directly

        lb = options.lb;
        ub = options.ub;
        lb(end) = options.lb(3);
        ub(end) = options.ub(3);

        wwct = inverse_wct_model_data(Tamb, HR, Tin, q, Tout, ...
            model_data_path=options.inverse_model_data_path, ...
            lb=lb, ...
            ub=ub, ...
            silence_warnings=options.silence_warnings, ...
            raise_error_on_invalid_inputs=options.raise_error_on_invalid_inputs, ...
            n_wct=options.n_wct ...
        );
        wwct = max(lb_x, min(ub_x, wwct));
        valid = (inner_model(wwct) <= options.tolerance);
    else
        % Inverse the direct model
        N=400;
        X = linspace(lb_x, ub_x, N)';
        fvals = inner_model(X);
        [best_val, idx] = min(fvals);
        wwct = X(idx,:);
        valid = (best_val <= options.tolerance);

        % % Optimization options
        % opt = optimoptions('fmincon', 'Algorithm', 'sqp', 'OptimalityTolerance', 1e-10, 'StepTolerance', 1e-11, 'Display', 'none'); 
        % 
        % % Run optimization
        % % (options.lb+options.ub)/2
        % [wwct, fval, exitflag] = fmincon(@(wwct) inner_model(wwct), (lb_x+ub_x)/2, [], [], [], [], lb_x, ub_x, [], opt);
        % valid = (fval <= options.tolerance) && (exitflag > 0);
    end

    if ~valid && ~options.silence_warnings
        fprintf("No feasible fan speed found: fval=%.3f > tol=%.3f or exit flag=%d > 0\n", fval, options.tolerance, exitflag)
    end

    function residual = inner_model(wwct)
        % Compute the output temperature using the WCT model
        Twct_out = wct_model_fun(Tamb, HR, Tin, q, wwct, ...
            model_data_path=options.model_data_path, ...
            lb=options.lb, ...
            ub=options.ub, ...
            silence_warnings=options.silence_warnings, ...
            ce_coeffs=options.ce_coeffs, ...
            raise_error_on_invalid_inputs=options.raise_error_on_invalid_inputs, ...
            n_wct=options.n_wct, ...
            model=options.model ...
        );
        
        % Compute squared residual
        residual = abs(Tout - Twct_out);
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
