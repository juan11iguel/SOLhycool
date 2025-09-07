function [n_dc] = scale_dc(P_nom)
%  SCALE_DC calculates the number of dc's (ache's) required to cool a P_nom
%  thermal power
%  The ACHE base considered is the one of the WASCOP pilot plant (200 kW)

%%  Inputs & Outputs
%   P_nom           - nominal power of the scaled ACHE (kW)
%   n_dc            - number of ACHE's required

%%  Parameters:
%   dT              - diferencia de temperatura nominal en el SC-tubos
%   Tm              - temperatura media nominal en el SC-tubos (ºC)
%   n_tb_piloto     - número de tubos en paralelo en DC planta piloto
%   m_dc_piloto     - flujo másico nominal en planta piloto (kg/s)

arguments (Input)
        P_nom (1,1) double {mustBePositive}
end

arguments (Output)
        n_dc (1,1) double 
end

dT = 7; % como en WASCOP (40-33) ºC https://collab.psa.es/index.php/f/264130
n_tb_piloto = 60; % número de tubos en DC planta piloto
Tm = 36.5; % como en WASCOP
m_dc_piloto= 24*1000/3600; 

% %% flujo másico nominal por los tubos del SC: msc (kg/s)
msc_nom=P_nom/(XSteam('Cp_pT',2,Tm).*dT); %kg/s


%% flujo másico nominal agua por el conjunto de ACHEs (kg/s)
mdc_nom=msc_nom; %kg/s

%% mtubo DC en planta piloto = planta escalada (kg/s)
mt_dc_nom=m_dc_piloto/n_tb_piloto;

%% número de DCs en planta escalada 
n_tb_scaled = mdc_nom/mt_dc_nom;
n_dc=n_tb_scaled/n_tb_piloto;
n_dc=round(n_dc);

end