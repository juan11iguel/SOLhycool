function FF = SurfaceCondeser_v4(x, A, Tv, Q, mc, options)
%UNTITLED Summary of this function goes here
%   Detailed explanation goes here
% 
% x(1): Tcin
% x(2): Tcout

% global ms mc Tcin;

% mc: caudal de cooling (m3/h)
% Tcin: temperatura de entrada cooling (ºC)
% Q: thermal power (kW)


mc_u=mc*1000/3600; % kg/s

corr=options.parameters.condenser_option;
U=condenser_heat_transfer_coefficient(mc, x(1), Tv, corr);

landa=XSteam('hV_T',Tv)-XSteam('hL_T',Tv);
Cp=XSteam('Cp_pT',2,(x(1)+x(2))/2);
dT1=Tv-x(1);
dT2=Tv-x(2);

dTML=(dT1-dT2)/log(dT1/dT2) ;



F(1) = Q-mc_u*Cp*(x(2)-x(1));
F(2) = Q-U*A*dTML;
FF=F(1)^2+F(2)^2;
end