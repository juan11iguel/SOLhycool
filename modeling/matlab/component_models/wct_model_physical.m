function [Tout, Ce, Cw] = wct_model_physical(Tamb, HR, Tin, q, w_fan, options)
    % WCT_MODEL  Predicts outlet temperature, electrical and water consumption for the WASCOP wet cooling tower.
    % 
    % Inputs:
    %   Tamb    - Ambient temperature (ºC)
    %   HR      - Relative humidity (%)
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
    %   Cw      - Water consumption (l/h)

    arguments (Input)
        Tamb (1,1) double
        HR (1,1) double
        Tin (1,1) double
        q (1,1) double
        w_fan (1,1) double
        options.raise_error_on_invalid_inputs (1,1) logical = false
        options.model_data_path string = "NOT_USED_KEPT_FOR_SIMILAR_INTERFACE_WITH_DATA_DRIVEN_VERSION"
        options.lb (1,5) double = [0.1    0.1     5.0    5.0       0.];
        options.ub (1,5) double = [50.0   99.99   55.0   24.8400   95.];
        options.silence_warnings logical = false
        options.ce_coeffs (1,:) double = [0.4118, -11.54, 189.4];
        
        % Specific parameters for the physical model
        options.c_poppe (1,1) double = 1.4889
        options.n_poppe (1,1) double = -0.71
        options.Ta_out (1,1) double = 40.0
        options.HR2 (1,1) double = 100.0
    end

    arguments (Output)
        Tout (1,1) double % ºC
        Ce (1,1) double % kW
        Cw (1,1) double % l/h
    end


    % Validate inputs
    max_values = options.ub;
    min_values = options.lb;
    vars = ["Tamb", "HR", "Tin", "q", "w_fan"];

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
        % Skip wet cooler
        Tout = Tin;
        Ce = 0;
        Cw = 0;

        return;
    end

    % Else
    Mwct = q;
    SC_fan_wct = w_fan;
    Twct_in = Tin;

    c_poppe = options.c_poppe;
    n_poppe = options.n_poppe;
    Ta_out = options.Ta_out;
    HR2 = options.HR2;

    dTwct=0.1; % paso para iterar. Inicialmente estaba en 6
    m_drift= 0;%0.1; % caudal perdido por separador a pesar de contraflujo, dato fabricante (%)
    
    % %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
    % ma = ajuste_m_dot_a(SC_fan_wct);
    ma = ajuste_m_dot_aT(SC_fan_wct,Tamb);   
    % %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

    [Tdb, w, phi, h, Tdp, v, Twb] = Psychrometricsnew('Tdb',Tamb,'phi',HR); % Salidas: [Tdb, humratio, phi, entalphy, Tdp, volume, Twb]
    Tww =Twct_in;
    Dens_agua=-1.72087973954183E-07*Tww^4+0.0000480220158358691*Tww^3-0.00782109015813148*Tww^2+0.0563115452841885*Tww+999.8;
    mw = Mwct * Dens_agua /3600;

    % Obtener correlación de Merkel a partir de ajuste y ratio de flujos
    Me_corr = c_poppe*(mw/ma)^(n_poppe);

    % Calcular temperatura de salida y consumo de agua
    opts = optimset('Display', 'off','MaxIter', 10);
    fun=@(x) (Me_Poppe_cc(Twct_in+273.15,x(1)+273.15,Tamb+273.15,Twb+273.15,ma,mw,101325)- Me_corr);
    x0=Twct_in-dTwct;
    [Twct_out, fval, exitflag, output] = fsolve(fun,x0,opts); % ºC, kg/s
    [Me_Poppe, M_lost_wct] = Me_Poppe_cc(Twct_in+273.15,Twct_out+273.15,Tamb+273.15,Twb+273.15,ma,mw,101325);
    M_lost_wct = m_drift/100 * mw + M_lost_wct;

    % Converir M_lost_wct de kg/s a L/min
    Tww =Twct_out;
    Dens_agua=-1.72087973954183E-07*Tww^4+0.0000480220158358691*Tww^3-0.00782109015813148*Tww^2+0.0563115452841885*Tww+999.8;
    M_lost_wct = M_lost_wct / Dens_agua  * 1000*3600; % kg/s -> l/h
    
    Tout = Twct_out;
    Cw = M_lost_wct;

    % Consumo eléctrico
    Ce = power_consumption(w_fan) * 1e-3; % kW

    %% NESTED FUNCTIONS
    function P_fan_W = power_consumption(w_fan)
        % Use polyval for fan power calculation
        P_fan_W = max(0, polyval(options.ce_coeffs, w_fan)); % W
    end
end

%% FUNCIONES AUXILIARES

