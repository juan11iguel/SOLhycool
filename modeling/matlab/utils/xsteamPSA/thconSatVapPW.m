function thcon_water = thconSatVapPW(pressure)

% thconSatVapPW.m
% Usage: thcon_water = thconSatVapPW(pressure)
% pressure in bar
% thcon_water in W/m-K
% Created by Diego Alarcón (11/02/2021)
% Last modification by Diego Alarcón (11/02/2021)
%

[num_row,num_col]=size(pressure);
thcon_water=zeros(max(num_row,num_col),1);


for k=1:max(num_row,num_col)
    if isnan(pressure(k))
        thcon_water(k)=NaN;
    else
        thcon_water(k)=XSteam('tcV_p',pressure(k));
    end;
end;



