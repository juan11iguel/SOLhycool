function cv_water = cvSatVapPW(pressure)

% cvSatVapPW.m
% Usage: cv_water = cvSatVapPW(pressure)
% pressure in bar
% cv_water in kJ/kg-K
% Created by Diego Alarcón (11/02/2021)
% Last modification by Diego Alarcón (11/02/2021)
%

[num_row,num_col]=size(pressure);
cv_water=zeros(max(num_row,num_col),1);


for k=1:max(num_row,num_col)
    if isnan(pressure(k))
        cv_water(k)=NaN;
    else
        cv_water(k)=XSteam('CvV_P',pressure(k));
    end;
end;



