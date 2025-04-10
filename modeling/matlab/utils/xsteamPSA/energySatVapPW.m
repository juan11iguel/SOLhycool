function energy_water = energySatVapPW(pressure)

% energySatVapPW.m
% Usage: energy_water = energySatVapPW(pressure)
% pressure in bar
% energy_water in kJ/kg
% Created by Diego Alarcón (11/02/2021)
% Last modification by Diego Alarcón (11/02/2021)
%

[num_row,num_col]=size(pressure);
energy_water=zeros(max(num_row,num_col),1);


for k=1:max(num_row,num_col)
    if isnan(pressure(k))
        energy_water(k)=NaN;
    else
        energy_water(k)=XSteam('uV_p',pressure(k));
    end;
end;



