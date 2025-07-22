function [wwct, valid] = wct_inverse_model_data(Tamb, HR, Tin, q, Tout, options)
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
        options.lb_x (1,1) double = 0;
        options.ub_x (1,1) double = 93.4161;
        options.silence_warnings logical = false
        options.tolerance (1,1) double = 1e-3
        options.model_data_path string = fullfile(fileparts(mfilename('fullpath')), "wct_model_data.mat")
        options.ce_coeffs (1,:) double = [0.4118, -11.54, 189.4];
        options.lb (1,5) double = 0.9*[9.0600   10.3300   31.1700    5.7049         0];
        options.ub (1,5) double = 1.1*[38.7500   89.2500   40.9400   24.8400   93.4161];
        options.raise_error_on_invalid_inputs (1,1) logical = false
    end

    arguments (Output)
        wwct (1,1) double
        valid (1,1) logical
    end

    if q < 1e-3
        wwct = 0;
        valid = true;
        return 
    end

    % Optimization options
    opt = optimoptions('fmincon', 'Algorithm', 'sqp', 'OptimalityTolerance', 1e-10, 'StepTolerance', 1e-11, 'Display', 'none'); 
    
    % Define equality constraints (empty for now)
    Aeq = [];
    beq = [];
    
    % Run optimization
    % (options.lb+options.ub)/2
    [wwct, fval, exitflag] = fmincon(@(wwct) inner_model(wwct), options.lb_x, [], [], [], [], options.lb_x, options.ub_x, [], opt);
    valid = (fval <= options.tolerance) && (exitflag > 0);

    function residual = inner_model(wwct)
        % Compute the output temperature using the WCT model
        Twct_out = wct_model_data(Tamb, HR, Tin, q, wwct, ...
            model_data_path=options.model_data_path, ...
            lb=options.lb, ...
            ub=options.ub, ...
            silence_warnings=options.silence_warnings, ...
            ce_coeffs=options.ce_coeffs, ...
            raise_error_on_invalid_inputs=options.raise_error_on_invalid_inputs ...
        );
        
        % Compute squared residual
        residual = (Tout - Twct_out).^2;
    end

end
