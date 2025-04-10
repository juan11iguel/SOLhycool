function dens_water = densSatLiqPW(pressure)

% densSatLiqPW.m
% Usage: dens_water = densSatLiqPW(pressure)
% pressure in bar
% dens_water in kg/m3
% Created by Diego Alarcón (11/02/2021)
% Last modification by Diego Alarcón (11/02/2021)
%

[num_row,num_col]=size(pressure);
dens_water=zeros(max(num_row,num_col),1);


for k=1:max(num_row,num_col)
    if isnan(pressure(k))
        dens_water(k)=NaN;
    else
        dens_water(k)=XSteam('rhoL_p',pressure(k));
    end;
end;



