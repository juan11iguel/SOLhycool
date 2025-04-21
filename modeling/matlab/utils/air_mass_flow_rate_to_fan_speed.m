function [wwct, valid] = air_mass_flow_rate_to_fan_speed(ma_kgs, options)
    % Polynomial fit to convert from to air mass flow rate in kg/s fan speed (as a VFD percentage)
    arguments (Input)
        ma_kgs double
        options.lb (1,1) double = 21.0;
        options.ub (1,1) double = 93.4161;
        options.tolerance (1,1) double = 1e-1
    end

    arguments (Output)
        wwct double
        valid logical
    end

    Aeq = [];
    beq = [];
    % Optimization options
    opt = optimoptions('fmincon', 'Algorithm', 'sqp', 'OptimalityTolerance', 1e-10, 'StepTolerance', 1e-11, 'Display', 'none');     
    
    wwct = nan(1, length(ma_kgs));
    valid = nan(1, length(ma_kgs));
    for i=1:length(ma_kgs)
        ma_kgs_ = ma_kgs(i);
        [wwct(i), fval, exitflag] = fmincon(@(wwct) inner_fun(wwct), options.lb, [], [], Aeq, beq, options.lb, options.ub, [], opt);
        
        % Determine validity based on residual and exitflag
        valid(i) = (fval <= options.tolerance) && (exitflag > 0);
    end

   function residual = inner_fun(w)
        % Compute the output temperature using the WCT model
        out = fan_speed_to_air_mass_flow_rate_fit(w);
        
        % Compute squared residual
        residual = abs(out - ma_kgs_);
    end  
end