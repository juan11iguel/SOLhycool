function cp_water = cpSatVapTW(temperature)

% cpSatVapTW.m
% Usage: cp_water = cpSatVapTW(temperature)
% temperature in ºC
% cp_water in kJ/kg-K
% Created by Diego Alarcón (11/02/2021)
% Last modification by Diego Alarcón (11/02/2021)
%

[num_row,num_col]=size(temperature);
cp_water=zeros(max(num_row,num_col),1);


for k=1:max(num_row,num_col)
    if isnan(temperature(k))
        cp_water(k)=NaN;
    else
        cp_water(k)=XSteam('CpV_T',temperature(k));
    end;
end;



