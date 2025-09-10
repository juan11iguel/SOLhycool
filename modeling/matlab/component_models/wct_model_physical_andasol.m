function [Twct_out, M_lost_wct, Pth, Pe] = wct_model_physical_andasol(Tamb, HR, Twct_in, Mwct, SC_fan_wct, SC_pump_wct, varargin)

    % Model originally created by Pedro Navarro, adapted and scaled by Lidia Roca Sobrino

    iP = inputParser;        
    addParameter(iP, 'c_poppe', 1.52); %1.4889)
    addParameter(iP, 'n_poppe', -0.69); %-0.71)
    addParameter(iP, 'Ta_out', 40)
    addParameter(iP, 'HR2', 100)
    
    % Output from scaling script wct_scaling.m
    addParameter(iP, 'Mwct_min', 320*3600/1000)
    addParameter(iP, 'Mwct_max', 1100*3600/1000)
    addParameter(iP, 'params_pc2mair', [-0.01032,2.43,501.1])

    
    parse(iP,varargin{:})
    c_poppe = iP.Results.c_poppe;
    n_poppe = iP.Results.n_poppe;
    Ta_out = iP.Results.Ta_out;
    HR2 = iP.Results.HR2;
    Mwct_min = iP.Results.Mwct_min;
    Mwct_max = iP.Results.Mwct_max;
    params_pc2mair = iP.Results.params_pc2mair;
    
    max_values = [50, 100, 50, Mwct_max, 100, 100];
    min_values = [ 5,   5, 10,  Mwct_min,  20,  25];
    vars = ["Tamb", "HR", "Twct_in", "Mwct", "SC_fan_wct", "SC_pump_wct"];
    
    ERROR = 0;
    for idx=1:length(vars)
        var = vars(idx); value = eval(var);
        if value > max_values(idx) | value < min_values(idx)
        else
            ERROR = ERROR+1;
        end
    end
    ERROR = 6;
    
    if ERROR == 6
    m_drift= 0;%0.1; % caudal perdido por separador a pesar de contraflujo, dato fabricante (%)
    
% %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
    ma = ajuste_m_dot_a_andasol(SC_fan_wct);
   % ma = ajuste_m_dot_aT(SC_fan_wct,Tamb);   
% %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

    [Tdb, w, phi, h, Tdp, v, Twb] = Psychrometricsnew('Tdb',Tamb,'phi',HR); % Salidas: [Tdb, humratio, phi, entalphy, Tdp, volume, Twb]
    Tww =Twct_in;
    Dens_agua=-1.72087973954183E-07*Tww^4+0.0000480220158358691*Tww^3-0.00782109015813148*Tww^2+0.0563115452841885*Tww+999.8;
    mw = Mwct * Dens_agua /3600;

    % Obtener correlación de Merkel a partir de ajuste y ratio de flujos
    Me_corr = c_poppe*(mw/ma)^(n_poppe);

    % Calcular temperatura de salida y consumo de agua
    options = optimset('Display', 'off');
    fun=@(x) (Me_Poppe_cc(Twct_in+273.15,x(1)+273.15,Tamb+273.15,Twb+273.15,ma,mw,101325)- Me_corr);
    x0=Twct_in-6;
    Twct_out = fsolve(fun,x0,options); % ºC, kg/s
    [Me_Poppe, M_lost_wct] = Me_Poppe_cc(Twct_in+273.15,Twct_out+273.15,Tamb+273.15,Twb+273.15,ma,mw,101325);
    M_lost_wct = m_drift/100 * mw + M_lost_wct;

    % Converir M_lost_wct de kg/s a L/min
    Tww =Twct_out;
    Dens_agua=-1.72087973954183E-07*Tww^4+0.0000480220158358691*Tww^3-0.00782109015813148*Tww^2+0.0563115452841885*Tww+999.8;
    M_lost_wct = M_lost_wct / Dens_agua  * 1000*60;

    % Consumo eléctrico
    Pe = ConsumoElectrico_E01_andasol(SC_fan_wct,Tamb,HR); % + ConsumoElectrico_P7(SC_pump_wct); % kWe
    Pth = Mwct/3.6*(Twct_in - Twct_out)*4.186; % Mwct: m³/h -> kg/s; kWth
   
 
    else
    Twct_out = 0;
    M_lost_wct = 1;
    end


%     function v_aire = ajuste_v_aire(SC_fan_wct)
%         % SC_fan_wct -> v_aire (kg/s)
%         %      f(x) = p1*x^2 + p2*x + p3
%         % Coefficients (with 95% confidence bounds):
%         p1 = -0.00027051;
%         p2 = 0.06744305;
%         p3 = 0.40447051;
%         v_aire = p1*(SC_fan_wct)^2 + p2*SC_fan_wct - p3;
%     end

