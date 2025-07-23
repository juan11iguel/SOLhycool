function [Tout, Ce] = dc_model_physical(Tamb, Tin, q, w_fan, options)
    % DC_MODEL (PHYSICAL)  Predicts outlet temperature and electrical consumption for the physical DC model.
    %
    % Inputs:
    %   Tamb    - Ambient temperature (ºC)
    %   Tin     - Inlet temperature (ºC)
    %   q       - Volumetric flow rate (m³/h)
    %   w_fan   - Fan load (%)
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
    
    arguments (Input)
        Tamb (1,1) double
        Tin (1,1) double
        q (1,1) double
        w_fan (1,1) double
        options.raise_error_on_invalid_inputs (1,1) logical = false
        options.model_data_path string = "NOT_USED_KEPT_FOR_SIMILAR_INTERFACE_WITH_DATA_DRIVEN_VERSION"
        options.silence_warnings logical = false
        options.lb (1,4) double = 0.9*[5.0600   10.0, 5.2211, 11];
        options.ub (1,4) double = 1.1*[50.7500   50.0, 24.1543, 99.1800];
        options.ce_coeffs (1,:) double = [-0.0002431, 0.04761, -2.2, 48.63, -295.6];
    end

    arguments (Output)
        Tout (1,1) double
        Ce (1,1) double
    end

% Validate inputs
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


if ~valid_inputs
    Tout = Tin;
    Ce = 0;

    return;
end

% Else

T_amb = Tamb;
SC_DC = w_fan;
Tin_DC = Tin;
q_DC_m3h = q;


%% PARÁMETROS DE RESOLUCIÓN

n_max=100;   % Número máxima de iteraciones 
dif_Q_lim=0.1; % Criterio de convergencia calor. Diferencia relativa (%) entre calores calculados mediante proceso iterativo
dif_T_lim=0.001; % Criterio de convergencia temperatura. Diferencia (ºC) entre temperatura calculada y estimación previa 

% PARÁMETROS GEOMÉTRICOS DEL INTERCAMBIADOR
A_pa=4.32;
cat=0.0327;
D_e=0.0127;
D_i=0.0094;
factor_fin_cor=1.0667;
h_fin=0.0024;
h_plate=0.392;
hip=0.0372;
k_fin=237;
k_tube=350;
L_1=0.0186;
L_2=0.0356;
L_te=3.6;
n_tb=60;
n_wp=3;
t_fin=2.1e-04;
w_plate=1.068;

%% Estimación inicial de temperaturas
Tout_DC_est=Tin_DC;
T_air_o_est=T_amb;

