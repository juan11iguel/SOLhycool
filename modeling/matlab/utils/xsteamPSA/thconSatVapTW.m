function thcon_water = thconSatVapTW(temperature)

% thconSatVapTW.m
% Usage: entropy_water = thconSatVapTW(temperature)
% temperature in ºC
% thcon_water in W/m-K
% Created by Diego Alarcón (11/02/2021)
% Last modification by Diego Alarcón (11/02/2021)
%

[num_row,num_col]=size(temperature);
thcon_water=zeros(max(num_row,num_col),1);


for k=1:max(num_row,num_col)
    if isnan(temperature(k))
        thcon_water(k)=NaN;
    else
        thcon_water(k)=XSteam('tcV_T',temperature(k));
    end;
end;




