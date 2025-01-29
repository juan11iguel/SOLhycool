function [Tc_in, Tc_out] = condenser_model(mv_kgs, Tv_C, mc_kgs, options)
    %CONDENSER_MODEL Model of a surface condenser using saturated vapor as
    %input and that outputs saturated liquid
    % It returns thermal power calculated in three different ways:
    % - Log temperature difference and heat transfer
    % - Latent phase change heat of vapour
    % - Sensible absorbed heat by coolant
    %   Detailed explanation goes here
    % Tv: Tv (ºC)
    % Tc_out: Tcout (ºC)
    % ms: caudal de vapor (kg/h)
    % qc: caudal de cooling (m3/h)
    % Tc_in: temperatura de entrada cooling (ºC)
    % option: tipo de correlación seleccionada (1-7)
    arguments (Input)
        mv_kgs (1,1) double
        Tv_C (1,1) double
        mc_kgs (1,1) double
        options.option (1,1) int8 {mustBeInRange(options.option, 1, 7)} = 7
        options.A (1,1) double {mustBePositive} = 19.30 %%19.967-> https://collab.psa.es/f/174826 24/U;
        options.deltaTv_cout_min (1,1) double {mustBePositive} = 2;
        options.Tmin (1,1) double = 25;
    end

    arguments (Output)
        Tc_in (1,1) double
        Tc_out (1,1) double
    end
    
    % opt= optimoptions('fsolve', 'Display', 'off', 'Algorithm', 'trust-region');
    opt = optimoptions('fmincon', 'Algorithm', 'sqp', 'OptimalityTolerance', 1e-10, 'StepTolerance', 1e-11, 'Display','none'); 
   
    Cp = XSteam('Cp_pT',2,Tv_C);
    lambda=XSteam('hV_T',Tv_C)-XSteam('hL_T',Tv_C);
    Qc = mv_kgs * lambda;
    
    lb = [options.Tmin, options.Tmin + Qc / (Cp*mc_kgs)];
    
    Tc_out_max = Tv_C-options.deltaTv_cout_min;
    Tc_in_max = Tc_out_max - Qc / (Cp*mc_kgs);
    ub = [Tc_in_max, Tc_out_max];
    
    x0 = (ub+lb)./2;

    x = fmincon(@(x) inner_model(x), x0, [], [], [], [], lb, ub, [] ,opt);
    Tc_in = x(1);
    Tc_out = x(2);
    
    function error = inner_model(x)
        Tc_in = x(1);
        Tc_out = x(2);
        U=condenser_heat_transfer_coefficient(mc_kgs, Tc_in, Tv_C, options.option);
        
        % ms_u=ms/3600; % kg/h -> kg/s
        % mc_u=qc*1000/3600; % m³/h -> kg/s
        % Cp=XSteam('Cp_pT',2,(Tc_in+Tc_out)/2);
        dT1=Tv_C-Tc_in;
        dT2=Tv_C-Tc_out;
        
        % para evitar problemas con el logaritmo neperiano hay que asegurarse que
        % dT1>dT2 
        %dTML=(dT1-dT2)/log(max(dT1/dT2,1.1)); % así me aseguro que no da problemas 
        dTML=(dT1-dT2)/log(dT1/dT2); 
        
        % if dT1>dT2
        %     dTML=(dT1-dT2)/log(dT1/dT2);
        % else
        %     dTML=(dT1+dT2)/2;
        % end;
        Q = [mv_kgs*lambda, mc_kgs*Cp*(Tc_out-Tc_in), U*options.A*dTML];
        error = sum((Q - mean(Q)).^2);
        % fprintf("condenser model residual: %.2f for Tc_in=%.2f, Tc_out=%.2f, Tv=%.2f\n", error, Tc_in, Tc_out, Tv_C)
    end
end