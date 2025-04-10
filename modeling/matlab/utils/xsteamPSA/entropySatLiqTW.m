function entropy_water = entropySatLiqTW(temperature)

% entropySatLiqTW.m
% Usage: entropy_water = entropySatLiqTW(temperature)
% temperature in ºC
% entropy_water in kJ/kg-K

[num_row,num_col]=size(temperature);
entropy_water=zeros(max(num_row,num_col),1);


for k=1:max(num_row,num_col)
    if isnan(temperature(k))
        entropy_water(k)=NaN;
    else
        entropy_water(k)=XSteam('sL_T',temperature(k));
    end;
end;