while(1)  
    % Este primer bucle se utiliza porque para el cálculo de las propiedades se
    % debe usar la temperatura promedio para ambas corrientes, sin embargo,
    % la de salida no se conoce, con lo que es necesario iterar. 
    
    %% COEFICIENTE CONVECCIÓN LADO AGUA
    
    % Calculamos gasto másico de agua. Como el caudalímetro está a la salida considero la temperatura a la
    % salida estimada
    prop=water_prop(Tout_DC_est); 
    rho_wo=prop(1);
    m_dot_w = q_DC_m3h/3600.*rho_wo;
    % Gasto másico de aire
    m_air=calcula_m_air(SC_DC);
    
    % Propiedades del agua a la temperatura media
    prop=water_prop((Tin_DC+Tout_DC_est)/2);
    rho_w=prop(1);
    mu_w=prop(2);
    cp_w=prop(3);
    k_w=prop(4);
    Pr_w=prop(5);
    
    A_pw=pi*D_i^2/4*n_tb; % Área transversal de paso del agua (m^2)
    u_w=(q_DC_m3h/3600)/A_pw; % Velocidad media del agua (m/s)
    Re_w=rho_w.*u_w*D_i./mu_w;  % Número de Reynolds lado agua 
    
    % Coeficiente de convección con correlación Gnielinski
    lambda_w=(1.82*log10(Re_w)-1.64).^(-2); % Factor de fricción lado agua
    K=(1+(D_i/L_te)^(2/3)); % Factor que tiene en cuenta la longitud del tubo
    Nu_w = (lambda_w.*(Re_w-1000).*Pr_w.*K)./(8.*(1+12.7.*(lambda_w./8).^(1/2).*(Pr_w.^(2/3)-1))); % Número de Nusselt lado agua
    h_w=Nu_w.*k_w/D_i; % Coeficiente de convección lado agua (W/(m2ºC))
    
    %% COEFICIENTE CONVECCIÓN LADO AIRE
    
    % Propiedades del aire a la temperatura media
    prop=air_prop((T_amb+T_air_o_est)/2,101300);
    rho_a=prop(1);
    mu_a=prop(2);
    cp_a=prop(3);
    k_a=prop(4);
    Pr_a=prop(5);
    
    u_a=m_air./(rho_a*A_pa); % Velocidad media lado aire (m/s)
    Re_a=rho_a.*u_a*D_e./mu_a; % Número de Reynolds lado aire
    
    Nu_a=0.0064111.*Re_a.^0.91433 .*Pr_a.^0.36; % Correlación empirica (usando ensayos previos)
    h_a=Nu_a.*k_a./D_e; % Coeficiente de convección lado aire (W/(m2ºC))
    
    %% CALOR DISIPADO TOTAL
    
    A_int=pi*D_i*L_te*n_tb*n_wp; % Área interior, lado agua (m2)
    
    n_plates=floor(L_te/(t_fin+h_fin)); % Numero de placas/aletas
    
    A_ext_nf=(pi*D_i*L_te*n_tb*n_wp)-((pi*D_i*t_fin*n_plates*n_tb*n_wp));    % Área exterior sin aletas (lado aire)
    A_ext_f=2*((n_plates*w_plate*h_plate)-(pi*D_e^2/4*n_plates*n_tb*n_wp)); % Área de las aletas (lado aire)
    A_ext=A_ext_nf+factor_fin_cor*A_ext_f; % área exterior total, lado aire (m2)
    
    UA_inv=1./(A_int.*h_w)+log(D_e./D_i)/(2*pi*k_tube*L_te*n_tb)+1./(A_ext.*h_a);
    UA=UA_inv.^(-1); % Producto U·A 
    
    %% CÁLCULO TEMP. SALIDA DEL AIRE
    
    C_W=m_dot_w.*cp_w; % Capacidad calorífica agua
    C_A=m_air.*cp_a;   % Capacidad calorífica aire
    
    % Resolvemos el intercambiador directamente mediante proceso iterativo
        % Es encesario resolverlo así porque no disponenmos de la relación
        % eficiencia(NTU,c) para esta topología.
        
         n=0;  % Inicializamos el contador del número de iteraciones
            if C_W>C_A
                Tout_DC_max=Tin_DC;
                Q_max=m_air*cp_a*(Tin_DC-T_amb);
                Tout_DC_min=Tin_DC-Q_max/(m_dot_w*cp_w);           
            else
                Tout_DC_max=Tin_DC;
                Tout_DC_min=T_amb;
            end
            
        Tout_DC_prev= (Tout_DC_min+Tout_DC_max)/2;
            
        while(1)
            n=n+1;  % Se actualiza número de iteración        
            % Calor lado agua
            Q_water=m_dot_w*cp_w*(Tin_DC-Tout_DC_prev);
            % Temperatura de salida del aire
            T_air_o=T_amb+Q_water/(m_air*cp_a);
            % Calor según la ley de enf. de Newton
            F= calculo_FT(Tin_DC,Tout_DC_prev,T_amb,T_air_o); % Factor de corrección de LMTD
            DTLM=calculo_DTLM(Tin_DC,Tout_DC_prev,T_amb,T_air_o); % Diferencia de temperaturas logarítmica media(ºC)
            Q_law=UA*F*DTLM;
    
            dif_Q=(Q_water-Q_law)/Q_law*100; % Diferencia relativa entre calores
            
            if (abs(dif_Q)<=dif_Q_lim) || n>=n_max % Si se cump,e criterio de convergencia o se supera número máximo de iteraciones
                n_iter=n;
                Tout_DC=Tout_DC_prev;
                break;
            else
                if Q_water<Q_law % Aumentamos 'Q_water' bajando la temperatura (se enfría)
                    Tout_DC_max=Tout_DC_prev;
                else   % Reducimos 'Q_water' aumentando la temperatura (se enfría)
                    Tout_DC_min=Tout_DC_prev;
                end
                Tout_DC_prev= (Tout_DC_min+Tout_DC_max)/2;
            end
        end
    
    if max(abs(Tout_DC-Tout_DC_est))<dif_T_lim && max(abs(T_air_o-T_air_o_est))<dif_T_lim   % Se comprueba criterio de convergencia para las temperaturas (se aplica a lado aire y agua)
        break;
    else
        % Actualizamos estimación
        Tout_DC_est=Tout_DC;
        T_air_o_est=T_air_o;
    end

