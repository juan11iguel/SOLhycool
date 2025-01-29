function U = condenser_heat_transfer_coefficient(qc, Tc_in, Tv, option)
    %Correlación de U para Surface Condenser
    % inputs:
    %   mc (m3/h): caudal de agua que circula por dentro de los tubos
    %   Tcin (ºC): temperatura del agua a la entrada de los tubos
    %   Tv (ºC): temperatura del vapor
    %   option: tipo de correlación seleccionada (1-7)
    % outputs:
    %   U (kW/m2ºC): coef de transferencia de calor
    arguments
        qc (1,1) double
        Tc_in (1,1) double
        Tv (1,1) double
        option (1,1) int8 {mustBeInRange(option, 1, 7)} = 7
    end
    
    qc2=qc*1000; %kg/h
    switch option
        case 1
            %% Correlación de U en función de mc (kg/h) y Tv (ºC)
            p1=0.128;
            p2=23.4865;
            p3=3.7088E-04;
            p4=-198.473;
            p5=-0.1444;
            p6=-1.7952E-06;
            U=p1*qc2+p2*Tv+p3*Tv*qc2+p4+p5*Tv^2+p6*qc2^2;
        case 2
            %% Correlación de U en función de Tcin (ºC) y Tv (ºC)
            p1=120.73;
            p2=-69.79;
            p3=-6.69;
            p4=2091.34;
            p5=2.27;
            p6=4.37;
            U=p1*Tc_in+p2*Tv+p3*Tv*Tc_in+p4+p5*Tv^2+p6*Tc_in^2;
        case 3
            %% Correlación de U en función de mc_tubo (kg/h) y Tcwin (ºC) 
            p1=12.7054620668315;
            p2=2.91062113817186;
            p3=0.00953039010846794;
            p4=343.289496507627;
            p5=-0.00100009808582273;
            p6=-0.0483094341070905;
            mc2_tubo=qc2/24;
            U=p1*Tc_in+p2*mc2_tubo+p3*mc2_tubo*Tc_in+p4+p5*mc2_tubo^2+p6*Tc_in^2;
        case 4 % valor nominal según especificaciones
            U=1582*4184/3600;   %1.582-> https://collab.psa.es/f/174826; %
        case 5
            %valor medio de los obtenidos a partir de Calibra_Uexp.m
            U=1377.3;
        case 6 %correlación obtenida a partir de Calibra_Uexp.m
           mc2_tubo=qc2/24;
           p00 =      0.1508;
           p10 =     0.06595 ;
           p01 =     -0.0007606  ;
           p20 =    -0.00153  ;
           p11 =    7.008e-05  ;
           p02 =     -5.328e-07  ;
           U = (p00 + p10*Tc_in + p01*mc2_tubo + p20*Tc_in^2 + p11*Tc_in*mc2_tubo + p02*mc2_tubo^2)*1000;
    
        case 7 %correlación obtenida a partir de Calibra_Uexp.m pero con "SC_data_DoE_recortado.mat"
            mc2_tubo=qc2/24;
           p00 =      0.8285  ;
           p10 =   -0.008205 ;
           p01 =   4.938e-05 ;
           p20 =  -6.011e-05  ;
           p11 =   6.084e-05 ;
           p02 =  -8.933e-07 ;
           U = (p00 + p10*Tc_in + p01*mc2_tubo + p20*Tc_in^2 + p11*Tc_in*mc2_tubo + p02*mc2_tubo^2)*1000;
    
    end
    U=U/1000; % kW/m2ºC 
end