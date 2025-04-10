function enthalpy_satvap = enthalpySatVapTW(temperature)

% enthalpySatVapTW.m
% Usage: enthalpy_satvap = enthalpySatVapTW(temperature)
% temperature in ºC
% enthalpy in kJ/kg

[num_row,num_col]=size(temperature);
enthalpy_satvap=zeros(max(num_row,num_col),1);


for k=1:max(num_row,num_col)
    if isnan(temperature(k))
        enthalpy_satvap(k)=NaN;
    else
        enthalpy_satvap(k)=XSteam('hV_T',temperature(k));
    end;
end;
