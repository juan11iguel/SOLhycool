function [n_tb_sc_scaled, A_scaled] = scale_sc(P_nom, Tv_nom)
%  SCALE_DSC calculates the number of tubes in parallel required to condensate a vpour characterized by a P_nom
%  thermal power
%  The SC base considered is the one of the WASCOP pilot plant (200 kW)

%%  Inputs & Outputs
%   P_nom           - nominal power of the scaled SC (kW)
%   n_tb_sc_scaled  - number of tubes in parallel required inside SC
%   A_scaled        - Area (m2)

%%  Parameters:
%   dT              - diferencia de temperatura nominal en el SC-tubos
%   Tm              - temperatura media nominal en el SC-tubos (ºC)
%   n_tb_piloto     - número de tubos en paralelo en SC planta piloto
%   Tc_in_C         - Inlet water temperature inside SC tubes
%   overdesign      - Overdesign percentage in pilot SC

arguments (Input)
        P_nom (1,1) double {mustBePositive}
        Tv_nom (1,1) double {mustBePositive} = 41.5
end

arguments (Output)
        n_tb_sc_scaled (1,1) double
        A_scaled (1,1) double
end

Tc_in_C = 33; %como en WASCOP (40.2-33) ºC https://collab.psa.es/index.php/f/271168
Tc_out_C = 40.02; %como en WASCOP (40.2-33) ºC https://collab.psa.es/index.php/f/271168
dT = Tc_out_C-Tc_in_C; 
n_tb_piloto = 24; % número de tubos en SC planta piloto (96 tubos /4 pasos)
Tm = 36.5; % como en WASCOP
qsc_nom_piloto = 9828/1000; %m3/h
msc_nom_piloto = qsc_nom_piloto*1000/3600; %kg/s
mt_sc_nom_piloto = msc_nom_piloto/ n_tb_piloto;
mt_sc_nom_scaled = mt_sc_nom_piloto; % suponemos el mismo flujo másico por tubo
overdesign = 1.8464; % 84.64 %

% %% flujo másico nominal TOTAL antes de disrtibuirse por los tubos del SC: msc (kg/s)
msc_nom_scaled=P_nom/(XSteam('Cp_pT',2,Tm).*dT); %kg/s

fprintf("Nominal mass flow rate vapor? cooling? %.3f\n", msc_nom_scaled)

% %% número de tubos en paralelo en planta escalada (suponiendo el mismo flujo másico por tubo que en planta piloto)
n_tb_sc_scaled = msc_nom_scaled/mt_sc_nom_scaled;
n_tb_sc_scaled = round(n_tb_sc_scaled);

%% Calculo de A_scaled

U_kcal = 1582.26; % kcal/m2-h-C
U = U_kcal*4.184/3600;  %W/m2-C
dT1 = Tv_nom-Tc_in_C;
dT2 = Tv_nom-Tc_out_C;
LMTD = (dT1-dT2)/log(dT1/dT2) ;
A_scaled = P_nom/(U*LMTD);
A_scaled = A_scaled*overdesign;

end