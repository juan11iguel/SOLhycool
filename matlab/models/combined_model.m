function [Tout, Cw, Ce_cc, detailed] = combined_model(Tamb, HR, mc_m3h, Tin, R1, R2, w_dc_fan, w_wct_fan)
    % Combined model of a wet cooling tower (WC) and dry cooling (DC) that can
    % be configured based on three-way valves R1 and R2 (see model_hybrid_system.png 
    % for graphical description).
    %
    % Nomenclature

    % Limits
    m_dc_min = 5; % Imposed by DC model
    m_dc_max = 24;

    m_wct_min = 5.7; % Imposed by WCT model
    m_wct_max = 24;
    
    w_dc_fan_min = 11; %
    w_dc_fan_max = 99.18;

    w_wct_fan_min = 21; %
    w_wct_fan_max = 93.4161; %

    T_dc_in_min = 33.16;
    T_dc_in_max = 41.92;

    T_wct_in_min = 31.17;
    T_wct_in_max = 40.94;

    % Calculations

    % Dry cooler
    m_dc = mc_m3h*(1-R1);
    Tdc_in = Tin;

    if m_dc >= m_dc_min && m_dc <= m_dc_max && ...
       w_dc_fan >= w_dc_fan_min && w_dc_fan <= w_dc_fan_max && ...
       Tdc_in >= T_dc_in_min && Tdc_in <= T_dc_in_max

        % Evaluate model
        [Tdc_out, Ce_dc] = dc_model_PSA(Tamb, Tdc_in, m_dc, w_dc_fan);
        if Ce_dc<0
            warning('combined_model:unreasonable_cost', 'Electrical consumption of DC does not make sense: %.2f', Ce_dc)
            Ce_dc = 0;
        end
    
    else
        % Skip dry cooler
        Tdc_out = Tdc_in;
        Ce_dc = 0;
    end

    % Mixer 1
    m_vm = m_dc*R2;
    [m_wct, Twct_in] = mixer(mc_m3h*R1 + 1e-6, m_vm, Tin, Tdc_out);
    % m_wct = m_dc*R2 + mc_m3h*R1 + 1e-6;
    % Twct_in = (mc_m3h*R1*Tin + m_dc*R2*Tdc_out) / m_wct;

    % Wet cooling tower
    if m_wct >= m_wct_min && m_wct <= m_wct_max && ...
       w_wct_fan >= w_wct_fan_min && w_wct_fan <= w_wct_fan_max && ...
       Twct_in >= T_wct_in_min && Twct_in <= T_wct_in_max
        
        % Evaluate model
        [Twct_out, Cw, ~, Ce_wct] = wct_model_PSA(Tamb, HR, Twct_in, m_wct, w_wct_fan);
    
        if Cw < 0
            warning('combined_model:unfeasible_output', ['The conditions ' ...
                    'Tamb=%.0f, HR=%.0f, Tin=%.2f, q=%.2f, w=%.1f produced an' ...
                    'unreasonable output: Cw=%.2f'], Tamb, HR, Twct_in, m_wct, w_wct_fan, Cw)
            Cw = 0;
        end
    
    else
        % Skip wet cooling tower
        Twct_out = Twct_in;
        Ce_wct = 0;
        Cw = 0;

    end

    % Mixer 2
    [m_mix2, Tout] = mixer(m_dc*(1-R2), m_wct, Tdc_out, Twct_out);
    
    if abs(m_mix2 - mc_m3h) > 0.1
        throw(MException('combined_model:mass_balance_error', 'Mass balances not gud'))
    end

    % m_mix2 = m_wct + m_dc*(1-R2); % == mdot
    % Tout = (m_wct*Twct_out + m_dc*(1-R2)*Tdc_out) / (m_mix2);

    % Combined cooler total electrical consumption
    Ce_cc = Ce_dc + Ce_wct;

    d = struct;
    
    % Inputs
    d.Tamb = Tamb;
    d.HR = HR;
    d.R1 = R1;
    d.R2 = R2;
    % costs
    d.Ce_dc = Ce_dc; % kWe
    d.Ce_wct = Ce_wct; % kWe
    d.Ce_cc = Ce_cc; % kWe
    d.Cw_wct = Cw; % m3
    % flows
    d.q_wct = m_wct;
    d.q_dc = m_dc;
    d.q_vm = m_vm;
    d.q_c = mc_m3h;
    % temperatures
    d.Tdc_in = Tdc_in;
    d.Twct_in = Twct_in;
    d.Tdc_out = Tdc_out;
    d.Twct_out = Twct_out;
    % control signals
    d.w_dc = w_dc_fan;
    d.w_wct = w_wct_fan;
    
    detailed = d;

end

% function P_pump = power_consumption(q_m3h)
%     % Keep in mind that this consumption is already accounted for in
%     % surface_condenser_model
%     %
%     % q_m3h (m³/h) -> P_pump (kW)
%     % f(x) = p1*x^3 + p2*x^2 + p3*x + p4
%     % Aqui habria que incluir informacion de donde estan los datos / codigo
%     % donde se haya hecho este ajuste
% 
%            p1 =    0.1461;
%            p2 =    5.763;
%            p3 =    -38.32;
%            p4 =    227.8;
% 
%     P_pump=(p1.*q_m3h.^3 + p2.*q_m3h.^2 + p3.*q_m3h + p4)/1000; %kW
% end

% function raise_error(variable, lower_limit, upper_limit)
%     msg = sprintf("Input %s is outside limits (%.2f > %s > %.2f)", string(variable), lower_limit, string(variable), upper_limit);
%     throw(MException('DC_model:invalid_input', msg))
% end