function Ce_c = recirculation_pump_consumption(qc)
    % q (m³/h) -> P_pump (kW)
    % f(x) = p1*x^3 + p2*x^2 + p3*x + p4
           p1 =    0.1461;
           p2 =    5.763;
           p3 =    -38.32;
           p4 =    227.8;
    Ce_c =max((p1.*qc.^3 + p2.*qc.^2 + p3.*qc + p4)*1e-3, 0); %kW
end