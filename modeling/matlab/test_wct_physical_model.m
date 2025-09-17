%%
% Enable all warnings
warning('on', 'all');

% Condensador: (qmin, qmax) m3/h: [3456, 11880]
% Torre (qmin, qmax) m3/h: [1152, 3960]
clc; clear all

Tamb=23;
HR=40;
Twct_in = 33;
Mwct = linspace(1152, 3960, 10);
SC_fan_wct = 20:10:90;

Twct_out = zeros(length(Mwct), length(SC_fan_wct));
cnt=1;
for j=1:length(Mwct)

    for i=1:length(SC_fan_wct)
        tic
        [Twct_ou, Pe, M_lost_wct] = wct_model_physical_andasol(Tamb, HR, Twct_in, Mwct(j), SC_fan_wct(i));
        Twct_out(j, i) = Twct_ou;
        fprintf("Completed %d/%d in %.2f sec | q = %.0f, w = %.0f --> Tout = %.2f, M_lost_wct (m³/h) = %.2f\n", cnt, length(Mwct)*length(SC_fan_wct), toc, Mwct(j), SC_fan_wct(i), Twct_ou, M_lost_wct*1e-3)
        cnt=cnt+1;
    end
end

%% Visualize

figure
plot(SC_fan_wct, Twct_out, 'LineWidth', 1.5)

% Add axis labels
xlabel('Fan Control (% of maximum speed)', 'FontSize', 16, 'FontWeight', 'bold')
ylabel('WCT Outlet Temperature (°C)', 'FontSize', 16, 'FontWeight', 'bold')
title('Cooling Tower Performance: Outlet Temperature vs Fan Control', 'FontSize', 18, 'FontWeight', 'bold')

% Add grid for better readability
grid on
grid minor

% Add legend with flow values for each line
legend_labels = cell(length(Mwct), 1);
for i = 1:length(Mwct)
    legend_labels{i} = sprintf('Flow: %.0f m³/h', Mwct(i));
end
legend(legend_labels, 'Location', 'best', 'FontSize', 14)

% Add text annotations for flow values at the end of each line
hold on
for i = 1:length(Mwct)
    % Add text at the rightmost point of each line
    text(SC_fan_wct(end) + 1, Twct_out(i, end), sprintf('%.0f m³/h', Mwct(i)), ...
         'FontSize', 13, 'FontWeight', 'bold', 'Color', 'black', ...
         'HorizontalAlignment', 'left', 'VerticalAlignment', 'middle')
end
hold off

% Improve figure appearance
set(gca, 'FontSize', 14)
xlim([SC_fan_wct(1) - 2, SC_fan_wct(end) + 8]) % Extend x-axis to accommodate text labels

% [Twct_ot, Ce, Cw] = wct_model_data(Tamb, HR, Twct_in, Mwct, SC_fan_wct, ...
%     model_data_path="/home/patomareao/development/SOLhycool/modeling/data/models_data/model_data_wct_fp_andasol_gaussian_cascade.mat", ...
%     silence_warnings=true, ...
%     raise_error_on_invalid_inputs=true, ...
%     lb=[0.1,   0.1,     5.0,      1107.,   0.], ...
%     ub=[50.,   99.99,   55.,      3960.,   95.], ...
%     n_wct=1 ...
% )