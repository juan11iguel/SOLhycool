function [Tc_out_C, Ce_kW, Pcool_req] = surface_condenser_model(Mv_kgs, Tv_C, mc_m3h, Tc_in_C)
    
    % Changelog
    % - 20240205. Added subcooling

    Pc=1.6; % bar
    deltaTsubcooling = 2;

    mc_kgs = mc_m3h/3600*densW(25, Pc); % m3/h -> kg/s

    Pcool_req_lat = Mv_kgs*(enthalpySatVapTW(Tv_C)-enthalpySatLiqTW(Tv_C));
    Pcool_req_sen = Mv_kgs*cpW(Tv_C, Pc)*(deltaTsubcooling);
    Pcool_req = Pcool_req_lat + Pcool_req_sen;

    Tc_out_C = Tc_in_C + Pcool_req/(mc_kgs*cpW(Tc_in_C, Pc));

    Ce_kW = power_consumption(mc_m3h);

end


function P_pump = power_consumption(q_m3h)
    % q_m3h (m³/h) -> P_pump (kW)
    % f(x) = p1*x^3 + p2*x^2 + p3*x + p4
    % Aqui habria que incluir informacion de donde estan los datos / codigo
    % donde se haya hecho este ajuste

           p1 =    0.1461;
           p2 =    5.763;
           p3 =    -38.32;
           p4 =    227.8;

    P_pump=(p1.*q_m3h.^3 + p2.*q_m3h.^2 + p3.*q_m3h + p4)/1000; %kW
end