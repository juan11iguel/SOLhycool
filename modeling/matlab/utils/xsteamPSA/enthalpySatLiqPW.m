function enthalpy_water = enthalpySatLiqPW(pressure)

% enthalpySatLiqPW.m
% Usage: enthalpy_water = enthalpySatLiqPW(pressure)
% pressure in bar
% enthalpy_water in kJ/kg
% Created by Diego Alarcón (11/02/2021)
% Last modification by Diego Alarcón (11/02/2021)
%

[num_row,num_col]=size(pressure);
enthalpy_water=zeros(max(num_row,num_col),1);


for k=1:max(num_row,num_col)
    if isnan(pressure(k))
        enthalpy_water(k)=NaN;
    else
        enthalpy_water(k)=XSteam('hL_p',pressure(k));
    end;
end;



