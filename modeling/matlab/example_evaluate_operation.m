data = readtable("../assets/data.csv");

%% Evaluate wct fan speed given outlet temperature
for i=1:height(data)
    if ~(data.qwct(i) > 0.5)
        continue
    end
    [wwct, valid] = wct_inverse_model(data.Tamb(i), data.HR(i), data.Twct_in(i), data.qwct(i), data.Twct_out(i));

    fprintf("Point %d | wwct model: %.2f, wwct experimental: %.2f | Valid: %s\n", i, wwct, data.wwct(i), string(valid))
end

%% Evaluate operation point given everything but the wct fan frequency


parameters = default_parameters();
parameters.condenser_option = 7;
options = struct('model_type', 'data', 'lb', nan, 'ub', nan, 'x0', nan, 'silence_warnings', false, 'parameters', parameters);

for i=1:height(data)
    % if ~(data.qwct(i) > 0.5)
    %     continue
    % end
    [Ce_kWe, Cw_lh, detailed, valid] = evaluate_operation(data.Tamb(i), HR_pp, data.mv(i), data.qc(i), data.Rp(i), data.Rs(i), data.wdc(i), data.Tv(i));

    fprintf("Point %d | wwct model: %.2f, wwct experimental: %.2f | Valid: %s\n", i, detailed.wwct, data.wwct(i), string(valid))
    fprintf("Tc_in_ref= %.2f, Tc_in_mod=%.2f | Tc_out_ref= %.2f, Tc_out_mod=%.2f | Tdc_out_ref= %.2f, Tdc_out_mod=%.2f | Twct_in_ref= %.2f, Twct_in_mod=%.2f | Twct_out_ref= %.2f, Twct_out_mod=%.2f\n\n", ...
        data.Tc_in(i), detailed.Tc_in, data.Tc_out(i), detailed.Tc_out, data.Tdc_out(i), detailed.Tdc_out, data.Twct_in(i), detailed.Twct_in, data.Twct_out(i), detailed.Twct_out)
end

