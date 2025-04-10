function cp_water = cpSatVapPW(pressure)

% cpSatVapPW.m
% Usage: cp_water = cpSatVapPW(pressure)
% pressure in bar
% cp_water in kJ/kg-K
% Created by Diego Alarcón (11/02/2021)
% Last modification by Diego Alarcón (11/02/2021)
%

[num_row,num_col]=size(pressure);
cp_water=zeros(max(num_row,num_col),1);


for k=1:max(num_row,num_col)
    if isnan(pressure(k))
        cp_water(k)=NaN;
    else
        cp_water(k)=XSteam('CpV_P',pressure(k));
    end;
end;



