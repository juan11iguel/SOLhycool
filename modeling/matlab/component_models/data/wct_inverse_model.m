function [wwct, valid] = wct_inverse_model(Tamb, HR, Tin, q, Tout, options)
%WCT_INVERSE_MODEL Solves for wwct using fmincon with output validation
    
    arguments (Input)
        Tamb (1,1) double
        HR (1,1) double
        Tin (1,1) double
        q (1,1) double
        Tout (1,1) double
        options.lb (1,1) double = 0;
        options.ub (1,1) double = 93.4161;
        options.silence_warnings logical = false
        options.tolerance (1,1) double = 1e-3
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
    [wwct, fval, exitflag] = fmincon(@(wwct) inner_model(wwct), options.lb, [], [], Aeq, beq, options.lb, options.ub, [], opt);
    
    % Determine validity based on residual and exitflag
    valid = (fval <= options.tolerance) && (exitflag > 0);

    function residual = inner_model(wwct)
        % Compute the output temperature using the WCT model
        Twct_out = wct_model(Tamb, HR, Tin, q, wwct, silence_warnings=options.silence_warnings);
        
        % Compute squared residual
        residual = (Tout - Twct_out).^2;
    end

end