%     function m_dot_a = ajuste_m_dot_a(SC_fan_wct)
%         p1 = -0.0014;
%         p2 = 0.1743;
%         p3 = -0.7251;
%         m_dot_a = p1*(SC_fan_wct/2)^2 + p2*SC_fan_wct/2 + p3;
%     end

% %% variador de frecuencia (%) - caudal de aire (m3/h) WCT planta andasol
%     function m_dot_a = ajuste_m_dot_a_andasol(SC_fan_wct)
%        p1 =     -0.1461;
%        p2 =       36.37;
%        p3 =       130.7;
%        m_dot_a = p1*SC_fan_wct^2 + p2*SC_fan_wct + p3;
%     end

%% variador de frecuencia (%) - flujo másico de aire (kg/s) WCT planta andasol
function m_dot_a = ajuste_m_dot_a_andasol(SC_fan_wct)
       p1 =     params_pc2mair(1); %-0.01032;
       p2 =     params_pc2mair(2); %  2.43;
       p3 =     params_pc2mair(3); % 501.1;
       m_dot_a = p1*SC_fan_wct^2 + p2*SC_fan_wct + p3;
end

%     function m_dot_a = ajuste_m_dot_aT(SC_fan_wct,Tamb)
%         p00 =   -0.0433;
%         p10 =   0.1650;
%         p01 =   -0.0273;   
%         p20 =   -0.0013;  
%         p11 =   0.0000;    
%         p02 =   0.0003;    
%         m_dot_a = p00 + p10*(SC_fan_wct/2) + p01*Tamb + p20*(SC_fan_wct/2)^2 + p11*(SC_fan_wct/2)*Tamb + p02*Tamb^2;
%     end

    function [CE] = ConsumoElectrico_E01_andasol(x,T,HR)
        % Nota: estoy tomando la T del ambiente, no del aire a la salida
        % para calcular la densidad del aire.
        ef=0.7;
        [Tdb_2, w_2, phi_2, h_2, Tdp_2, v_2, Twb_2] = Psychrometricsnew('Tdb',T,'phi',HR); % Salidas: [Tdb, humratio, phi, entalphy, Tdp, volume, Twb]
        rho_air=1/v_2;
        Qair= (ajuste_m_dot_a_andasol(x))/rho_air; % m3/s
        CE=(dp_wct(x)* Qair/1000)/ef; %kW        
    end

    function [dp_est] = dp_wct(fan)
        p1 =     0.06322  ;
        p2 =      -1.503  ;
        p3 =       100.9  ;
        dp_est = p1*fan^2 + p2*fan + p3; %Pa
    end

    function [CE] = ConsumoElectrico_P7(x)
    % x -> SC E01 (%)
    % f(x) = p1*x^3 + p2*x^2 + p3*x + p4
           p1 =    0.005245  ;
           p2 =    -0.08947  ;
           p3 =       4.514  ;
           p4 =       45.41 ;
    CE=(p1.*x.^3 + p2.*x.^2 + p3.*x + p4)/1000; %kW
    
    end

    function raise_error(variable, lower_limit, upper_limit)
        msg = sprintf("Input %s is outside limits (%.2f > %s > %.2f)", string(variable), lower_limit, string(variable), upper_limit);
        throw(MException('MED_model:invalid_input', msg))
    end
    
    function [Tda_ss] = T_da_ss(h,w,pT)
        %La función T_da_ss devuelve la temperatura del aire (K) que, en
        %condiciones de sobresaturación, verifica los valores de entalpía y humedad
        %específica introducidos como inputs. 
        
        %% Ejemplo de cálculo Kloppers
        
        % h=50.01967;
        % w=0.0133338;
        % pT=101712.27;
        % [Tda_ss] = T_da_ss(50,0.0133,101712.27)
        % El resultado (página 8 apéndice G) Tda_ss=290.8448 K.
        
        %% Constantes para el cálculo de las propiedades termofíscas del aire y vapor de agua Kröger (Anexo A AIR-COOLED HEAT EXCHANGERS AND COOLING TOWERS)
        
        To= 273.15;
        C1=1.045356*10^3;
        C2=3.161783*10^(-1);
        C3=7.083814*10^(-4);
        C4=2.705209*10^(-7);
        C5=1.3605*10^3;
        C6=2.31334;
        C7=2.46784*10^(-10);
        C8=5.91332*10^(-13);
        C9=3.4831814*10^6;
        C10=5.8627703*10^3;
        C11=12.139568;
        C12=1.40290431*10^(-2);
        C13=8.15599*10^3;
        C14=2.80627*10^1;
        C15=5.11283*10^(-2);
        C16=2.17582*10^(-13);
        C17=2501.6;
        C18=2.3263;
        C19=1.8577;
        C20=4.184;
        C21=0.62509;
        C22=1.005;
        C23=1.00416;
        C24=10.79586;
        C25=5.02808;
        C26=1.50474*10^(-4);
        C27=4.2873*10^(-4);
        C28=2.786118312;
        C29=0.865;
        C30=0.667;
        C31=0.622;
        
        h_fg=C9-C10*To+C11*(To^2)-C12*(To^3); % Entalpía de vaporización (evaluada en 273.15 K)
        
        f=@(x)((((C1-C2*((x(1)+273.15)/2)+C3*(((x(1)+273.15)/2))^2-C4*(((x(1)+273.15)/2))^3)*(x(1)-273.15)+((0.62198*(10^(C24*(1-(To/x(1)))+C25*(log10(To/x(1)))+C26*(1-10^((-8.29692)*((x(1)/To)-1)))+C27*(10^((4.76955)*(1-(To/x(1))))-1)+C28)) )/(pT-(10^(C24*(1-(To/x(1)))+C25*(log10(To/x(1)))+C26*(1-10^((-8.29692)*((x(1)/To)-1)))+C27*(10^((4.76955)*(1-(To/x(1))))-1)+C28)) ))*(h_fg+(C13-C14*((x(1)+273.15)/2)+C15*(((x(1)+273.15)/2))^2-C16*(((x(1)+273.15)/2))^6)*(x(1)-273.15))+(w-((0.62198*(10^(C24*(1-(To/x(1)))+C25*(log10(To/x(1)))+C26*(1-10^((-8.29692)*((x(1)/To)-1)))+C27*(10^((4.76955)*(1-(To/x(1))))-1)+C28)) )/(pT-(10^(C24*(1-(To/x(1)))+C25*(log10(To/x(1)))+C26*(1-10^((-8.29692)*((x(1)/To)-1)))+C27*(10^((4.76955)*(1-(To/x(1))))-1)+C28)) )))*(C13-C14*((x(1)+273.15)/2)+C15*(((x(1)+273.15)/2))^2-C16*(((x(1)+273.15)/2))^6)*(x(1)-273.15))/1000)-h);
        x0=[273.15]; 
        x=fsolve(f,x0,options);
        
        Tda_ss=x;
    
    end
    
    function [w_a] = w_a(Tda,HR,pT)
    %La función w devuelve la humedad del aire en (kg/kg) a partir de la temperatura seca del aire (K), la humedad relativa (%) y la presión total del aire (Pa)
    
    % Tda=9.7+273.15;
    % HR=82.54;
    % pT=101712.27;
    
    %% Constantes para el cálculo de las propiedades termofíscas del aire y vapor de agua Kröger (Anexo A AIR-COOLED HEAT EXCHANGERS AND COOLING TOWERS)
    
    To= 273.15;
    C1=1.045356*10^3;
    C2=3.161783*10^(-1);
    C3=7.083814*10^(-4);
    C4=2.705209*10^(-7);
    C5=1.3605*10^3;
    C6=2.31334;
    C7=2.46784*10^(-10);
    C8=5.91332*10^(-13);
    C9=3.4831814*10^6;
    C10=5.8627703*10^3;
    C11=12.139568;
    C12=1.40290431*10^(-2);
    C13=8.15599*10^3;
    C14=2.80627*10^1;
    C15=5.11283*10^(-2);
    C16=2.17582*10^(-13);
    C17=2501.6;
    C18=2.3263;
    C19=1.8577;
    C20=4.184;
    C21=0.62509;
    C22=1.005;
    C23=1.00416;
    C24=10.79586;
    C25=5.02808;
    C26=1.50474*10^(-4);
    C27=4.2873*10^(-4);
    C28=2.786118312;
    C29=0.865;
    C30=0.667;
    C31=0.622;
    
    %% Cálculo humedad
    
        pvs=10^(C24*(1-(To/Tda))+C25*(log10(To/Tda))+C26*(1-10^((-8.29692)*((Tda/To)-1)))+C27*(10^((4.76955)*(1-(To/Tda)))-1)+C28);   % pvs
        w_a = (0.62198 * pvs * (HR / 100)) / (pT - pvs * (HR / 100)); %w

end


end