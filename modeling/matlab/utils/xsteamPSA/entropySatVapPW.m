function entropy_water = entropySatVapPW(pressure)

% entropySatVapPW.m
% Usage: entropy_water = entropySatVapPW(pressure)
% pressure in bar
% entropy_water in kJ/kg-K
% Created by Diego Alarcón (11/02/2021)
% Last modification by Diego Alarcón (11/02/2021)
%

[num_row,num_col]=size(pressure);
entropy_water=zeros(max(num_row,num_col),1);


for k=1:max(num_row,num_col)
    if isnan(pressure(k))
        entropy_water(k)=NaN;
    else
        entropy_water(k)=XSteam('sV_p',pressure(k));
    end;
end;