end

%% SALIDAS-OUTPUTS

% Tout_DC;   % Temperatura de salida del agua (ºC)
% T_air_o;   % Temperatura de salida del aire (ºC)
% Q_law;     % Calor intercambiado (W)

Ce = power_consumption(w_fan) * 1e-3; % kW
Tout = Tout_DC;

% END OF MAIN FUNCTION ----------------------------------------------------

%% FUNCIONES

% Propiedades agua
function  prop = water_prop(T_w)
    rho_w=-1.72087973954183E-07*T_w^4+0.0000480220158358691*T_w^3-0.00782109015813148*T_w^2+0.0563115452841885*T_w+999.8;
    k_w = -0.614255+ 6.9962e-3*(T_w+273.15)-1.01075e-5*(T_w+273.15)^2+4.74737e-12*(T_w+273.15)^4;
    mu_w = 2.414e-5*10^(247.8/(T_w+273.15-140));
    cp_w = 8.15599e3-28.0627*(T_w+273.15)+5.11283e-2*(T_w+273.15)^2-2.17582e-13*(T_w+273.15)^6;
    Pr_w = mu_w * cp_w / k_w;
    prop=[rho_w,mu_w,cp_w,k_w,Pr_w];
end

% Propiedades aire
function prop = air_prop(T_a,p_a)
    R = 0.287;
    rho_a = p_a/(R*(T_a+273.15));
    mu_a = 2.287973e-6 + 6.259793e-8*(T_a+273.15) - 3.131956e-11*(T_a+273.15)^2 + 8.15038e-15*(T_a+273.15)^3;
    cp_a = 1.045356e3 - 3.161783e-1*(T_a+273.15)+7.083814e-4*(T_a+273.15)^2-2.705209e-7*(T_a+273.15)^3;
    k_a = -4.937787e-4 + 1.018087e-4*(T_a+273.15) - 4.627937e-8*(T_a+273.15)^2 + 1.250603e-11*(T_a+273.15)^3;
    Pr_a = mu_a*cp_a/k_a;
    prop=[rho_a, mu_a, cp_a, k_a,  Pr_a];
end

% Gasto de aire
function m_dot_a =calcula_m_air(SC_DC)
    m_dot_a =0.30195*SC_DC-1.02179;
end

% Salto de temperaturas logarítmico medio
function DTLM = calculo_DTLM(Tin_DC,Tout_DC,T_amb,T_air_o)
%     DTLM=((Tin_DC-T_air_o)-(Tout_DC-T_amb)) / log((Tin_DC-T_air_o) / (Tout_DC-T_amb));
   delta_T1=Tin_DC-T_air_o;
   delta_T2=Tout_DC-T_amb;
   DTLM=(delta_T2-delta_T1)/log(delta_T2/delta_T1);
   DTLM=real(DTLM);
end
 
% Cálculo del factor de corrección del LMTD
function FT = calculo_FT(Tin_DC,Tout_DC,T_amb,T_air_o)

% Coeficientes para tres pasos por carcasa (de Kroger pág 462)
    aik = [-0.843 0.0302    0.48  0.0812 
            5.85   -0.00964  -3.28 -0.834
            -12.8  -0.228    7.11  2.19
            9.24   0.266     -4.9  -1.69];
   
    phi_1 = (Tin_DC - Tout_DC)/(Tin_DC - T_amb);
    phi_2 = (T_air_o - T_amb)/(Tin_DC - T_amb);
    phi_3 = (phi_1 - phi_2)./log((1 - phi_2)/(1 - phi_1));
    if phi_2 > 1
        FT = 1;
        else
            FT = 0;
            for i=1:4
                for k=1:4
                    FT = FT+aik(i,k)*(1-phi_3)^k*sind(2*i*atan(phi_1/phi_2));
                end
            end
            FT = 1-FT;
    end
end

function P_fan_W = power_consumption(w_fan)
    P_fan_W = max(0, polyval(options.ce_coeffs, w_fan)); % W
end

function raise_error(variable, value, lower_limit, upper_limit)
    msg = sprintf("Input %s=%.2f is outside limits (%.2f < %s < %.2f)", string(variable), value, lower_limit, string(variable), upper_limit);
    throw(MException('model:invalid_input', msg))
end

end