function entropy_water = entropySatVapTW(temperature)

% entropySatVapTW.m
% Usage: entropy_water = entropySatVapTW(temperature)
% temperature in ºC
% entropy_water in kJ/kg-K

[num_row,num_col]=size(temperature);
entropy_water=zeros(max(num_row,num_col),1);


for k=1:max(num_row,num_col)
    if isnan(temperature(k))
        entropy_water(k)=NaN;
    else
        entropy_water(k)=XSteam('sV_T',temperature(k));
    end;
end;




