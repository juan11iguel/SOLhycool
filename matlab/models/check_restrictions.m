function [c, ceq] = check_restrictions(x, Tamb, HR, Mv, Tv, varargin)

    % global mv tv
    % global valid_inputs

    % Mv = mv; Tv = tv;

    R1  = x(1);
    R2  = x(2);
    
    % Check if mc_m3h is provided as an input
    if nargin > 5 && ~isempty(varargin{1})
        mc_m3h = varargin{1};
        Tdc_out = x(3);
        Twct_out = x(4);
    else
        % Default value or handling for mc_m3h when not provided
        mc_m3h  = x(3); % m3/h
        Tdc_out = x(4);
        Twct_out = x(5);
    end
    % Tc_in = x(6);

    % mdc_min = 5;    % Imposed by DC model (m3/h)
    % mdc_max = 24.15; % % Imposed by DC model (m3/h)
    % mwct_min = 5.7; % Imposed by WCT model (m3/h)
    % mwct_max = 34.84; % Imposed by WCT model (m3/h)
    % 
    % Tdc_in_model_min = 33.16; % Minimum temperature evaluated in DC model (ºC)
    % Tdc_in_model_max = 41.92; % Maximum temperature evaluated in DC model (ºC)
    % Twct_in_model_min = 31.17; % Minimum temperature evaluated in WCT model (ºC)
    % Twct_in_model_max = 40.94; % Maximum temperature evaluated in WCT model (ºC)

    % [lb_R1, ub_R1] = deal(0, 1);
    % [lb_R2, ub_R2] = deal(0, 1);
    % [lb_mc_m3h, ub_mc_m3h] = deal(12, 24);
    % [lb_Tcin, ub_Tcin] = deal(Tcin_min, tv-2); % deltaTc_min, deltaT_min 
    % [lb_Tdc_out, ub_Tdc_out] = deal(tamb, tv-2); % Habria que tenerlo sincronizado con evaluate_ptop, que deberia ser una clase
    % [lb_Twct_out, ub_Twct_out] = deal(Twb, tv-2);
    % 
    % lb = [lb_R1, lb_R2, lb_mc_m3h, lb_Tdc_out, lb_Twct_out, lb_Tcin];
    % ub = [ub_R1, ub_R2, ub_mc_m3h, ub_Tdc_out, ub_Twct_out, ub_Tcin];

    % w_fan_min = 0;   % (%)
    % w_fan_wct_max = 93.4; % (%)
    % w_fan_dc_max  = 99.18; % (%)

    deltaT_min = 1;  % Minimum temperature difference between vapor and condenser outlet (ºC)

    [~, ~, ~, ~, ~, ~, Twb] = Psychrometricsnew('Tdb', Tamb, 'phi', HR, 'P', 101.325);
    Tc_in_min = Twb;
    Tc_out_max = Tv - deltaT_min;

    Pc = 1.6; % bar
    mc_kgs = mc_m3h/3600*densW(25, Pc); % m3/h -> kg/s


    % Obtener Tc_in a partir de variables de decision
    Tc_in = (1-R1)*(1-R2)*Tdc_out + (R1*(1-R2)+R2)*Twct_out;
    % Tc_in > Tc_in_min
    c(1) = Tc_in_min - Tc_in;

    % Comprobar que se cumple la potencia de refrigeracion con modelo de condensador
    Tc_out = Tc_in + Mv*enthalpySatVapTW(Tv)/(mc_kgs*cpW(Tc_in, Pc));
    % Tc_out < Tc_out_max
    c(2) = Tc_out - Tc_out_max;


    % Restricciones de desigualdad c: 
    % x1+x2<1 -> c = x1+x2-1
    % x1 > x2-1 -> c = x1-x2-1
    % c <= 0
    
    % Restricciones en caudal y temperatura de modelos de ANN

%     if R1<0.95
%         
%         mdc = mc_m3h*(1-R1);
%         % mdc > mdc_min
%         c(3) = mdc_min - mdc - 0.5; % Everything below minimum plus some margin (0.5) will be considered zero by combined_model
%         % mdc < mdc_max
%         c(4) = mdc - mdc_max - 0.5; % Everything below minimum plus some margin (0.5) will be considered zero by combined_model
%         
%         % Only check temperature limits if system is going to be used
%         if mdc > mdc_min && mdc<mdc_max
%             % Tdc_in (=Tc_out) > Tdc_in_min
%             c(5) = Tdc_in_model_min - Tc_out;
%             % Tdc_in (=Tc_out) < Tdc_in_max
%             c(6) = Tdc_out - Tdc_in_model_max;
%         else
%             c(5) = 0;
%             c(6) = 0;
%         end
%     else
%         c(3) = 0;
%         c(4) = 0;
%         c(5) = 0;
%         c(6) = 0;
%     end
    
    % WCT
%     if R1>0.05 && R2>0.05
%         mwct = mc_m3h*(R1*(1-R2)+R2);
%         
%         % mwct > mwct_min
%         c(7) = mwct_min - mwct;
%         % mwct < mwct_max
%         c(8) = mwct - mwct_max;
%         
%         
% 
%         % Only check temperature limits if system is going to be used
%         if mwct > mwct_min && mwct<mwct_max
%             % Twct_in = (mdc*Tc_out + mc_m3h*R1*Tdc_out)/(mdc+mc_m3h*R1);
%             Twct_in = R1*Tc_out + ((1-R1)*R2+R1)*Tdc_out;
%             % Twct_in > Twct_in_min
%             c(9) = Twct_in_model_min - Twct_in;
%             % Twct_in < Twct_in_max
%             c(10) = Twct_in - Twct_in_model_max;
%         else
%             c(9)  = 0;
%             c(10) = 0;
%         end
%     else
%         c(7)  = 0;
%         c(8)  = 0;
%         c(9)  = 0;
%         c(10) = 0;
%     end


    % Temperatura de salida consecuencia de decision de R1, R2, mc, Tdc, Twct
    % tiene que coincidir con variable de decision
    % Tc_in* - Tc_in f(R1, R2, mc, Tdc, Twct) < 0.1
    % c(9) = abs(Tc_in  - ((1-R1)*(1-R2)*Tdc_out + (R1*(1-R2)+R2)*Twct_out)) - 0.1;
    % margen de 0.1 ºC

    % Restricciones de velocidad de ventilador
    % Tc_out = Tc_in + Mv*enthalpySatVapTW(Tv)/(mc_kgs*cpW(Tc_out, Pc));
    % 
    % % Solve w_dc_fan and w_wct_fan
    % fun = @(x)calculo_w(x, Tc_in, Tamb, HR, mc_m3h, Tc_out, R1, R2);
    % lb = [w_fan_min, w_fan_min]; ub = [w_fan_dc_max, w_fan_wct_max]; x0 = [50, 50];
    % 
    % out = fmincon(fun,x0,A,b,Aeq,beq,lb,ub,[],options_fmincon);
    % [w_dc_fan, w_wct_fan] = deal(out(1), out(2));
    % 
    % c(8) = Tc_in - combined_model(Tamb, HR, mc_m3h, Tc_out, R1, R2, w_dc_fan, w_wct_fan);

    % Potencia de refrigeracion
    % Tc_out < Tv-deltaTmin
    % c(11) = Tc_out - Tv-deltaT_min; 

    ceq = [];

    % c>0
    % valid_inputs(end+1,:) = c>0; 
    
end