function v_aire = ajuste_v_aire(SC_fan_wct)
    % SC_fan_wct -> v_aire (kg/s)
    %      f(x) = p1*x^2 + p2*x + p3
    % Coefficients (with 95% confidence bounds):
    p1 = -0.00027051;
    p2 = 0.06744305;
    p3 = 0.40447051;
    v_aire = p1*(SC_fan_wct)^2 + p2*SC_fan_wct - p3;
end

function m_dot_a = ajuste_m_dot_a(SC_fan_wct)
    p1 = -0.0014;
    p2 = 0.1743;
    p3 = -0.7251;
    m_dot_a = p1*(SC_fan_wct/2)^2 + p2*SC_fan_wct/2 + p3;
end

function m_dot_a = ajuste_m_dot_aT(SC_fan_wct,Tamb)
    p00 =   -0.0433;
    p10 =   0.1650;
    p01 =   -0.0273;   
    p20 =   -0.0013;  
    p11 =   0.0000;    
    p02 =   0.0003;    
    m_dot_a = p00 + p10*(SC_fan_wct/2) + p01*Tamb + p20*(SC_fan_wct/2)^2 + p11*(SC_fan_wct/2)*Tamb + p02*Tamb^2;
end

function [Tda_ss] = T_da_ss(h,w,pT)
    %La función T_da_ss devuelve la temperatura del aire (K) que, en
    %condiciones de sobresaturación, verifica los valores de entalpía y humedad
    %específica introducidos como inputs. 
    opts = optimset('Display', 'off','MaxIter', 10);
    
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
    x=fsolve(f,x0,opts);
    
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

function raise_error(variable, value, lower_limit, upper_limit)
     msg = sprintf("Input %s=%.2f is outside limits (%.2f > %s > %.2f)", string(variable), value, lower_limit, string(variable), upper_limit);
%         throw(MException('model:invalid_input', msg))
     warning(msg)
end

