function [Qreleased, Qabsorbed, Qtransferred, Qtable] = compute_condenser_heats(data, n_options, options)
%COMPUTE_CONDENSER_HEATS Function that computes thermal power in a
%condenser. Computes and visualizes thermal power from load, coolant and 
% transfer medium sides and compares them.
%   It includes latent heat released by vapor(Qreleased), heat absorbed by
%   the coolant (Qabsorned) and the heat transferred by the heat exchanger
%   (Qtransferred), which is computed for every heat transfer coefficient
%   alternative. Ideally they should all match, in practice they don't. All
%   heats have kW units.

arguments (Input)
    data table
    n_options int8
    options.visualize logical = false
end

arguments (Output)
    Qreleased 
    Qabsorbed
    Qtransferred
    Qtable
end

N = height(data);

Qreleased = zeros(1, N);
Qabsorbed = zeros(1, N);

Qtransferred =zeros(n_options, N);
for i=1:N
    for option=1:n_options
        Q = condenser_heats_model(data.mv(i)/3600, data.Tv(i), data.qc(i)/3.6, data.Tc_in(i), data.Tc_out(i), option=option);
        Qtransferred(option, i) = Q(3);
    end
    Q = condenser_heats_model(data.mv(i)/3600, data.Tv(i), data.qc(i)/3.6, data.Tc_in(i), data.Tc_out(i), option=7);
    [Qreleased(i), Qabsorbed(i)] = deal(Q(1), Q(2));
end
data.Qreleased = Qreleased';
data.Qabsorbed = Qabsorbed';

% Build outout table
columnNames = arrayfun(@(i) sprintf('Qtransferred_option_%d', i), 1:n_options, 'UniformOutput', false);
Qtable = array2table(Qtransferred', 'VariableNames', columnNames);


if options.visualize
columnNames = arrayfun(@(i) sprintf('Qtr,opt%d', i), 1:n_options, 'UniformOutput', false);
data_plot = [Qreleased', Qabsorbed', Qtransferred'];
groupLabels = [{'Qreleased', 'Qabsorbed'}, columnNames];

figure("Units","normalized")
% Create a tiled layout
t = tiledlayout("flow"); % Rows = number of data rows
dates = data.date;

% Colors and line styles
colors = [1, 0, 0; 0, 1, 0; 0, 0, 1]; % Red, Green, Blue
% Store average errors for global subtitle
avgErrors = zeros(N, n_options);

% Plot each row as a bar chart
for i = 1:N
    nexttile; % Create a new tile for each row
    b = bar(data_plot(i, :), 'FaceColor', 'flat');
    
    % Calculate (Qreleased + Qabsorbed)/2
    avgValue = mean([Qreleased(i), Qabsorbed(i)]);

    % Compute absolute difference for each Qtransferred option
    absDiffs = abs(Qtransferred(:, i)' - avgValue);

    % Compute the average error for this date
    avgErrors(i, :) = absDiffs; % Accumulate for global mean

    % Set colors
    b.Labels = strings(1, n_options+2);
    for j = 1:numel(b.YData)
        if j == 1
            b.CData(j,:) = colors(1, :); % Qreleased (Red)
        elseif j == 2
            b.CData(j,:) = colors(2, :); % Qabsorbed (Green)
        else
            b.CData(j,:)= colors(3, :); % Qtransferred_* (Blue)
        end
    end
    b.Labels(1,3:end) = string(arrayfun(@(n_opt) sprintf('%.2f', absDiffs(n_opt)), 1:n_options, 'UniformOutput', false));

    % Plot horizontal line at the average
    hold on;
    yline(avgValue, '--k', 'LineWidth', 1.5, 'Label', 'Avg Q', 'LabelVerticalAlignment', 'bottom');

    % Set subplot title with absolute differences
    title(sprintf('Tile %d: %s', i, datestr(dates(i))))% \nAvg Diff: %s, num2str(absDiffs, ' %.2f ')));
    
    % Add labels and title
    % title(sprintf('Tile %d: %s', i, datestr(dates(i))));
    ylabel('Value (kW)');
    xticks(1:numel(data(i, :)));
    xticklabels(groupLabels);
    xtickangle(45);
    set(gca, 'TickLabelInterpreter', 'none'); % Disable interpreter to avoid weird symbols

    ylim([0 320]); % Set common Y-axis limits
    grid on;
    hold off;
end

% Add global title
sgtitle({'Heat released by vapor, absorbed by coolant, and transferred by heat exchanger', ...
         sprintf('Mean Absolute Error per Option: %s', num2str(mean(avgErrors), ' %.2f '))});

% Global layout adjustments
t.TileSpacing = 'compact';
t.Padding = 'compact';

end

end

