function cv_water = cvSatVapTW(temperature)

% cvSatVapTW.m
% Usage: cp_water = cvSatVapTW(temperature)
% temperature in ºC
% cv_water in kJ/kg-K
% Created by Diego Alarcón (11/02/2021)
% Last modification by Diego Alarcón (11/02/2021)
%

[num_row,num_col]=size(temperature);
cv_water=zeros(max(num_row,num_col),1);


for k=1:max(num_row,num_col)
    if isnan(temperature(k))
        cv_water(k)=NaN;
    else
        cv_water(k)=XSteam('CvV_T',temperature(k));
    end;
end;