function [Me_Poppe, M_lost_wct] = Me_Poppe_cc(Tw1,Tw2,Tas1,Tbh,ma,mw,pT)
    %% Experimento 1 Ghazani
    
    % Tw1=52+273.15;
    % Tw2=40+273.15;
    % Tas1=30+273.15;
    % Tbh=25+273.15;
    % ma =265/3600;
    % mw=235/3600;
    % pT=101712.27;
    % 
    % T_0=25+273.15;
    % phi_0=50;
    % p_0=pT;
    % N=10;
    % [R,Res,Me_Poppe_cc] =  Me_Poppe_cc(52+273.15,40+273.15,30+273.15,25+273.15,265/3600,235/3600,101325,10)
    %% Ejemplo aleatorio para torre de refrigeracion 
    
    %Tw1=312.82; %(TEMPERATURA DE ENTRADA DEL AGUA)
    %Tw2=300.92; %(TEMPERATURA DE SALIDA DEL AGUA)
    %Tas1=282.85;%(TEMPERATURA DE ENTRADA DEL AIRE)
    %Tbh=281.38; %(TEMPERATURA DE BULBO HUMEDO DE ENTRADA DE AIRE)
    %HR1=82.54; %(HUMEDAD RELATIVA)
    %ma =4.1340; %(FLUJO MASICO DE AIRE SECO)
    %mw=3.999; %(FLUJO MASICO DE AGUA)
    %pT=101712.27; %(PRESION ATMOSFERICA)
    
    %% Constantes para el cálculo de las propiedades termofíscas del aire y vapor de agua Kröger (Anexo A AIR-COOLED HEAT EXCHANGERS AND COOLING TOWERS)
    N=5;
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
    
    hfg=C9-C10*To+C11*(To^2)-C12*(To^3); % Calor latente del agua a  la temperatura T=To 
    
    % Con la función Psychrometricsnew calculo las propiedades en la entrada
    [Tdb, humratio, phi, entalphy, Tdp, volume, Twb] =Psychrometricsnew('Tdb',Tas1-273.15,'Twb',Tbh-273.15);
    
    %SIENDO tdb TEMPERATURA DE BULBO SECO, humratio HUMEDAD ESPECIFICA, phi
    %HUMEDAD RELATIVA, entalphy ENTALPIA, tdp (), volume VOLUMEN, twb
    %TEMPERATURA DE BULBO HUMEDO.
    
    %% Inicio Runge-Kutta 4º orden 
    % Número de intervalos y DeltaTw
    
    DeltaTw=(Tw1-Tw2)/N;
    
    % Prevemos las dimensiones de las matrices de resultados y de cálculo y
    % definimos el primer nivel de la matriz de resultados
    R_cc=zeros(19,4*N);
    Res_cc=zeros(7,N+1);
    
    
    % Creamos la primera columna matriz resultados Res(:,1).
    % Res(:,1)=[humratio;entalphy/1000;Tw2;0;Tas1;phi;Tbh;0;0;0;0;0;0;0];
    Res_cc(1,1)=humratio; %HUMEDAD ESPECIFICA
    Res_cc(2,1)=entalphy/1000; %ENTALPIA
    Res_cc(3,1)=Tw2; %TEMPERATURA DE SALIDA DEL AGUA
    Res_cc(4,1)=0; % Me al inicio es nulo
    Res_cc(5,1)=Tas1; %TEMPERATURA DE ENTRADA DEL AIRE
    Res_cc(6,1)=phi;%HUMEDAD RELATIVA
    Res_cc(7,1)=Tbh;%TEMPERATURA DE BULBO HUMEDO EN LA ENTRADA DE AIRE.
    
    %% El cálculo de Me depende de la humedad absoluta a la salida. Al ser desconocida realizamos la programación en torno a ella. 
    % Para ello, calculamos un vector de humedades que debe converger en el
    % valor de humedad a la salida. El primer valor será el correspondiente a
    % la entrada y el segundo lo aumentamos un 5% para que entre en el bucle
    % del while
    
    % Humedad específica en la sección de entrada (ya calculada)
    w(1)=Res_cc(1,1);
    wo=w(1,1);  %LA HUMEDAD QUE TENGO A LA SALIDA DIGO QUE VA A SER IGUAL QUE LA QUE TENGO EN LA ENTRADA
    
    f=2;  
    w(f)=1.05*wo;
    
    while abs(w(f)-w(f-1))*100/w(f)>0.1 %ESTE BUCLE VA HACIENDO LAS ITERACIONES HASTA QUE EL ERROR SEA MENOR DE 0.1 
     f=f+1;
     
    for i=1:N;
        if Res_cc(6,i)<100; % Evaluamos HR. Si HR<100 al final del intervalo calculamos normal. De lo contrario consideramos sobresaturación
            %Todo lo que va aqui dentro es el cálculo sin saturación
            for k=1:4; % Cálculo de subetapas en cada intervalo
                j=4*(i-1)+k; 
                 if j==1 % Sirve para identificar que la primera etapa es la entrada del aire y salida del agua
                    R_cc(1,j)=Res_cc(1,i); %GUARDO LA HUMEDAD ESPECIFICA
                    R_cc(2,j)=Res_cc(2,i)*1000; %GUARDO LA ENTALPIA
                    R_cc(3,j)=Res_cc(3,i); %TEMPERATURA DE SALIDA DEL AGUA
                 else % Si no es la primera etapa 
                    if k==1
                    R_cc(1,j)=Res_cc(1,i); % Humedad en el step anterior
                    R_cc(2,j)=Res_cc(2,i)*1000; %h
                    R_cc(3,j)=Res_cc(3,i);
                    R_cc(17,j)=Res_cc(4,i); %Me
                    elseif k==2
                    R_cc(1,j)=R_cc(1,j-1)+R_cc(14,j-1)/2;
                    R_cc(2,j)=R_cc(2,j-1)+R_cc(15,j-1)/2; 
                    R_cc(3,j)=Res_cc(3,i)+DeltaTw/2;
                    elseif k==3
                    R_cc(1,j)=R_cc(1,j-2)+R_cc(14,j-1)/2;
                    R_cc(2,j)=R_cc(2,j-2)+R_cc(15,j-1)/2;
                    R_cc(3,j)=Res_cc(3,i)+DeltaTw/2;                
                    else
                    R_cc(1,j)=R_cc(1,j-3)+R_cc(14,j-1);
                    R_cc(2,j)=R_cc(2,j-3)+R_cc(15,j-1);
                    R_cc(3,j)=Res_cc(3,i)+DeltaTw;
                    end
                 end
            R_cc(4,j)=(R_cc(3,j)+273.15)/2;   %Tªcps (TEMPERATURA A LA QUE TIENEN QUE SER EVALUADOS LOS CALORES ESPECIFICOS)
            R_cc(5,j)=C1-C2*R_cc(4,j)+C3*(R_cc(4,j))^2-C4*(R_cc(4,j))^3;   %Cpa (CALOR ESPECIFICO DEL AIRE SECO)
            R_cc(6,j)=C5+C6*R_cc(4,j)-C7*(R_cc(4,j))^5+C8*(R_cc(4,j))^6;   %Cpv (CALOR ESPECIFICO DEL VAPOR DE AGUA)
            R_cc(7,j)=C13-C14*R_cc(4,j)+C15*(R_cc(4,j))^2-C16*(R_cc(4,j))^6;   %Cpw (CALOR ESPECIFICO DEL AGUA)
            R_cc(8,j)=10^(C24*(1-(To/R_cc(3,j)))+C25*(log10(To/R_cc(3,j)))+C26*(1-10^((-8.29692)*((R_cc(3,j)/To)-1)))+C27*(10^((4.76955)*(1-(To/R_cc(3,j))))-1)+C28);   % pvs (PRESION DE VAPOR DE AGUA EVALUADA EN TO)
            R_cc(9,j)=(C21*R_cc(8,j))/(pT-(C22*R_cc(8,j))); %wsw (RELACION DE HUMEDAD PARA AIRE SATURADO)
            R_cc(10,j)=hfg+(R_cc(6,j)*(R_cc(3,j)-To));   %hv (ENTALPIA DEL VAPOR DE AGUA A LA TEMPERATURA LOCAL, EN RELACION CON EL AGUA A 0ºC)
            R_cc(11,j)=(R_cc(5,j)*(R_cc(3,j)-To))+R_cc(9,j)*R_cc(10,j); %hmasw (ENTALPIA DE AIRE SATURADO A LA TEMPERATURA DEL AGUA)
            R_cc(12,j)=(C29^C30)*((((C31+R_cc(9,j))/(C31+R_cc(1,j)))-1)/(log(((C31+R_cc(9,j))/(C31+R_cc(1,j))))));   %Le (NUMERO DE LEWIS)
            R_cc(13,j)=(mw/ma)*(1-((ma/mw)*(wo-R_cc(1,j))));  %Balance de masa (BALANCE DE MASA)
            R_cc(14,j)=(DeltaTw*R_cc(7,j)*R_cc(13,j)*(R_cc(9,j)-R_cc(1,j)))/(R_cc(11,j)-R_cc(2,j)+(R_cc(12,j)-1)*(R_cc(11,j)-R_cc(2,j)-(R_cc(9,j)-R_cc(1,j))*R_cc(10,j))-((R_cc(9,j)-R_cc(1,j))*R_cc(7,j)*(R_cc(3,j)-To))); %j (CALCULO DE LA J)
            R_cc(15,j)=(DeltaTw*R_cc(7,j)*R_cc(13,j))*(1+(((R_cc(9,j)-R_cc(1,j))*R_cc(7,j)*(R_cc(3,j)-To))/(R_cc(11,j)-R_cc(2,j)+(R_cc(12,j)-1)*(R_cc(11,j)-R_cc(2,j)-(R_cc(9,j)-R_cc(1,j))*R_cc(10,j))-((R_cc(9,j)-R_cc(1,j))*R_cc(7,j)*(R_cc(3,j)-To))))); %k (CALCULO DE LA K)
            R_cc(16,j)=(DeltaTw*R_cc(7,j))/(R_cc(11,j)-R_cc(2,j)+(R_cc(12,j)-1)*(R_cc(11,j)-R_cc(2,j)-(R_cc(9,j)-R_cc(1,j))*R_cc(10,j))-((R_cc(9,j)-R_cc(1,j))*R_cc(7,j)*(R_cc(3,j)-To))); %l (CALCULO DE LA L)
            [Tdb, humratio, phi, entalphy, Tdp, volume, Twb] =Psychrometricsnew('h',R_cc(2,j),'w',R_cc(1,j)); %PARA ESA ENTALPIA Y HUMEDAD ESPECIFICA DE ESE SUBNIVEL OBTENGO LOS VALORES PSICROMETRICOS
            R_cc(18,j)=Tdb+273.15; % Tas puede que difiera del valor real si dentro del intervalo se produce sobresaturación. Si se activan los siguientes comandos se puede evaluar
            end
             
     % Al final del ciclo de k completamos la matriz de resultados. Dejamos en
     % blanco la temperatura del aire, la humedad y el bulbo húmedo al no saber si estamos en condiciones de
     % sobresaturación. Completamos i+1 ya que estamos en k=4 del nivel
     % anterior 
    % Res(:,i+1)=[Res(1,i)+(R(14,j-3)+2*R(14,j-2)+2*R(14,j-1)+R(14,j))/6;(1000*Res(2,i)+(R(15,j-3)+2*R(15,j-2)+2*R(15,j-1)+R(15,j))/6)/1000;Res(3,i)+DeltaTw;Res(4,i)+(R(16,j-3)+2*R(16,j-2)+2*R(16,j-1)+R(16,j))/6;0;0;0;0;0;0;0;0;0;0];     
    Res_cc(1,i+1)=Res_cc(1,i)+(R_cc(14,j-3)+2*R_cc(14,j-2)+2*R_cc(14,j-1)+R_cc(14,j))/6; %RELACION DE HUMEDAD EN EL NIVEL CORRESPONDIENTE
    Res_cc(2,i+1)=(1000*Res_cc(2,i)+(R_cc(15,j-3)+2*R_cc(15,j-2)+2*R_cc(15,j-1)+R_cc(15,j))/6)/1000; %ENTALPIA DEL AIRE EN EL NIVEL CORRESPONDIENTE
    Res_cc(3,i+1)=Res_cc(3,i)+DeltaTw;
    Res_cc(4,i+1)=Res_cc(4,i)+(R_cc(16,j-3)+2*R_cc(16,j-2)+2*R_cc(16,j-1)+R_cc(16,j))/6; %NUMERO DE MERKEL EN EL NIVEL CORRESPONDIENTE
     % Con la función Psychrometricsnew calculo las propiedades a partir h y w
    % de la matriz Res
     [Tdb, humratio, phi, entalphy, Tdp, volume, Twb] =Psychrometricsnew('h',1000*Res_cc(2,i+1),'w',Res_cc(1,i+1));
     
     % Asumimos aire no saturado, E INTRODUCIMOS LOS VALORES QUE NOS INTERESAN
     % DEL DIAGRAMA PICROMETRICO
     Res_cc(5,i+1)=Tdb+273.15; %TEMPERATURA DE BULBO SECO
     Res_cc(6,i+1)=phi;%HUMEDAD RELATIVA
     Res_cc(7,i+1)=Twb+273.15; %TEMPERATURA DE BULBO HUMEDO
     
      
        if Res_cc(6,i+1)<100; %SI LA HUMEDAD RELATIVA ES MENOR DE 100
            % Confirmamos si no está saturado
            Res_cc(5,i+1)=Tdb+273.15;
            Res_cc(6,i+1)=phi;
            Res_cc(7,i+1)=Twb+273.15;
         else
         % Corregimos si está sobresaturado
            Res_cc(5,i+1)=T_da_ss(Res_cc(2,i+1),Res_cc(1,i+1),pT); 
            % La función T_da_ss devuelve la temperatura del aire (K) que, en
            %condiciones de sobresaturación, verifica los valores de entalpía y humedad
            %específica introducidos como inputs.
            Res_cc(6,i+1)=100; %EN ESTE CASO AL ESTAR SOBRESATURADO LA HUMEDAD RELATIVA ES 100
            Res_cc(7,i+1)=Res_cc(5,i+1);      
        end
            
                         
        else %ESTE VA CON EL IF QUE ESTA JUSTO ANTES DEL FOR DE ARRIBA DE MANERA QUE
            %COMO EN ESE NOS SALE QUE EL AIRE YA ESTA SATURADO DA EL SALTO A
            %ESTAS ECUACIONES Y NO HACE EL CALCULO DE NO SATURADO Y DESPUES
            %CORREGIR.
            %Todo lo que va aqui dentro es el cálculo con sobre saturación
             for k=1:4; % Cálculo de subetapas en cada intervalo
                j=4*(i-1)+k; 
                    if k==1
                    R_cc(1,j)=Res_cc(1,i); % Humedad en el step anterior
                    R_cc(2,j)=Res_cc(2,i)*1000; %h
                    R_cc(3,j)=Res_cc(3,i);
                    R_cc(17,j)=Res_cc(4,i); %Me
                    elseif k==2
                    R_cc(1,j)=R_cc(1,j-1)+R_cc(14,j-1)/2;
                    R_cc(2,j)=R_cc(2,j-1)+R_cc(15,j-1)/2; 
                    R_cc(3,j)=Res_cc(3,i)+DeltaTw/2;
                    elseif k==3
                    R_cc(1,j)=R_cc(1,j-2)+R_cc(14,j-1)/2;
                    R_cc(2,j)=R_cc(2,j-2)+R_cc(15,j-1)/2;
                    R_cc(3,j)=Res_cc(3,i)+DeltaTw/2;                
                    else
                    R_cc(1,j)=R_cc(1,j-3)+R_cc(14,j-1);
                    R_cc(2,j)=R_cc(2,j-3)+R_cc(15,j-1);
                    R_cc(3,j)=Res_cc(3,i)+DeltaTw;
                    end
     % Para condiciones de sobresaturación se requiere la humedad específica
     % del aire  en condiciones de saturación a Tas. Se añade 1 fila con wsa
     % R(20,j). El cálculo de j, k y l cambia en condiciones de saturación
     % frente a aire no saturado.
     
            R_cc(4,j)=(R_cc(3,j)+273.15)/2;   %Tªcps
            R_cc(5,j)=C1-C2*R_cc(4,j)+C3*(R_cc(4,j))^2-C4*(R_cc(4,j))^3;   %Cpa
            R_cc(6,j)=C5+C6*R_cc(4,j)-C7*(R_cc(4,j))^5+C8*(R_cc(4,j))^6;   %Cpv
            R_cc(7,j)=C13-C14*R_cc(4,j)+C15*(R_cc(4,j))^2-C16*(R_cc(4,j))^6;   %Cpw
            R_cc(8,j)=10^(C24*(1-(To/R_cc(3,j)))+C25*(log10(To/R_cc(3,j)))+C26*(1-10^((-8.29692)*((R_cc(3,j)/To)-1)))+C27*(10^((4.76955)*(1-(To/R_cc(3,j))))-1)+C28);   % pvs
            R_cc(9,j)=(C21*R_cc(8,j))/(pT-(C22*R_cc(8,j))); %wsw
            R_cc(10,j)=hfg+(R_cc(6,j)*(R_cc(3,j)-To));   %hv
            R_cc(11,j)=(R_cc(5,j)*(R_cc(3,j)-To))+R_cc(9,j)*R_cc(10,j); %hmasw
            R_cc(18,j)=T_da_ss(R_cc(2,j)/1000,R_cc(1,j),pT); % Tas
    %         [Tdb, humratio, phi, entalphy, Tdp, volume, Twb] =Psychrometricsnew('Tdb',R(18,j),'phi',100);
            R_cc(19,j)=w_a(R_cc(18,j),100,pT); % wsa
    %         R(19,j)=humratio; % wsa
            R_cc(12,j)=(C29^C30)*((((C31+R_cc(9,j))/(C31+R_cc(19,j)))-1)/(log(((C31+R_cc(9,j))/(C31+R_cc(19,j))))));   %Le
            R_cc(13,j)=(mw/ma)*(1-((ma/mw)*(wo-R_cc(1,j))));  %Balance de masa
            R_cc(14,j)=(DeltaTw*R_cc(7,j)*R_cc(13,j)*(R_cc(9,j)-R_cc(19,j)))/(R_cc(11,j)-R_cc(2,j)+(R_cc(12,j)-1)*(R_cc(11,j)-R_cc(2,j)-(R_cc(9,j)-R_cc(19,j))*R_cc(10,j)+(R_cc(1,j)-R_cc(19,j))*R_cc(7,j)*(R_cc(3,j)-To))+((R_cc(1,j)-R_cc(9,j))*R_cc(7,j)*(R_cc(3,j)-To))); %j
            R_cc(15,j)=(DeltaTw*R_cc(7,j)*R_cc(13,j))*(1+(((R_cc(9,j)-R_cc(19,j))*R_cc(7,j)*(R_cc(3,j)-To))/(R_cc(11,j)-R_cc(2,j)+(R_cc(12,j)-1)*(R_cc(11,j)-R_cc(2,j)-(R_cc(9,j)-R_cc(19,j))*R_cc(10,j)+(R_cc(1,j)-R_cc(19,j))*R_cc(7,j)*(R_cc(3,j)-To))+((R_cc(1,j)-R_cc(9,j))*R_cc(7,j)*(R_cc(3,j)-To))))); %k
            R_cc(16,j)=(DeltaTw*R_cc(7,j))/(R_cc(11,j)-R_cc(2,j)+(R_cc(12,j)-1)*(R_cc(11,j)-R_cc(2,j)-(R_cc(9,j)-R_cc(19,j))*R_cc(10,j)+(R_cc(1,j)-R_cc(19,j))*R_cc(7,j)*(R_cc(3,j)-To))+((R_cc(1,j)-R_cc(9,j))*R_cc(7,j)*(R_cc(3,j)-To))); %l
             end
             
    % Las 4 primeras filas son w, h, Tw y Me, calculadas con RK.          
    % Res(:,i+1)=[Res(1,i)+(R(14,j-3)+2*R(14,j-2)+2*R(14,j-1)+R(14,j))/6;(1000*Res(2,i)+(R(15,j-3)+2*R(15,j-2)+2*R(15,j-1)+R(15,j))/6)/1000;Res(3,i)+DeltaTw;Res(4,i)+(R(16,j-3)+2*R(16,j-2)+2*R(16,j-1)+R(16,j))/6;0;0;0;0;0;0;0;0;0;0];
            Res_cc(1,i+1)=Res_cc(1,i)+(R_cc(14,j-3)+2*R_cc(14,j-2)+2*R_cc(14,j-1)+R_cc(14,j))/6;
            Res_cc(2,i+1)=(1000*Res_cc(2,i)+(R_cc(15,j-3)+2*R_cc(15,j-2)+2*R_cc(15,j-1)+R_cc(15,j))/6)/1000;
            Res_cc(3,i+1)=Res_cc(3,i)+DeltaTw;
            Res_cc(4,i+1)=Res_cc(4,i)+(R_cc(16,j-3)+2*R_cc(16,j-2)+2*R_cc(16,j-1)+R_cc(16,j))/6;
            Res_cc(5,i+1)=T_da_ss(Res_cc(2,i+1),Res_cc(1,i+1),pT);
            Res_cc(6,i+1)=100;
            Res_cc(7,i+1)=Res_cc(5,i+1);
        end
    end
    
    w(f)=Res_cc(1,N+1);
    wo=w(f); 
    end
    
    %%%%-----------REPRESNTACION DE RESULTADOS POR PANTALLA-------
    %fprintf('\n                                                         RESULTADOS DE LA MATRIZ R');
    %fprintf('\nw(kg/kg)     |%f        |%f        |%f        |%f        |%f        |%f        |%f        |%f        |', R_cc(1,1),R_cc(1,2),R_cc(1,3),R_cc(1,4),R_cc(1,5),R_cc(1,6),R_cc(1,7),R_cc(1,8));
    %fprintf('\nhma(j/kg)    |%f    |%f    |%f    |%f    |%f    |%f    |%f    |%f    |', R_cc(2,1),R_cc(2,2),R_cc(2,3),R_cc(2,4),R_cc(2,5),R_cc(2,6),R_cc(2,7),R_cc(2,8));
    %fprintf('\nTw(ºC)       |%f      |%f      |%f      |%f      |%f      |%f      |%f      |%f      |', R_cc(3,1),R_cc(3,2),R_cc(3,3),R_cc(3,4),R_cc(3,5),R_cc(3,6),R_cc(3,7),R_cc(3,8));
    %fprintf('\nTw Cp(ºC)    |%f      |%f      |%f      |%f      |%f      |%f      |%f      |%f      |', R_cc(4,1),R_cc(4,2),R_cc(4,3),R_cc(4,4),R_cc(4,5),R_cc(4,6),R_cc(4,7),R_cc(4,8));
    %fprintf('\nCpa(J/kg*K)  |%f     |%f     |%f     |%f     |%f     |%f     |%f     |%f     |', R_cc(5,1),R_cc(5,2),R_cc(5,3),R_cc(5,4),R_cc(5,5),R_cc(5,6),R_cc(5,7),R_cc(5,8));
    %fprintf('\nCpv(J/kg*K)  |%f     |%f     |%f     |%f     |%f     |%f     |%f     |%f     |', R_cc(6,1),R_cc(6,2),R_cc(6,3),R_cc(6,4),R_cc(6,5),R_cc(6,6),R_cc(6,7),R_cc(6,8));
    %fprintf('\nCpw(J/kg*K)  |%f     |%f     |%f     |%f     |%f     |%f     |%f     |%f     |', R_cc(7,1),R_cc(7,2),R_cc(7,3),R_cc(7,4),R_cc(7,5),R_cc(7,6),R_cc(7,7),R_cc(7,8));
    %fprintf('\nPv(Pa)       |%f     |%f     |%f     |%f     |%f     |%f     |%f     |%f     |', R_cc(8,1),R_cc(8,2),R_cc(8,3),R_cc(8,4),R_cc(8,5),R_cc(8,6),R_cc(8,7),R_cc(8,8));
    %fprintf('\nWsw(Kg/kg)   |%f        |%f        |%f        |%f        |%f        |%f        |%f        |%f        |', R_cc(9,1),R_cc(9,2),R_cc(9,3),R_cc(9,4),R_cc(9,5),R_cc(9,6),R_cc(9,7),R_cc(9,8));
    %fprintf('\nhv(J/kg)     |%f  |%f  |%f  |%f  |%f  |%f  |%f  |%f  |', R_cc(10,1),R_cc(10,2),R_cc(10,3),R_cc(10,4),R_cc(10,5),R_cc(10,6),R_cc(10,7),R_cc(10,8));
    %fprintf('\nhma,sw(J/kg) |%f    |%f   |%f   |%f   |%f   |%f  |%f   |%f  |', R_cc(11,1),R_cc(11,2),R_cc(11,3),R_cc(11,4),R_cc(11,5),R_cc(11,6),R_cc(11,7),R_cc(11,8));
    %fprintf('\nLe           |%f        |%f        |%f        |%f        |%f        |%f        |%f        |%f        |', R_cc(12,1),R_cc(12,2),R_cc(12,3),R_cc(12,4),R_cc(12,5),R_cc(12,6),R_cc(12,7),R_cc(12,8));
    %fprintf('\nL/G          |%f        |%f        |%f        |%f        |%f        |%f        |%f        |%f        |', R_cc(13,1),R_cc(13,2),R_cc(13,3),R_cc(13,4),R_cc(13,5),R_cc(13,6),R_cc(13,7),R_cc(13,8));
    %fprintf('\nj            |%f        |%f        |%f        |%f        |%f        |%f        |%f        |%f        |', R_cc(14,1),R_cc(14,2),R_cc(14,3),R_cc(14,4),R_cc(14,5),R_cc(14,6),R_cc(14,7),R_cc(14,8));
    %fprintf('\nk            |%f    |%f    |%f    |%f    |%f    |%f    |%f    |%f    |', R_cc(15,1),R_cc(15,2),R_cc(15,3),R_cc(15,4),R_cc(15,5),R_cc(15,6),R_cc(15,7),R_cc(15,8));
    %fprintf('\nl            |%f        |%f        |%f        |%f        |%f        |%f        |%f        |%f        |', R_cc(16,1),R_cc(16,2),R_cc(16,3),R_cc(16,4),R_cc(16,5),R_cc(16,6),R_cc(16,7),R_cc(16,8));
    %fprintf('\nMe           |%f        |%f        |%f        |%f        |%f        |%f        |%f        |%f        |', R_cc(17,1),R_cc(17,2),R_cc(17,3),R_cc(17,4),R_cc(17,5),R_cc(17,6),R_cc(17,7),R_cc(17,8));
    %fprintf('\nk            |%f    |%f    |%f    |%f    |%f    |%f    |%f    |%f    |', R_cc(15,1),R_cc(15,2),R_cc(15,3),R_cc(15,4),R_cc(15,5),R_cc(15,6),R_cc(15,7),R_cc(15,8));
    
    
    
    %fprintf('\n\n\n                                                         RESULTADOS DE LA MATRIZ RES');
    %fprintf('\nw(kg/kg)     |%f      |%f      |%f      |', Res_cc(1,1),Res_cc(1,2),Res_cc(1,3));
    %fprintf('\nhma(j/kg)    |%f     |%f     |%f     |', Res_cc(2,1),Res_cc(2,2),Res_cc(2,3));
    %fprintf('\nTw(ºC)       |%f    |%f    |%f    |', Res_cc(3,1),Res_cc(3,2),Res_cc(3,3));
    %fprintf('\nMe           |%f      |%f      |%f      |', Res_cc(4,1),Res_cc(4,2),Res_cc(4,3));
    %fprintf('\nTdb(K)       |%f    |%f    |%f    |', Res_cc(5,1),Res_cc(5,2),Res_cc(5,3));
    %fprintf('\nPhi(-)   |%f     |%f    |%f    |', Res_cc(6,1),Res_cc(6,2),Res_cc(6,3));
    %fprintf('\nTwb(K)       |%f    |%f    |%f    |', Res_cc(7,1),Res_cc(7,2),Res_cc(7,3));
    
    Me_Poppe=Res_cc(4,N+1);
    %R_cc=R_cc;
    %Res_cc=Res_cc;
    
    %load PshycrometricChart.mat
    
    %figure, plot(PshycrometricChart(:,1),PshycrometricChart(:,3));
    %hold on, plot(PshycrometricChart(:,1),PshycrometricChart(:,4),'r:');
    %plot(PshycrometricChart(:,1),PshycrometricChart(:,5),'r:');
    %plot(PshycrometricChart(:,1),PshycrometricChart(:,6),'r:');
    %plot(PshycrometricChart(:,1),PshycrometricChart(:,7),'r:');
    %plot(PshycrometricChart(:,1),PshycrometricChart(:,8),'r:');
    %plot(PshycrometricChart(:,1),PshycrometricChart(:,9),'r:');
    %plot(PshycrometricChart(:,1),PshycrometricChart(:,10),'r:');
    %plot(PshycrometricChart(:,1),PshycrometricChart(:,11),'r:');
    %plot(PshycrometricChart(:,1),PshycrometricChart(:,12),'r:');
    %---------- axis([0 40 0 60])
    
    
    %plot((Res_cc(5,:)-273.15),(Res_cc(1,:)*1000),'k');
    
    %xlabel('Temperatura (ºC)','FontName','TrebuchetMS','FontSize', 11);
    %ylabel('Humedad (g_v / kg_{as})','FontName','TrebuchetMS','FontSize', 11);
    %text(3,45,'Presión = 101325 Pa','FontSize',7)
    %legend 'BOXOFF'
    
    M_lost_wct = ma*(Res_cc(1,N+1)-Res_cc(1,1));
    
end
