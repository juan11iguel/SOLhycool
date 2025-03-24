function [Q, U] = condenser_heats_model(mv_kgs, Tv, mc_kgs, Tc_in, Tc_out, options)
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
        Tv (1,1) double
        mc_kgs (1,1) double
        Tc_in (1,1) double
        Tc_out (1,1) double
        options.option (1,1) int8 {mustBeInRange(options.option, 1, 7)} = 7
        options.A (1,1) double {mustBePositive} = 19.30 %%19.967-> https://collab.psa.es/f/174826 24/U;
    end

    arguments (Output)
        Q (1,3) double
        U (1,1) double
    end
    
    U=condenser_heat_transfer_coefficient(mc_kgs*3.6, Tc_in, Tv, options.option); % qc/mc: kg/s -> m3/h
    
    % ms_u=ms/3600; % kg/h -> kg/s
    % mc_u=qc*1000/3600; % m³/h -> kg/s
    lambda=XSteam('hV_T',Tv)-XSteam('hL_T',Tv);
    Cp=XSteam('Cp_pT',2,(Tc_in+Tc_out)/2);
    dT1=Tv-Tc_in;
    dT2=Tv-Tc_out;
    
    % para evitar problemas con el logaritmo neperiano hay que asegurarse que
    % dT1>dT2 
    %dTML=(dT1-dT2)/log(max(dT1/dT2,1.1)); % así me aseguro que no da problemas 
    dTML=(dT1-dT2)/log(dT1/dT2); 
    
    % if dT1>dT2
    %     dTML=(dT1-dT2)/log(dT1/dT2);
    % else
    %     dTML=(dT1+dT2)/2;
    % end;
    
    Q = [mv_kgs*lambda;
         mc_kgs*Cp*(Tc_out-Tc_in);
         U*options.A*dTML]';
end


